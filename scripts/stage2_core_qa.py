"""Independent synthetic journey assertions; imported by browser audit only."""
from datetime import timedelta
from pathlib import Path
import secrets,uuid
import pyotp
from django.utils import timezone
from django.contrib.sessions.models import Session
from accounts import services
from accounts.models import Account,Person,Invitation,RecoveryCode


def run(browser,base,out,record,fixtures):
    def context(width):
        c=browser.new_context(viewport={'width':width,'height':1000 if width>600 else 844})
        p=c.new_page();p.set_default_timeout(7000);return c,p
    def submit(p):
        p.locator('form.auth-live-form button[type=submit]:not([name=begin])').last.click()
        p.wait_for_load_state('networkidle')
    def login(p,email,pw):
        p.goto(base+'/auth/login/');p.locator('#id_email').fill(email);p.locator('#id_password').fill(pw);submit(p)
    def capture(p,name):
        assert not p.evaluate('document.documentElement.scrollWidth>innerWidth'), 'horizontal overflow'
        sensitive=p.locator('.setup-secret code,.recovery-codes,input[name=code],input[name=proof],input[type=password]')
        p.screenshot(path=str(out/(name+'.png')),full_page=True,mask=[sensitive])
        return {'url':p.url.split('#')[0],'heading':p.locator('main h1').inner_text(),'screenshot':name+'.png','overflow':False}
    def case(name,fn):
        try:
            detail=fn() or {};record(name,'pass',**detail)
        except Exception as exc:
            import traceback
            trace=[f for f in traceback.extract_tb(exc.__traceback__) if f.filename==__file__]
            record(name,'fail',type(exc).__name__+' at QA line '+str(trace[-1].lineno if trace else 0))
    for width,label in [(1440,'desktop'),(390,'mobile')]:
        data,pw=fixtures();pending,pemail=data['pending'];active,aemail=data['active'];staff,semail=data['staff_mfa'];suspended,xemail=data['suspended']
        c,p=context(width)
        def password_and_loading():
            token,proof=services.issue_token(active,'reset')
            p.goto(base+'/auth/reset/#'+str(token.pk)+'.'+proof);p.wait_for_url(lambda url: '#' not in url)
            first=p.locator('#id_password');second=p.locator('#id_confirm')
            assert first.get_attribute('type')=='password' and second.get_attribute('type')=='password'
            toggle=p.locator('button[data-target="id_password"]');toggle.focus();toggle.press('Space')
            assert first.get_attribute('type')=='text' and second.get_attribute('type')=='password'
            assert toggle.get_attribute('aria-pressed')=='true'
            assert first.evaluate('e=>e===document.activeElement')
            toggle.focus();toggle.press('Space');assert first.get_attribute('type')=='password'
            p.goto(base+'/auth/login/?lang=fr');p.locator('#id_email').fill('loading@example.invalid');p.locator('#id_password').fill(pw)
            # Exercise actual click/submit listeners without navigation hiding the transient status.
            p.locator('form.auth-live-form').evaluate("f=>f.addEventListener('submit',e=>e.preventDefault(),{once:true})")
            button=p.locator('form.auth-live-form button[type=submit]');button.click()
            p.wait_for_function("document.querySelector('.submit-status').textContent.trim().length > 0")
            assert p.locator('.submit-status').inner_text().strip()
            assert 'Working' not in p.locator('.submit-status').inner_text()
            return {'password_mask_default':True,'independent_controls':True,'keyboard_focus':True,'localized_loading':True,'loading_check':'actual submit event with test-only navigation prevention'}
        case('controls:password-loading:'+label,password_and_loading);c.close()
        c,p=context(width)
        def pending_verify():
            login(p,pemail,pw)
            assert '/auth/status/' in p.url
            capture(p,'pending-'+label)
            link=p.locator('main a[href="/auth/verify/"]').first;assert link.is_visible();link.click()
            assert p.locator('#id_email').count()==0, 'known contact should not need email re-entry'
            assert pemail not in p.locator('main').inner_text(), 'unmasked destination'
            assert '***@' in p.locator('.destination strong').inner_text(), 'missing masked contact context'
            capture(p,'verify-bound-'+label)
            token,otp=services.issue_token(pending,'verify');p.locator('#id_code').fill(otp);submit(p)
            pending.refresh_from_db();assert pending.status=='active'
            assert p.locator('#id_code').count()==0,'stale verification form after success'
            return capture(p,'verify-success-'+label)
        case('journey:pending-verify:'+label,pending_verify);c.close()
        c,p=context(width)
        def linked_invitation():
            login(p,aemail,pw);p.goto(base+'/auth/invitation/')
            names=p.locator('form.auth-live-form input:not([type=hidden])').evaluate_all('(els)=>els.map(x=>x.name)');assert names[:2]==['code','email']
            capture(p,'invitation-'+label)
            person=Person.objects.create(display_name='Synthetic linked person');code=secrets.token_urlsafe(20)
            Invitation.objects.create(person=person,email=aemail,digest=services.digest(code),expires_at=timezone.now()+timedelta(hours=1))
            p.locator('#id_code').fill(code);p.locator('#id_email').fill(aemail);submit(p)
            active.refresh_from_db();assert active.person_id==person.pk
            assert p.locator('#id_code').count()==0
            capture(p,'invitation-success-'+label);p.goto(base+'/auth/status/')
            assert p.locator('main a[href="/auth/invitation/"]').count()==0,'already linked account offered claim'
            return capture(p,'linked-status-'+label)
        case('journey:invitation-linked:'+label,linked_invitation);c.close()
        c,p=context(width)
        def missing_reset():
            p.goto(base+'/auth/reset/?lang=fr');assert not p.locator('#id_password').is_visible()
            assert p.locator('main a[href="/auth/recover/"]').first.is_visible()
            assert 'Proof:' not in p.locator('main').inner_text()
            return capture(p,'reset-missing-fr-'+label)
        case('journey:reset-missing:'+label,missing_reset);c.close()
        c,p=context(width)
        def invalid_reset():
            p.goto(base+'/auth/reset/#'+str(uuid.uuid4())+'.'+secrets.token_urlsafe(32))
            p.wait_for_url(lambda url: '#' not in url)
            if p.locator('#id_password').is_visible():
                np='NW-'+secrets.token_urlsafe(18)+'!aA1';p.locator('#id_password').fill(np);p.locator('#id_confirm').fill(np);submit(p)
            assert not p.locator('#id_password').is_visible()
            assert p.locator('main a[href="/auth/recover/"]').first.is_visible()
            return capture(p,'reset-invalid-'+label)
        case('journey:reset-invalid:'+label,invalid_reset);c.close()
        c,p=context(width)
        def reset_success_replay():
            token,proof=services.issue_token(active,'reset');fragment=str(token.pk)+'.'+proof
            p.goto(base+'/auth/reset/#'+fragment);p.wait_for_url(lambda url: '#' not in url)
            assert p.locator('#id_password').is_visible(),'valid fragment incorrectly hidden'
            capture(p,'reset-valid-'+label)
            np='NW-'+secrets.token_urlsafe(18)+'!aA1';p.locator('#id_password').fill(np);p.locator('#id_confirm').fill(np);submit(p)
            active.user.refresh_from_db();assert active.user.check_password(np)
            assert p.locator('#id_password').count()==0
            capture(p,'reset-success-'+label)
            p.goto(base+'/');p.goto(base+'/auth/reset/#'+fragment);p.wait_for_url(lambda url: '#' not in url)
            assert not p.locator('#id_password').is_visible()
            assert p.locator('main a[href="/auth/recover/"]').first.is_visible()
            active.user.refresh_from_db();assert active.user.check_password(np),'one-use proof was replayable'
            return capture(p,'reset-used-'+label)
        case('journey:reset-valid-used:'+label,reset_success_replay);c.close()
        c,p=context(width)
        def suspended_page():
            login(p,xemail,pw);assert '/auth/status/' in p.url
            assert p.locator('main a[href*="help"],main a[href*="review"]').count()>0
            assert p.locator('main a[href="/auth/verify/"]').count()==0
            return capture(p,'suspended-'+label)
        case('journey:suspended:'+label,suspended_page);c.close()
        c,p=context(width);recovery=[]
        def mfa_enrollment():
            login(p,semail,pw);assert '/auth/mfa/' in p.url
            assert not p.locator('#id_code').is_visible(),'MFA code competes with begin setup'
            capture(p,'mfa-begin-'+label);p.locator('form.mfa-begin button[type=submit]').click();p.wait_for_load_state('networkidle')
            secret=p.locator('.setup-secret code').inner_text()
            assert p.locator('.setup-secret').bounding_box()['y'] < p.locator('#id_code').bounding_box()['y']
            capture(p,'mfa-secret-'+label)
            p.locator('#id_code').fill(pyotp.TOTP(secret).now());submit(p)
            recovery.extend(p.locator('.recovery-codes code').all_text_contents());assert recovery
            staff.refresh_from_db();assert staff.mfa_secret
            return capture(p,'mfa-recovery-save-'+label)
        case('journey:mfa-enrollment:'+label,mfa_enrollment);c.close()
        c,p=context(width)
        def recovery_login():
            assert recovery,'enrollment prerequisite failed'
            login(p,semail,pw);assert '/auth/mfa/' in p.url
            assert p.locator('main a[href*="help"]').count()>0,'no actionable lost-factor support'
            capture(p,'mfa-challenge-'+label)
            p.locator('#id_code').fill(recovery[0]);submit(p)
            assert '/auth/status/' in p.url
            assert RecoveryCode.objects.get(account=staff,digest=services.digest(recovery[0])).used_at
            capture(p,'mfa-recovered-'+label)
            sessionid=next(x['value'] for x in c.cookies() if x['name']=='sessionid')
            Session.objects.filter(session_key=sessionid).update(expire_date=timezone.now()-timedelta(seconds=1))
            p.goto(base+'/auth/status/');assert p.locator('main a[href="/auth/login/"]').count()>0
            return capture(p,'expired-'+label)
        case('journey:mfa-recovery-expiry:'+label,recovery_login);c.close()
        c,p=context(width)
        def recovery_replay():
            assert recovery,'enrollment prerequisite failed'
            login(p,semail,pw);p.locator('#id_code').fill(recovery[0]);submit(p)
            assert '/auth/mfa/' in p.url
            assert p.locator('.error-summary').is_visible()
            return capture(p,'mfa-recovery-used-'+label)
        case('journey:mfa-recovery-one-use:'+label,recovery_replay);c.close()
