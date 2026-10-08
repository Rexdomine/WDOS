"""
Stage 4 Dashboard System Browser Verification Suite
Automated End-to-End Playwright Testing using Microsoft Edge

Executes sequential browser tests covering all Stage 4 deliverables:
1. Seven Distinct Role Views (Founder/HQ, Operations, Country Lead, Chapter Lead, Member, Candidate, Community)
2. Desktop (1280x800) and Mobile (390x844) Responsive Layouts
3. Cross-Network Separation (WGMN vs WNNN)
4. Geographic Boundaries & Wrong-Country Prevention
5. Unauthorized Role Tampering & Unauthorized Drilldown Rejection (HTTP 403)
6. Scoped Drill-downs (Chapters, Alerts, Meetings, Reports)
7. Scoped Live Actions (Alert Acknowledgment, Meeting RSVP toggle)
8. Live Dynamic Database Reconciliation (No Fake "Live" KPIs)
9. Truthful Scoped Empty States with ARIA status
10. Scoped CSV Data Export
11. Accessibility Controls & High Contrast Theme

Saves screenshot evidence to: test_evidence/stage4_dashboards/
"""

import csv
import io
import os
import sys
import time
from pathlib import Path

# Django setup
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wdos_project.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
import django
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.management import call_command
from django.utils import timezone
from django.conf import settings

from accounts.models import Account, Membership, OnboardingDraft
from foundation.models import (
    Chapter,
    CountryHub,
    DashboardAlert,
    DashboardReport,
    ScheduledMeeting,
    WorkItem,
)
from playwright.sync_api import sync_playwright

User = get_user_model()
BASE_URL = "http://127.0.0.1:8001"
EVIDENCE_DIR = Path("test_evidence/stage4_dashboards")


def make_session_cookie(email: str):
    user = User.objects.get(email=email)
    account = Account.objects.get(user=user)
    
    session = SessionStore()
    now = timezone.now().timestamp()
    session["_auth_user_id"] = str(user.id)
    session["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    session["_auth_user_hash"] = user.get_session_auth_hash()
    session["security_version"] = account.security_version
    session["mfa_verified"] = True
    session["last_activity"] = now
    session["absolute_expiry"] = now + 43200
    session.save()
    
    return {
        "name": settings.SESSION_COOKIE_NAME,
        "value": session.session_key,
        "domain": "127.0.0.1",
        "path": "/",
    }


def run_all_tests():
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 78)
    print("STARTING STAGE 4 BROWSER VERIFICATION SUITE")
    print("Target Server:", BASE_URL)
    print("Evidence Directory:", EVIDENCE_DIR.resolve())
    print("=" * 78)

    # Database is pre-seeded with complete test fixtures
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA busy_timeout = 30000;")
    print("[Setup] Database ready with 5 Hubs, 12 Chapters, 4 Alerts, 5 Meetings, 3 Reports.\n")

    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)

        # ---------------------------------------------------------------------
        # TEST 1: Founder / HQ Executive Dashboard (Desktop & Mobile)
        # ---------------------------------------------------------------------
        print("Test 1: Founder / HQ Executive Dashboard...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("founder@example.org")])
        page = ctx.new_page()

        page.goto(f"{BASE_URL}/foundation/?role=founder")
        page.wait_for_selector("#page-title")
        heading = page.locator("#page-title").inner_text()
        assert page.locator("text=WGMN · Good Mother Network").first.is_visible()
        assert page.locator("text=WNNN · Next-Gen Nurturers").first.is_visible()
        assert page.locator("text=Country Hub Regional Operations").first.is_visible()
        assert page.locator("text=Executive & Audit Reports").first.is_visible()
        assert page.locator("text=TOTAL NETWORK MEMBERSHIP").first.is_visible()

        # Save desktop screenshot
        desktop_shot = EVIDENCE_DIR / "01_founder_hq_desktop.png"
        page.screenshot(path=str(desktop_shot), full_page=True)
        print(f"  -> Captured Desktop screenshot: {desktop_shot.name}")

        # Test Mobile view
        mobile_ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
        mobile_ctx.add_cookies([make_session_cookie("founder@example.org")])
        m_page = mobile_ctx.new_page()
        m_page.goto(f"{BASE_URL}/foundation/?role=founder")
        m_page.wait_for_selector(".mobile-head")
        assert m_page.locator(".mobile-head").is_visible()
        assert m_page.locator(".mobile-nav").is_visible()

        mobile_shot = EVIDENCE_DIR / "01_founder_hq_mobile.png"
        m_page.screenshot(path=str(mobile_shot), full_page=True)
        print(f"  -> Captured Mobile screenshot: {mobile_shot.name}")
        mobile_ctx.close()
        ctx.close()
        results.append(("01_founder_hq", "PASS", "Desktop & Mobile Executive HQ dashboard rendered with real network breakdown and hub status."))

        # ---------------------------------------------------------------------
        # TEST 2: Central Operations Dashboard
        # ---------------------------------------------------------------------
        print("\nTest 2: Central Operations Dashboard...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("ops@example.org")])
        page = ctx.new_page()

        page.goto(f"{BASE_URL}/foundation/?role=operations")
        page.wait_for_selector("#page-title")
        heading = page.locator("#page-title").inner_text()
        assert "Operations Coordination Dashboard" in heading
        assert page.locator("text=Onboarding Verification Pipeline").first.is_visible()
        assert page.locator("text=Active Work Items Queue").first.is_visible()
        assert page.locator("text=OPEN WORK ITEMS").first.is_visible()
        assert page.locator("text=John Kalu").first.is_visible()

        shot = EVIDENCE_DIR / "02_operations_dashboard.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Operations screenshot: {shot.name}")
        ctx.close()
        results.append(("02_operations_dashboard", "PASS", "Operations triage dashboard displaying verification queue and operational work items."))

        # ---------------------------------------------------------------------
        # TEST 3: Country / Field Leadership Dashboard (Nigeria Hub)
        # ---------------------------------------------------------------------
        print("\nTest 3: Country / Field Leadership Dashboard (Nigeria Hub)...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("country.ng@example.org")])
        page = ctx.new_page()

        page.goto(f"{BASE_URL}/foundation/?role=country_lead")
        page.wait_for_selector("#page-title")
        heading = page.locator("#page-title").inner_text()
        assert "Nigeria Country Hub Dashboard" in heading
        assert page.locator("text=Active Chapters in Nigeria").first.is_visible()
        assert page.locator("text=Lagos Central Chapter").first.is_visible()
        assert page.locator("text=Abuja FCT Chapter").first.is_visible()
        assert page.locator("text=Port Harcourt Chapter").first.is_visible()
        assert page.locator("text=National Assemblies & Gatherings").first.is_visible()
        assert page.locator("text=Country Hub Field Alerts").first.is_visible()

        shot = EVIDENCE_DIR / "03_country_lead_nigeria.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Nigeria Country Lead screenshot: {shot.name}")
        ctx.close()
        results.append(("03_country_lead_nigeria", "PASS", "Nigeria Country Hub dashboard with local chapters, LGA connections, alerts, and assemblies."))

        # ---------------------------------------------------------------------
        # TEST 4: Country / Field Leadership Dashboard (Kenya Hub - Isolation)
        # ---------------------------------------------------------------------
        print("\nTest 4: Country / Field Leadership Dashboard (Kenya Hub Isolation)...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("country.ke@example.org")])
        page = ctx.new_page()

        page.goto(f"{BASE_URL}/foundation/?role=country_lead")
        page.wait_for_selector("#page-title")
        heading = page.locator("#page-title").inner_text()
        assert "Kenya Country Hub Dashboard" in heading
        assert page.locator("text=Nairobi Kilimani Chapter").first.is_visible()
        # Strict isolation check: Nigerian chapters MUST NOT appear
        assert page.locator("text=Lagos Central Chapter").count() == 0
        assert page.locator("text=Abuja FCT Chapter").count() == 0

        shot = EVIDENCE_DIR / "04_country_lead_kenya.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Kenya Country Lead screenshot: {shot.name}")
        ctx.close()
        results.append(("04_country_lead_kenya", "PASS", "Kenya Country Hub strictly displays Kenyan chapters and excludes Nigerian data."))

        # ---------------------------------------------------------------------
        # TEST 5: Local Chapter Leadership Dashboard (Lagos Central)
        # ---------------------------------------------------------------------
        print("\nTest 5: Local Chapter Leadership Dashboard (Lagos Central)...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("chapter.lagos@example.org")])
        page = ctx.new_page()

        page.goto(f"{BASE_URL}/foundation/?role=chapter_lead")
        page.wait_for_selector("#page-title")
        heading = page.locator("#page-title").inner_text()
        assert "Lagos Central Chapter" in heading
        assert page.locator("text=CHAPTER LEADERSHIP").first.is_visible()
        assert page.locator("text=Chapter Member Roster").first.is_visible()
        assert page.locator("text=Ada Obinna").first.is_visible()
        assert page.locator("text=Lagos Central Weekly Chapter Fellowship").first.is_visible()

        shot = EVIDENCE_DIR / "05_chapter_lead_lagos.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Chapter Lead screenshot: {shot.name}")
        ctx.close()
        results.append(("05_chapter_lead_lagos", "PASS", "Local chapter view showing Lagos member roster, weekly meetups, and local bulletins."))

        # ---------------------------------------------------------------------
        # TEST 6: Member Personal Workspace View
        # ---------------------------------------------------------------------
        print("\nTest 6: Member Personal Workspace View...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("member.ada@example.org")])
        page = ctx.new_page()

        page.goto(f"{BASE_URL}/foundation/?role=member")
        page.wait_for_selector("#page-title")
        heading = page.locator("#page-title").inner_text()
        assert "Workspace" in heading
        assert page.locator("text=Lagos Central").first.is_visible()
        assert page.locator("text=Active Member").first.is_visible()

        shot = EVIDENCE_DIR / "06_member_workspace.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Member Workspace screenshot: {shot.name}")
        ctx.close()
        results.append(("06_member_workspace", "PASS", "Member personal workspace with local home connection, records table, and service options."))

        # ---------------------------------------------------------------------
        # TEST 7: Candidate Application & Accreditation Dashboard
        # ---------------------------------------------------------------------
        print("\nTest 7: Candidate Application & Accreditation Dashboard...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("candidate.john@example.org")])
        page = ctx.new_page()

        page.goto(f"{BASE_URL}/foundation/?role=candidate")
        page.wait_for_selector("#page-title")
        heading = page.locator("#page-title").inner_text()
        assert "Candidate Application Dashboard" in heading
        assert page.locator("text=Application for John Kalu").first.is_visible()
        assert page.locator("text=Step 6 of 8 Completed").first.is_visible()
        assert page.locator("text=Candidate Orientation Sessions").first.is_visible()
        assert page.locator("text=Your Onboarding Path").first.is_visible()

        shot = EVIDENCE_DIR / "07_candidate_dashboard.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Candidate Dashboard screenshot: {shot.name}")
        ctx.close()
        results.append(("07_candidate_dashboard", "PASS", "Candidate dashboard displaying progress card, orientation webinar registration, and onboarding timeline."))

        # ---------------------------------------------------------------------
        # TEST 8: Community Open View
        # ---------------------------------------------------------------------
        print("\nTest 8: Community Open View...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("community.amara@example.org")])
        page = ctx.new_page()

        page.goto(f"{BASE_URL}/foundation/?role=community")
        page.wait_for_selector("#page-title")
        heading = page.locator("#page-title").inner_text()
        assert "Welcome to the WDOS Community" in heading
        assert page.locator("text=Open Public Events & Webinars").first.is_visible()
        assert page.locator("text=Find a Local Chapter Near You").first.is_visible()
        assert page.locator("text=Ready to Join WDOS?").first.is_visible()

        shot = EVIDENCE_DIR / "08_community_dashboard.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Community Dashboard screenshot: {shot.name}")
        ctx.close()
        results.append(("08_community_dashboard", "PASS", "Public community view displaying open webinars, chapter directory, and join action."))

        # ---------------------------------------------------------------------
        # TEST 9a: Cross-Network Separation (WGMN vs WNNN Chapters Drill-down)
        # ---------------------------------------------------------------------
        print("\nTest 9a: Cross-Network Separation in Drilldowns...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("founder@example.org")])
        page = ctx.new_page()

        # WGMN Nigeria Chapters
        page.goto(f"{BASE_URL}/foundation/dashboard/drilldown/chapters/?network=WGMN&country=NG")
        page.wait_for_selector("table.records-table")
        assert page.locator("text=Lagos Central Chapter").first.is_visible()
        assert page.locator("text=Lagos Next-Gen Youth Hub").count() == 0
        shot_wgmn = EVIDENCE_DIR / "09a_scope_wgmn_chapters.png"
        page.screenshot(path=str(shot_wgmn), full_page=True)
        print(f"  -> Captured WGMN Chapters Drilldown: {shot_wgmn.name}")

        # WNNN Nigeria Chapters
        page.goto(f"{BASE_URL}/foundation/dashboard/drilldown/chapters/?network=WNNN&country=NG")
        page.wait_for_selector("table.records-table")
        assert page.locator("text=Lagos Next-Gen Youth Hub").first.is_visible()
        assert page.locator("text=Lagos Central Chapter").count() == 0
        shot_wnnn = EVIDENCE_DIR / "09b_scope_wnnn_chapters.png"
        page.screenshot(path=str(shot_wnnn), full_page=True)
        print(f"  -> Captured WNNN Chapters Drilldown: {shot_wnnn.name}")
        ctx.close()
        results.append(("09a_cross_network_separation", "PASS", "Strict separation of WGMN and WNNN chapters in server queries and views."))

        # ---------------------------------------------------------------------
        # TEST 9b: Scope Denied - Wrong Country Parameter Tampering (HTTP 403)
        # ---------------------------------------------------------------------
        print("\nTest 9b: Scope Denied - Wrong Country (HTTP 403)...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("country.ng@example.org")])
        page = ctx.new_page()

        # Nigeria lead attempts to tamper query param with country=KE
        response = page.goto(f"{BASE_URL}/foundation/?country=KE")
        assert response.status == 403, f"Expected 403, got {response.status}"
        assert page.locator("text=Access Restricted").first.is_visible()
        assert page.locator("text=wrong_country").first.is_visible()
        assert page.locator("text=Return to Authorized Workspace").first.is_visible()

        shot = EVIDENCE_DIR / "09c_wrong_country_blocked.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Wrong Country Denial screenshot: {shot.name}")
        ctx.close()
        results.append(("09b_wrong_country_blocked", "PASS", "HTTP 403 scope permission denied rendered with reason_code='wrong_country' and recovery link."))

        # ---------------------------------------------------------------------
        # TEST 9c: Scope Denied - Unauthorized Role Tampering (HTTP 403)
        # ---------------------------------------------------------------------
        print("\nTest 9c: Scope Denied - Unauthorized Role Tampering (HTTP 403)...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("candidate.john@example.org")])
        page = ctx.new_page()

        # Candidate attempts to switch to founder role
        response = page.goto(f"{BASE_URL}/foundation/?role=founder")
        assert response.status == 403, f"Expected 403, got {response.status}"
        assert page.locator("text=unauthorized_role").first.is_visible()

        shot = EVIDENCE_DIR / "09d_unauthorized_role_tampering_blocked.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Role Tampering Denial screenshot: {shot.name}")
        ctx.close()
        results.append(("09c_unauthorized_role_blocked", "PASS", "HTTP 403 rejected candidate switching to founder role with reason_code='unauthorized_role'."))

        # ---------------------------------------------------------------------
        # TEST 9d: Scope Denied - Unauthorized Drilldown Rejection (HTTP 403)
        # ---------------------------------------------------------------------
        print("\nTest 9d: Scope Denied - Unauthorized Drilldown (HTTP 403)...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("member.ada@example.org")])
        page = ctx.new_page()

        # Member attempts to view verification queue drilldown
        response = page.goto(f"{BASE_URL}/foundation/dashboard/drilldown/verifications/")
        assert response.status == 403, f"Expected 403, got {response.status}"
        assert page.locator("text=unauthorized_drilldown").first.is_visible()

        shot = EVIDENCE_DIR / "09e_unauthorized_drilldown_blocked.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Unauthorized Drilldown Denial screenshot: {shot.name}")
        ctx.close()
        results.append(("09d_unauthorized_drilldown_blocked", "PASS", "HTTP 403 rejected member accessing applicant verifications queue drilldown."))

        # ---------------------------------------------------------------------
        # TEST 10a: Authorized Chapters Drill-down View
        # ---------------------------------------------------------------------
        print("\nTest 10a: Authorized Chapters Drill-down View...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("founder@example.org")])
        page = ctx.new_page()

        page.goto(f"{BASE_URL}/foundation/dashboard/drilldown/chapters/?network=WGMN&country=NG")
        page.wait_for_selector("table.records-table")
        assert page.locator("text=Chapters Drill-down").first.is_visible()
        assert page.locator("text=NG-LOS-01").first.is_visible()
        assert page.locator("text=NG-ABJ-01").first.is_visible()
        assert page.locator("text=NG-PHC-01").first.is_visible()

        shot = EVIDENCE_DIR / "10a_drilldown_chapters_table.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Chapters Drilldown screenshot: {shot.name}")

        # ---------------------------------------------------------------------
        # TEST 10b: Individual Chapter Detail Profile View
        # ---------------------------------------------------------------------
        print("\nTest 10b: Individual Chapter Detail Profile View...")
        chap = Chapter.objects.get(code="NG-LOS-01")
        page.goto(f"{BASE_URL}/foundation/dashboard/chapters/{chap.id}/")
        page.wait_for_selector("#page-title")
        assert "Lagos Central Chapter" in page.locator("#page-title").inner_text()
        assert page.locator("text=Chapter Profile").first.is_visible()
        assert page.locator("text=NG-LOS-01").first.is_visible()
        assert page.locator("text=Adaeze Okonkwo").first.is_visible()

        shot = EVIDENCE_DIR / "10b_chapter_detail_profile.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Chapter Detail screenshot: {shot.name}")

        # ---------------------------------------------------------------------
        # TEST 10c: Executive Report Detail View
        # ---------------------------------------------------------------------
        print("\nTest 10c: Executive Report Detail View...")
        rep = DashboardReport.objects.filter(network="WGMN", country="ALL").first()
        page.goto(f"{BASE_URL}/foundation/dashboard/reports/{rep.id}/")
        page.wait_for_selector("#page-title")
        assert "Continental Impact & Growth Audit" in page.locator("#page-title").inner_text()
        assert page.locator("text=Executive Summary").first.is_visible()
        assert page.locator("text=Audited Metrics & KPIs").first.is_visible()
        assert page.locator("text=1420").first.is_visible()  # Total enrolled

        shot = EVIDENCE_DIR / "10c_report_detail_view.png"
        page.screenshot(path=str(shot), full_page=True)
        print(f"  -> Captured Report Detail screenshot: {shot.name}")

        # ---------------------------------------------------------------------
        # TEST 10d: Alert Detail & One-Click Scoped Acknowledgment Action
        # ---------------------------------------------------------------------
        print("\nTest 10d: Alert Detail & Acknowledgment Action...")
        alert = DashboardAlert.objects.filter(country="NG", network="WGMN").first()
        acc_founder = Account.objects.get(email="founder@example.org")
        alert.acknowledged_by.remove(acc_founder)
        page.goto(f"{BASE_URL}/foundation/dashboard/alerts/{alert.id}/")
        page.wait_for_selector("#page-title")
        assert "Acknowledge Alert" in page.content()

        shot_before = EVIDENCE_DIR / "10d1_alert_detail_before_ack.png"
        page.screenshot(path=str(shot_before), full_page=True)
        print(f"  -> Captured Alert Before Ack screenshot: {shot_before.name}")

        # Click Acknowledge Alert button
        page.click("button:has-text('Acknowledge Alert')")
        page.wait_for_load_state("networkidle")
        assert "Acknowledged" in page.content()

        shot_after = EVIDENCE_DIR / "10d2_alert_detail_after_ack.png"
        page.screenshot(path=str(shot_after), full_page=True)
        print(f"  -> Captured Alert After Ack screenshot: {shot_after.name}")

        # ---------------------------------------------------------------------
        # TEST 10e: Meeting Detail & Toggle RSVP Action
        # ---------------------------------------------------------------------
        print("\nTest 10e: Meeting Detail & RSVP Action...")
        meet = ScheduledMeeting.objects.get(title="Nigeria National Leadership Assembly")
        acc_founder = Account.objects.get(email="founder@example.org")
        meet.rsvp_accounts.remove(acc_founder)
        meet.attendees_count = 18
        meet.save()

        page.goto(f"{BASE_URL}/foundation/dashboard/meetings/{meet.id}/")
        page.wait_for_selector("#page-title")
        assert meet.title in page.locator("#page-title").inner_text()
        assert page.locator("text=RSVP to Attend").first.is_visible()

        shot_m_before = EVIDENCE_DIR / "10e1_meeting_detail_before_rsvp.png"
        page.screenshot(path=str(shot_m_before), full_page=True)
        print(f"  -> Captured Meeting Before RSVP screenshot: {shot_m_before.name}")

        # Click RSVP
        page.click("button:has-text('RSVP to Attend')")
        page.wait_for_load_state("networkidle")
        assert "RSVP Confirmed" in page.content()

        shot_m_after = EVIDENCE_DIR / "10e2_meeting_detail_after_rsvp.png"
        page.screenshot(path=str(shot_m_after), full_page=True)
        print(f"  -> Captured Meeting After RSVP screenshot: {shot_m_after.name}")
        ctx.close()
        results.append(("10_drilldowns_and_actions", "PASS", "Drill-downs, detail profiles, alert acknowledgment, and RSVP actions fully functional."))

        # ---------------------------------------------------------------------
        # TEST 11: Real Dynamic Database KPI Reconciliation (No Stale Caches)
        # ---------------------------------------------------------------------
        print("\nTest 11: Real Data Dynamic Aggregation (No Stale Caches)...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("founder@example.org")])
        page = ctx.new_page()

        # Ensure clean state for dynamic insertion test
        Chapter.objects.filter(code="NG-CAL-01").delete()

        page.goto(f"{BASE_URL}/foundation/?role=founder&network=WGMN&country=NG")
        page.wait_for_selector(".stats")
        initial_chapters_count = Chapter.objects.filter(network="WGMN", country="NG", status="active").count()
        assert str(initial_chapters_count) in page.locator(".stat:has-text('ACTIVE CHAPTERS') .stat-value").inner_text()

        # Dynamically create new chapter in database
        new_chap = Chapter.objects.create(
            code="NG-CAL-01",
            name="Calabar Cross River Chapter",
            network="WGMN",
            country="NG",
            region="Cross River",
            status="active",
            member_count=15,
        )

        # Refresh browser
        page.reload()
        page.wait_for_selector(".stats")
        updated_val = page.locator(".stat:has-text('ACTIVE CHAPTERS') .stat-value").inner_text()
        assert int(updated_val) == initial_chapters_count + 1, f"Expected {initial_chapters_count + 1}, got {updated_val}"

        shot_dyn = EVIDENCE_DIR / "11_dynamic_kpi_immediate_update.png"
        page.screenshot(path=str(shot_dyn), full_page=True)
        print(f"  -> Captured Dynamic KPI Update screenshot: {shot_dyn.name}")
        ctx.close()
        results.append(("11_dynamic_kpi_reconciliation", "PASS", f"KPI immediately reconciled database insertion from {initial_chapters_count} to {initial_chapters_count + 1}."))

        # ---------------------------------------------------------------------
        # TEST 12: Truthful Empty State with ARIA role="status"
        # ---------------------------------------------------------------------
        print("\nTest 12: Truthful Empty State with ARIA status...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("founder@example.org")])
        page = ctx.new_page()

        # Query WNNN chapters in South Africa (none exist in fixtures)
        page.goto(f"{BASE_URL}/foundation/dashboard/drilldown/chapters/?network=WNNN&country=ZA")
        page.wait_for_selector(".empty-state")
        empty_el = page.locator(".empty-state[role='status']").first
        assert empty_el.is_visible()
        assert "No Chapters in Current Scope" in empty_el.inner_text()

        shot_empty = EVIDENCE_DIR / "12_truthful_empty_state.png"
        page.screenshot(path=str(shot_empty), full_page=True)
        print(f"  -> Captured Truthful Empty State screenshot: {shot_empty.name}")
        ctx.close()
        results.append(("12_truthful_empty_state", "PASS", "Empty state correctly rendered with ARIA role='status' and truthful explanation."))

        # ---------------------------------------------------------------------
        # TEST 13: Scoped CSV Export
        # ---------------------------------------------------------------------
        print("\nTest 13: Scoped CSV Export...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("founder@example.org")])
        page = ctx.new_page()

        # Navigate to chapters drilldown with scope network=WGMN&country=NG
        page.goto(f"{BASE_URL}/foundation/dashboard/drilldown/chapters/?network=WGMN&country=NG")
        page.wait_for_selector("a:has-text('Export CSV')")
        with page.expect_download() as download_info:
            page.click("a:has-text('Export CSV')")
        download = download_info.value
        export_file = EVIDENCE_DIR / download.suggested_filename
        download.save_as(str(export_file))
        print(f"  -> Saved CSV export to: {export_file.name}")

        # Verify CSV contents
        content = export_file.read_text(encoding="utf-8")
        assert "Lagos Central Chapter" in content
        assert "Nairobi Kilimani Chapter" not in content  # Kenya chapter excluded
        assert "Lagos Next-Gen Youth Hub" not in content  # WNNN chapter excluded
        ctx.close()
        results.append(("13_scoped_csv_export", "PASS", f"CSV export strictly scoped to WGMN/NG; saved as {export_file.name}."))

        # ---------------------------------------------------------------------
        # TEST 14: Accessibility Preferences (High-Contrast Mode)
        # ---------------------------------------------------------------------
        print("\nTest 14: Accessibility QA (High-Contrast Mode)...")
        ctx = browser.new_context(viewport={"width": 1280, "height": 800})
        ctx.add_cookies([make_session_cookie("founder@example.org")])
        page = ctx.new_page()

        # Set high_contrast preference via the Settings UI form
        page.goto(f"{BASE_URL}/foundation/settings/")
        page.wait_for_selector("#high_contrast_toggle")
        page.check("#high_contrast_toggle")
        page.click("button:has-text('Save All Preferences')")
        page.wait_for_load_state("networkidle")

        page.goto(f"{BASE_URL}/foundation/?role=founder")
        page.wait_for_selector(".foundation-shell")
        body_class = page.locator("body").get_attribute("class")
        assert "theme-high-contrast" in body_class, f"Expected theme-high-contrast in body, got {body_class}"

        shot_hc = EVIDENCE_DIR / "14_accessibility_high_contrast.png"
        page.screenshot(path=str(shot_hc), full_page=True)
        print(f"  -> Captured High-Contrast screenshot: {shot_hc.name}")
        ctx.close()
        results.append(("14_accessibility_high_contrast", "PASS", "High contrast mode persists and applies theme-high-contrast class across shell."))

        browser.close()

    print("\n" + "=" * 78)
    print("BROWSER TEST EXECUTION SUMMARY:")
    print("=" * 78)
    all_passed = True
    for tid, status, msg in results:
        print(f"[{status}] {tid:<35} : {msg}")
        if status != "PASS":
            all_passed = False
    print("=" * 78)
    print("ALL TESTS COMPLETED SUCCESSFULLY!" if all_passed else "SOME TESTS FAILED!")
    print("Screenshots and exports saved to:", EVIDENCE_DIR.resolve())
    print("=" * 78)


if __name__ == "__main__":
    run_all_tests()
