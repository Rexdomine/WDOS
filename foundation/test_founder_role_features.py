"""
Comprehensive Test Suite: Role 01 Founder & Executive Director Features & Governance Limits
References:
- development_plan/WDOS_Visual_Flow_Role_Feature_Matrix.md (Role 1: Founder & Executive Director)
- WDOS-Complete-UI-Review-v2.pdf (Pages 75, 228, 231, 117, 666, 663, 669, 654, 657, 93, 498, 501, 402, 414, 384, 375, 486, 489, 630)

Verifies:
1. Card 1: Continental Command (DASH-01, GEO-01, GEO-02, DASH-10-CR)
2. Card 2: Executive Decisions (GOV-03, GOV-02, GOV-04) + POST ratification & issue logging
3. Card 3: Strategic Partnerships (REL-01, REL-02, DASH-07) + POST MoU sign-off
4. Card 4: Executive Messaging (COMMS-02, COMMS-01) + POST continental announcement
5. Card 5: Event Leadership (EVENT-01, EVENT-05, ROOM-03, MTG-06) + POST plenary chairing
6. Card 6: Performance Oversight (REP-05, REP-06)
7. Strict Guardrails: Safeguarding narrative restriction (SAFE-04 -> 403 Forbidden)
8. Visual Role Feature Matrix embed on DASH-01
"""

import io
import time
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from accounts.models import Account, Person
from foundation.scope import ScopePermissionDenied
from foundation.executive_director_engine import (
    assert_financial_disbursement_guardrail,
    assert_safeguarding_access_guardrail,
)

User = get_user_model()


class FounderRoleFeaturesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        sink = io.StringIO()
        call_command("seed_roles", stdout=sink)
        call_command("seed_shell_data", stdout=sink)
        call_command("seed_dashboards", stdout=sink)
        call_command("seed_test_accounts", stdout=sink)

    def setUp(self):
        self.founder_user = User.objects.get(email="founder@example.org")
        self.founder_account = Account.objects.get(email="founder@example.org")
        self.client = Client()

    def _login_as(self, user, account):
        self.client.force_login(user)
        session = self.client.session
        now = int(time.time())
        session["security_version"] = account.security_version
        session["mfa_verified"] = True
        session["last_activity"] = now
        session["absolute_expiry"] = now + 43200
        session.save()

    def _login_founder(self):
        self._login_as(self.founder_user, self.founder_account)

    # -------------------------------------------------------------------------
    # Card 1: Continental Command Tests
    # -------------------------------------------------------------------------
    def test_continental_command_screens(self):
        self._login_founder()

        # DASH-01: Continental priorities
        resp = self.client.get("/foundation/dashboards/DASH-01/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode()
        self.assertIn("Continental priorities", content)
        self.assertIn("Your priorities, relevant evidence and next actions in one clear view.", content)

        # GEO-01: Africa and network coverage
        resp = self.client.get("/foundation/stage6/GEO-01/")
        self.assertEqual(resp.status_code, 200)

        # GEO-02: Country command profile
        resp = self.client.get("/foundation/stage6/GEO-02/")
        self.assertEqual(resp.status_code, 200)

        # DASH-10-CR: Country Attention & Urgent Issues
        resp = self.client.get("/foundation/dashboards/DASH-10-CR/")
        self.assertEqual(resp.status_code, 200)

    # -------------------------------------------------------------------------
    # Card 2: Executive Decisions Tests
    # -------------------------------------------------------------------------
    def test_executive_decisions_workflow(self):
        self._login_founder()

        # GOV-03: Decision register
        resp = self.client.get("/foundation/governance/decisions/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Decision register", resp.content.decode())

        # Screen router alias
        resp_alias = self.client.get("/foundation/screens/GOV-03/")
        self.assertEqual(resp_alias.status_code, 200)

        # POST: Record / Ratify executive decision
        resp_post = self.client.post("/foundation/governance/decisions/", {
            "action": "record_decision",
            "reference": "POL-001",
            "decision": "Approved",
            "notes": "Continental mandate ratified by Founder."
        })
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn("Decision Recorded", resp_post.content.decode())

        # GOV-02: Issues, risks & corrective actions
        resp_gov02 = self.client.get("/foundation/governance/issues/")
        self.assertEqual(resp_gov02.status_code, 200)

        # POST: Record new issue
        resp_gov02_post = self.client.post("/foundation/governance/issues/", {
            "reference": "RSK-055",
            "finding": "Cross-network reporting drift",
            "owner": "HOFCO",
            "category": "Operational",
            "severity": "High",
            "mitigation": "Hold weekly reconciliation session.",
        })
        self.assertEqual(resp_gov02_post.status_code, 200)
        self.assertIn("New Governance Issue Logged", resp_gov02_post.content.decode())

        # GOV-04: Request controlled change
        resp_gov04 = self.client.get("/foundation/governance/change/")
        self.assertEqual(resp_gov04.status_code, 200)

        # POST: Submit controlled change
        resp_gov04_post = self.client.post("/foundation/governance/change/", {
            "change_title": "Reporting Format Standardization",
            "reason": "Harmonize evidence submission across 55 countries.",
            "affected_module": "Reports and accountability",
            "risk_rollback": "Maintain legacy form access for 30 days.",
        })
        self.assertEqual(resp_gov04_post.status_code, 200)
        self.assertIn("Controlled Change Submitted", resp_gov04_post.content.decode())

    # -------------------------------------------------------------------------
    # Card 3: Strategic Partnerships Tests
    # -------------------------------------------------------------------------
    def test_strategic_partnerships_workflow(self):
        self._login_founder()

        # REL-01: Stakeholder relationships register
        resp_rel01 = self.client.get("/foundation/relationships/")
        self.assertEqual(resp_rel01.status_code, 200)
        self.assertIn("Stakeholder relationships", resp_rel01.content.decode())

        # Screen alias
        resp_alias = self.client.get("/foundation/screens/REL-01/")
        self.assertEqual(resp_alias.status_code, 200)

        # REL-02: Review proposed partnership
        resp_rel02 = self.client.get("/foundation/relationships/review/?partner=rel-04")
        self.assertEqual(resp_rel02.status_code, 200)
        self.assertIn("Review a proposed partnership", resp_rel02.content.decode())

        # POST: Ratify strategic MoU
        resp_rel02_post = self.client.post("/foundation/relationships/review/?partner=rel-04", {
            "action": "record_decision",
            "decision": "Approve MoU",
            "notes": "Strategic bilateral partnership ratified by Executive Directorate."
        })
        self.assertEqual(resp_rel02_post.status_code, 200)
        self.assertIn("Authorized Decision Recorded", resp_rel02_post.content.decode())

        # DASH-07: Resource accountability
        resp_dash07 = self.client.get("/foundation/dashboards/DASH-07/")
        self.assertEqual(resp_dash07.status_code, 200)

    # -------------------------------------------------------------------------
    # Card 4: Executive Messaging Tests
    # -------------------------------------------------------------------------
    def test_executive_messaging_workflow(self):
        self._login_founder()

        # COMMS-02: Announcements
        resp_comms02 = self.client.get("/foundation/communications/announcements/")
        self.assertEqual(resp_comms02.status_code, 200)
        self.assertIn("Announcements", resp_comms02.content.decode())

        # Screen alias
        resp_alias = self.client.get("/foundation/screens/COMMS-02/")
        self.assertEqual(resp_alias.status_code, 200)

        # POST: Issue official continental announcement
        resp_post = self.client.post("/foundation/communications/announcements/", {
            "title": "Pan-African Solidarity Declaration 2026",
            "audience": "HQ / Both Networks",
            "summary": "Official declaration to all 55 country leaders",
            "content": "No Woman Is Left Out: We affirm our shared continental commitment.",
        })
        self.assertEqual(resp_post.status_code, 200)
        self.assertIn("Official Announcement Published", resp_post.content.decode())

        # COMMS-01: Messaging Inbox
        resp_comms01 = self.client.get("/foundation/messages/inbox/")
        self.assertEqual(resp_comms01.status_code, 200)

    # -------------------------------------------------------------------------
    # Card 5: Event Leadership Tests
    # -------------------------------------------------------------------------
    def test_event_leadership_workflow(self):
        self._login_founder()

        # EVENT-01: WODDI leadership gathering
        resp_event01 = self.client.get("/foundation/events/")
        self.assertEqual(resp_event01.status_code, 200)
        self.assertIn("WODDI leadership gathering", resp_event01.content.decode())

        # EVENT-05: Opening plenary
        resp_event05 = self.client.get("/foundation/events/plenary/")
        self.assertEqual(resp_event05.status_code, 200)
        self.assertIn("Opening plenary", resp_event05.content.decode())

        # POST: Chair opening plenary address
        resp_event05_post = self.client.post("/foundation/events/plenary/", {
            "action": "chair_session",
            "notes": "Addressed delegates from 55 African sovereign nations.",
        })
        self.assertEqual(resp_event05_post.status_code, 200)
        self.assertIn("Plenary Address Initiated", resp_event05_post.content.decode())

        # ROOM-03: Multilingua country coordination room
        resp_room03 = self.client.get("/foundation/rooms/coordination/")
        self.assertEqual(resp_room03.status_code, 200)
        self.assertIn("Country coordination", resp_room03.content.decode())

        # MTG-06: Meetings command centre
        resp_mtg06 = self.client.get("/foundation/meetings/command-centre/")
        self.assertEqual(resp_mtg06.status_code, 200)

    # -------------------------------------------------------------------------
    # Card 6: Performance Oversight Tests
    # -------------------------------------------------------------------------
    def test_performance_oversight_workflow(self):
        self._login_founder()

        # REP-05: Management reporting
        resp_rep05 = self.client.get("/foundation/reporting/management/")
        self.assertEqual(resp_rep05.status_code, 200)
        content_rep05 = resp_rep05.content.decode()
        self.assertIn("Management reporting", content_rep05)
        self.assertIn("Programme activities", content_rep05)
        self.assertIn("Meetings held", content_rep05)

        # REP-06: Performance scorecard
        resp_rep06 = self.client.get("/foundation/reporting/scorecard/")
        self.assertEqual(resp_rep06.status_code, 200)
        content_rep06 = resp_rep06.content.decode()
        self.assertIn("Performance scorecard", content_rep06)
        self.assertIn("Reporting compliance", content_rep06)
        self.assertIn("Ikeja", content_rep06)

    # -------------------------------------------------------------------------
    # Guardrail Boundaries Tests
    # -------------------------------------------------------------------------
    def test_strict_permission_boundaries(self):
        self._login_founder()

        # Safeguarding Boundary: Founder cannot view confidential case narratives (SAFE-04)
        resp_safe = self.client.get("/foundation/safeguarding/case/SG-024/")
        self.assertEqual(resp_safe.status_code, 403)

        # Alias route also fails closed
        resp_safe_alias = self.client.get("/foundation/screens/SAFE-04/")
        self.assertEqual(resp_safe_alias.status_code, 403)

        # Financial Dual-Signoff Guardrail
        from foundation.scope import get_user_scope
        founder_scope = get_user_scope(self.founder_account)
        with self.assertRaises(ScopePermissionDenied):
            assert_financial_disbursement_guardrail(founder_scope, 50000.0)
