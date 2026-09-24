#!/usr/bin/env python3
"""NightWing isolated WDOS Stage 2 browser QA. Product source is never modified."""
from __future__ import annotations
import os, sys, json, uuid, re, shutil, subprocess, tempfile, signal, secrets
from pathlib import Path
from datetime import timedelta

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT
OUT = ROOT/'.hermes'/'stage2-fidelity-qa'; OUT.mkdir(parents=True, exist_ok=True)
PORT = int(os.environ.get('WDOS_QA_PORT', '8195')); BASE = f'http://127.0.0.1:{PORT}'
CHROME=os.environ.get('WDOS_CHROME_PATH') or None
ROUTES={'AUTH-01':'/','AUTH-02':'/auth/login/','AUTH-03':'/auth/register/','AUTH-04':'/auth/verify/','AUTH-05':'/auth/invitation/','AUTH-06':'/auth/recover/','AUTH-07':'/auth/reset/','AUTH-08':'/auth/mfa/','AUTH-09':'/auth/status/'}
LANGS=['en','fr','pt','ar','sw']
rows=[]; server=None; temp=None

def source_digest():
    import hashlib
    h=hashlib.sha256()
    for top in ['accounts','templates','wdos_project']:
        for path in sorted((APP/top).rglob('*')):
            if path.is_file() and path.suffix in {'.py','.js','.css','.html','.json'}:
                h.update(str(path.relative_to(APP)).encode());h.update(path.read_bytes())
    return h.hexdigest()

SOURCE_BEFORE=source_digest()

def layout_metrics(page):
    return page.evaluate("""() => {
      const base=document.querySelector('.auth-wrap').getBoundingClientRect();
      const selectors={title:'.auth-form h1',lede:'.auth-form>p:not([class])',primary:'.auth-form .btn.primary',notice:'.auth-form .notice',footer:'.smallprint'};
      return Object.fromEntries(Object.entries(selectors).map(([k,s])=>{
        const e=document.querySelector(s); if(!e)return [k,null];const r=e.getBoundingClientRect(),c=getComputedStyle(e);
        return [k,{x:r.x-base.x,y:r.y-base.y,width:r.width,height:r.height,font:c.fontSize,lineHeight:c.lineHeight}];
      }));
    }""")

def safe_text(s):
    s=re.sub(r'(?i)(password|secret|otp|recovery|code|token|proof)\s*[:=]?\s*[^\s,;]+', r'\1:[REDACTED]', str(s))
    return re.sub(r'\b\d{6,}\b','[REDACTED]',s)[:4000]

def record(name, status, detail='', **extra):
    rows.append({'scenario':name,'status':status,'detail':safe_text(detail),**extra})
    (OUT/'report.json').write_text(json.dumps({'candidate_source':str(APP),'base_url':BASE,'source_digest_before':SOURCE_BEFORE,'source_digest_current':source_digest(),'incomplete_coverage':['Reference pixel comparison is captured, not automatically scored; parent visual review required','Synthetic local journey fixtures; not production user data'],'scenarios':rows},indent=2), encoding='utf8')

def bootstrap():
    global temp
    temp=Path(tempfile.mkdtemp(prefix='wdos-nightwing-'))
    db=temp/'isolated.sqlite3'; mod=temp/'nightwing_settings.py'
    mod.write_text(f"""from wdos_project.settings import *\nDATABASES={{'default':{{'ENGINE':'django.db.backends.sqlite3','NAME':r'{db}'}}}}\nWDOS_PUBLIC_ORIGIN='{BASE}'\nWDOS_SECURE_COOKIES=False\nSESSION_COOKIE_SECURE=False\nCSRF_COOKIE_SECURE=False\nBREVO_API_KEY=''\nWDOS_EMAIL_FROM=''\nDEBUG=True\nALLOWED_HOSTS=['127.0.0.1','localhost']\n""",encoding='utf8')
    for k in ['DATABASE_URL','WDOS_BREVO_API_KEY','WDOS_EMAIL_FROM','BREVO_API_KEY','EMAIL_HOST','EMAIL_HOST_PASSWORD']:
        os.environ.pop(k,None)
    os.environ.update({'PYTHONPATH':str(temp)+os.pathsep+str(APP), 'DJANGO_SETTINGS_MODULE':'nightwing_settings','DJANGO_ALLOW_ASYNC_UNSAFE':'1','WDOS_PUBLIC_ORIGIN':BASE,'WDOS_SECURE_COOKIES':'0','WDOS_ENVIRONMENT':'','DJANGO_SECRET_KEY':secrets.token_urlsafe(40)})
    sys.path[:0]=[str(temp),str(APP)]
    import django; django.setup()
    from django.core.management import call_command
    call_command('migrate', verbosity=0, interactive=False)
    return db

def fixtures():
    from django.contrib.auth import get_user_model
    from accounts.models import Account
    User=get_user_model(); suffix=secrets.token_hex(5); pw='NW-'+secrets.token_urlsafe(18)+'!aA1'
    data={}
    labels=[('pending','pending',False),('active','active',False),('staff_mfa','active',True),('suspended','suspended',False)]
    labels += [(f'active_{lang}','active',False) for lang in LANGS if lang != 'en']
    labels += [(f'staff_mfa_{lang}','active',True) for lang in LANGS if lang != 'en']
    for label,status,staff in labels:
        email=f'nw-{label}-{suffix}@example.invalid'; u=User.objects.create_user(email=email,password=pw,username=email); u.is_staff=staff; u.save(update_fields=['is_staff'])
        a=Account.objects.create(user=u,email=email,display_name='NightWing Fixture',status=status,verified_at=None if status=='pending' else __import__('django').utils.timezone.now())
        data[label]=(a,email)
    return data,pw

def run_server():
    global server
    env=os.environ.copy(); env['DATABASE_URL']=''; env['WDOS_BREVO_API_KEY']=''; env['WDOS_EMAIL_FROM']=''; env['WDOS_PUBLIC_ORIGIN']=BASE; env['WDOS_SECURE_COOKIES']='0'; env['DJANGO_SETTINGS_MODULE']='nightwing_settings'; env['PYTHONPATH']=str(temp)+os.pathsep+str(APP)
    server=subprocess.Popen([sys.executable,'manage.py','runserver',f'127.0.0.1:{PORT}','--noreload','--insecure'],cwd=APP,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    import time, urllib.request
    for _ in range(60):
        try:
            urllib.request.urlopen(BASE+'/',timeout=1); return
        except Exception: time.sleep(.2)
    raise RuntimeError('isolated localhost server did not start')

def main():
    db=bootstrap(); run_server()
    qa_data, qa_pw = fixtures()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True, executable_path=CHROME)

        def visit(page, sid, route, suffix=''):
            if sid == 'AUTH-05':
                lang = suffix.split('lang=', 1)[1] if 'lang=' in suffix else 'en'
                account, email = qa_data.get('active_'+lang, qa_data['active'])
                page.goto(BASE+'/auth/login/'+suffix, wait_until='networkidle')
                page.locator('#id_email').fill(email); page.locator('#id_password').fill(qa_pw)
                page.locator('form.auth-live-form button[type=submit]').click()
                page.wait_for_load_state('networkidle')
            elif sid == 'AUTH-08':
                lang = suffix.split('lang=', 1)[1] if 'lang=' in suffix else 'en'
                account, email = qa_data.get('staff_mfa_'+lang, qa_data['staff_mfa'])
                page.goto(BASE+'/auth/login/'+suffix, wait_until='networkidle')
                page.locator('#id_email').fill(email); page.locator('#id_password').fill(qa_pw)
                page.locator('form.auth-live-form button[type=submit]').click()
                page.wait_for_load_state('networkidle')
            page.goto(BASE+route+suffix, wait_until='networkidle', timeout=25000)
            if sid in {'AUTH-05', 'AUTH-08'}:
                assert route in page.url and '/auth/login/' not in page.url, f'{sid} was not authenticated: {page.url}'

        # Public breadth, canonical captures, locales, controls and destinations.
        for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
            ctx=browser.new_context(viewport={'width':width,'height':height}); page=ctx.new_page(); page.set_default_timeout(9000)
            for sid,route in ROUTES.items():
                try:
                    visit(page, sid, route)
                    for sel in ['.setup-secret','.recovery-codes','[sensitive]']:
                        for loc in page.locator(sel).all(): loc.evaluate("e=>e.textContent='[REDACTED]'")
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'), 'horizontal overflow'
                    assert page.locator('select[name=lang]').count()==1
                    assert page.locator('footer a').count()==3
                    page.screenshot(path=str(OUT/f'{sid}-{label}.png'),full_page=True)
                    page.locator('.auth-wrap').screenshot(path=str(OUT/f'normalized-{sid}-{label}.png'))
                    links=page.locator('a').evaluate_all('(es)=>es.map(e=>({text:e.innerText,href:e.getAttribute("href")}))')
                    record(f'public:{sid}:{label}','pass',url=page.url,overflow=page.evaluate('document.documentElement.scrollWidth>innerWidth'),links=links,controls=page.locator('input,button,select').count(),layout=layout_metrics(page))
                except Exception as e: record(f'public:{sid}:{label}','fail',str(e))
            for lang in LANGS:
                try:
                    for sid,route in ROUTES.items():
                        visit(page, sid, route, '?lang='+lang)
                        assert page.locator('html').get_attribute('lang')==lang
                        assert page.locator('html').get_attribute('dir')==('rtl' if lang=='ar' else 'ltr')
                        assert page.locator('select[name=lang]').input_value()==lang
                        assert not page.evaluate('document.documentElement.scrollWidth>innerWidth'), 'horizontal overflow'
                    page.screenshot(path=str(OUT/f'locale-{lang}-{label}.png'),full_page=True)
                    record(f'locale:{lang}:{label}','pass',routes_checked=len(ROUTES),overflow=False)
                except Exception as e: record(f'locale:{lang}:{label}','fail',str(e))
            ctx.close()
        # Reference captures are exact v1 HTML, untouched.
        ref=ROOT/'docs'/'approved-ui'/'stage-02'
        for width,height,label in [(1440,1000,'desktop'),(390,844,'mobile')]:
            ctx=browser.new_context(viewport={'width':width,'height':height}); page=ctx.new_page()
            for sid in ROUTES:
                f=ref/f'{sid}-{label}.html'
                if f.exists():
                    try:
                        page.goto(f.as_uri());page.locator('.auth-wrap').screenshot(path=str(OUT/f'reference-{sid}-{label}.png'));record(f'reference:{sid}:{label}','pass',layout=layout_metrics(page))
                    except Exception as e: record(f'reference:{sid}:{label}','fail',str(e))
            ctx.close()
        refpage=browser.new_page(viewport={'width':1440,'height':1000})
        for sid in ROUTES:
            try:
                refpage.goto((ref/f'{sid}-states.html').as_uri())
                refpage.screenshot(path=str(OUT/f'reference-{sid}-states.png'),full_page=True)
                record(f'reference:{sid}:states','pass')
            except Exception as exc:record(f'reference:{sid}:states','fail',type(exc).__name__)
        refpage.close()
        import importlib.util
        spec=importlib.util.spec_from_file_location('core_qa',ROOT/'scripts/stage2_core_qa.py')
        assert spec is not None and spec.loader is not None
        core=importlib.util.module_from_spec(spec);spec.loader.exec_module(core)
        core.run(browser,BASE,OUT,record,fixtures)
        browser.close()
        record('source-stability','pass' if source_digest()==SOURCE_BEFORE else 'fail','candidate changed during QA' if source_digest()!=SOURCE_BEFORE else '')
    record('fixture-bootstrap','pass',database='disposable sqlite; credentials not retained')

def cleanup():
    global server,temp
    if server:
        try: server.terminate()
        except Exception: pass
        try: server.wait(timeout=5)
        except Exception: server.kill()
    if temp: shutil.rmtree(temp,ignore_errors=True)

if __name__=='__main__':
    try: main()
    except Exception as e: record('bootstrap','fail',str(e))
    finally: cleanup()
    print(json.dumps({'report':str(OUT/'report.json'),'scenarios':len(rows),'passed':sum(r['status']=='pass' for r in rows),'failed':sum(r['status']=='fail' for r in rows)}))
    raise SystemExit(1 if any(r['status']=='fail' for r in rows) else 0)
