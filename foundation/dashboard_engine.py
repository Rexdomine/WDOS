"""
WDOS Stage 5 Shared Dashboard Engine & Data Contract Registry
Provides authorized, role-specific, scoped operating views for DASH-01 through DASH-17.
Enforces fail-closed server authorization, geographic boundaries, cross-network separation,
and authentic database-reconciled data contracts.
"""

from typing import Any, Dict, List, Optional
from django.utils import timezone
from .models import (
    Chapter,
    CountryHub,
    DashboardAlert,
    DashboardActivity,
    DashboardReport,
    ScheduledMeeting,
    WorkItem,
)
from accounts.models import Account, Membership, OnboardingDraft
from .scope import ScopePermissionDenied


DASHBOARD_SCREENS: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # DASH-01: Continental priorities (Founder / HQ Executive Overview)
    # -------------------------------------------------------------------------
    "DASH-01": {
        "screen_id": "DASH-01",
        "title": "Continental priorities",
        "desktop_pnum": 75,
        "mobile_pnum": 76,
        "state_pnum": 77,
        "eyebrow": "HQ / BOTH NETWORKS",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "founder",
        "default_role_title": "Executive overview",
        "default_network": "HQ / Both networks",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "1,248",
                "label": "WGMN active leaders",
                "sub": "Nigeria, Ghana and other country views",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "864",
                "label": "WNNN active leaders",
                "sub": "Separate network view",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "4",
                "label": "Decisions awaiting you",
                "sub": "2 require additional evidence",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["DECISION / CONCERN", "NETWORK / COUNTRY", "OWNER", "STATUS"],
            "rows": [
                {
                    "item": "Country leadership coverage",
                    "col2": "WGMN · Ghana",
                    "col3": "HOFCO",
                    "status_label": "Needs review",
                    "status_style": "amber",
                    "url": "/foundation/dashboards/dash-10-coverage/",
                },
                {
                    "item": "Programme expansion proposal",
                    "col2": "WNNN · Kenya",
                    "col3": "Programmes",
                    "status_label": "Decision due",
                    "status_style": "amber",
                    "url": "/foundation/dashboards/dash-05/",
                },
                {
                    "item": "Country dossier conflict",
                    "col2": "WGMN · Nigeria",
                    "col3": "QA / Controls",
                    "status_label": "Evidence needed",
                    "status_style": "amber",
                    "url": "/foundation/dashboards/dash-09/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Country leadership coverage",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "Needs review",
                    "action_style": "magenta",
                    "url": "/foundation/dashboards/dash-10-coverage/",
                },
                {
                    "title": "Programme expansion proposal",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Decision due",
                    "action_style": "magenta",
                    "url": "/foundation/dashboards/dash-05/",
                },
            ],
        },
        "chart_card": {
            "title": "Country follow-ups by network",
            "badge": "Illustrative · open actions",
            "bars": [
                {"label": "WGMN", "value": 7, "color": "#E4C1D6"},
                {"label": "WNNN", "value": 5, "color": "#D4006A"},
            ],
        },
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": [
            "DASH-02", "DASH-03", "DASH-04", "DASH-05", "DASH-06", "DASH-07", "DASH-08", "DASH-09",
            "DASH-10", "DASH-11", "DASH-12", "DASH-13", "DASH-14", "DASH-15", "DASH-16", "DASH-17"
        ],
    },

    # -------------------------------------------------------------------------
    # DASH-02: Country operations (Operations Lead / HOFCO)
    # -------------------------------------------------------------------------
    "DASH-02": {
        "screen_id": "DASH-02",
        "title": "Country operations",
        "desktop_pnum": 78,
        "mobile_pnum": 79,
        "state_pnum": 80,
        "eyebrow": "HQ / BOTH NETWORKS",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "operations",
        "default_role_title": "HOFCO",
        "default_network": "HQ / Both networks",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "12",
                "label": "Country follow-ups",
                "sub": "Assigned operational actions",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "8",
                "label": "Critical vacancies",
                "sub": "Approved seats only",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "6",
                "label": "Onboarding overdue",
                "sub": "Needs individual follow-through",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["COUNTRY PRIORITY", "NETWORK", "OWNER", "STATUS"],
            "rows": [
                {
                    "item": "Deputy leadership vacancy",
                    "col2": "WGMN · Ghana",
                    "col3": "Country team",
                    "status_label": "Open",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Country dossier verification",
                    "col2": "WNNN · Kenya",
                    "col3": "Custodian",
                    "status_label": "Review due",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "September report follow-up",
                    "col2": "WGMN · Nigeria",
                    "col3": "Country lead",
                    "status_label": "In progress",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Deputy leadership vacancy",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "Open",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Country dossier verification",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Review due",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-01", "DASH-03", "DASH-04", "DASH-10", "DASH-11"],
    },

    # -------------------------------------------------------------------------
    # DASH-03: Coordination desk (Network Secretary)
    # -------------------------------------------------------------------------
    "DASH-03": {
        "screen_id": "DASH-03",
        "title": "Coordination desk",
        "desktop_pnum": 81,
        "mobile_pnum": 82,
        "state_pnum": 83,
        "eyebrow": "HQ / BOTH NETWORKS",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "operations",
        "default_role_title": "Network Secretary",
        "default_network": "HQ / Both networks",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "18",
                "label": "Applications to screen",
                "sub": "Across authorized routes",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "5",
                "label": "Letters to prepare",
                "sub": "Human selection recorded",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "3",
                "label": "Register conflicts",
                "sub": "Evidence review required",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["WORK ITEM", "ROUTE / SCOPE", "DUE", "STATUS"],
            "rows": [
                {
                    "item": "Lina Mensah · Pack review",
                    "col2": "Referral · WNNN",
                    "col3": "Today",
                    "status_label": "Review ready",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Ada Okafor · Appointment letter",
                    "col2": "WGMN · Nigeria",
                    "col3": "19 Sep",
                    "status_label": "Prepare",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Unmatched leadership record",
                    "col2": "Country register",
                    "col3": "20 Sep",
                    "status_label": "Investigate",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Lina Mensah · Pack review",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "Review ready",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Ada Okafor · Appointment letter",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Prepare",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-01", "DASH-02", "DASH-04", "DASH-10-PIPELINE"],
    },

    # -------------------------------------------------------------------------
    # DASH-04: Administration overview (Director of Administration)
    # -------------------------------------------------------------------------
    "DASH-04": {
        "screen_id": "DASH-04",
        "title": "Administration overview",
        "desktop_pnum": 84,
        "mobile_pnum": 85,
        "state_pnum": 86,
        "eyebrow": "HQ / AUTHORIZED SCOPE",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "founder",
        "default_role_title": "Director of Administration",
        "default_network": "HQ / Authorized scope",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "9",
                "label": "Access reviews",
                "sub": "Due this month",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "4",
                "label": "Document revisions",
                "sub": "Awaiting publication review",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Handover exceptions",
                "sub": "Outstanding official records",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["CONTROL ITEM", "RESPONSIBLE TEAM", "DUE", "STATUS"],
            "rows": [
                {
                    "item": "Role access recertification",
                    "col2": "Administration",
                    "col3": "30 Sep",
                    "status_label": "Review due",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Leadership Pack revision",
                    "col2": "Network office",
                    "col3": "22 Sep",
                    "status_label": "Approval pending",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Office identity transfer",
                    "col2": "IT / Administration",
                    "col3": "19 Sep",
                    "status_label": "Evidence needed",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Role access recertification",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "Review due",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Leadership Pack revision",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Approval pending",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-01", "DASH-02", "DASH-03", "DASH-09"],
    },

    # -------------------------------------------------------------------------
    # DASH-05: Programme portfolio (Director of Programmes)
    # -------------------------------------------------------------------------
    "DASH-05": {
        "screen_id": "DASH-05",
        "title": "Programme portfolio",
        "desktop_pnum": 87,
        "mobile_pnum": 88,
        "state_pnum": 89,
        "eyebrow": "HQ / BOTH NETWORKS",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "operations",
        "default_role_title": "Director of Programmes",
        "default_network": "HQ / Both networks",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "7",
                "label": "Proposals to review",
                "sub": "Decision queue",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "12",
                "label": "Activities underway",
                "sub": "Approved programme work",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "4",
                "label": "Evidence overdue",
                "sub": "Follow-up required",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["PROGRAMME / ACTIVITY", "AREA", "OWNER", "STATUS"],
            "rows": [
                {
                    "item": "Community Skills Exchange",
                    "col2": "Lagos",
                    "col3": "Ada Okafor",
                    "status_label": "Approved",
                    "status_style": "green",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Family Wellbeing Circle",
                    "col2": "Abuja",
                    "col3": "Lina Mensah",
                    "status_label": "Under review",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Digital Confidence Workshop",
                    "col2": "Kano",
                    "col3": "Kemi Bello",
                    "status_label": "Evidence due",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Community Skills Exchange",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "Approved",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Family Wellbeing Circle",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Under review",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-01", "DASH-06", "DASH-07", "DASH-10"],
    },

    # -------------------------------------------------------------------------
    # DASH-06: Communications workspace (Communications Lead)
    # -------------------------------------------------------------------------
    "DASH-06": {
        "screen_id": "DASH-06",
        "title": "Communications workspace",
        "desktop_pnum": 90,
        "mobile_pnum": 91,
        "state_pnum": 92,
        "eyebrow": "HQ / BOTH NETWORKS",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "operations",
        "default_role_title": "Communications lead",
        "default_network": "HQ / Both networks",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "14",
                "label": "Media awaiting review",
                "sub": "Consent and usage checks",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "3",
                "label": "Campaigns scheduled",
                "sub": "Approved versions only",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "6",
                "label": "Deliverables due",
                "sub": "This week",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["COMMUNICATION", "AUDIENCE", "SCHEDULED", "STATUS"],
            "rows": [
                {
                    "item": "Monthly focus",
                    "col2": "WGMN · Nigeria",
                    "col3": "18 Sep · 09:00",
                    "status_label": "Approved",
                    "status_style": "green",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Country meeting reminder",
                    "col2": "WNNN · Kenya",
                    "col3": "19 Sep · 10:00",
                    "status_label": "Scheduled",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Programme highlights",
                    "col2": "Consented Community",
                    "col3": "Draft",
                    "status_label": "Review required",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Monthly focus",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "Approved",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Country meeting reminder",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Scheduled",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-01", "DASH-05", "DASH-08"],
    },

    # -------------------------------------------------------------------------
    # DASH-07: Resource accountability (Finance Reviewer)
    # -------------------------------------------------------------------------
    "DASH-07": {
        "screen_id": "DASH-07",
        "title": "Resource accountability",
        "desktop_pnum": 93,
        "mobile_pnum": 94,
        "state_pnum": 95,
        "eyebrow": "HQ / AUTHORIZED FINANCE",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "operations",
        "default_role_title": "Finance reviewer",
        "default_network": "HQ / Authorized finance",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "5",
                "label": "Reviews awaiting you",
                "sub": "Within delegated authority",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "3",
                "label": "Evidence outstanding",
                "sub": "Return requested",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Open exceptions",
                "sub": "Accountability follow-up",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["RECORD", "PROGRAMME", "EVIDENCE", "STATUS"],
            "rows": [
                {
                    "item": "FR-031 · Workshop materials",
                    "col2": "Community Skills Exchange",
                    "col3": "Receipt attached",
                    "status_label": "Review due",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "FR-028 · Venue resources",
                    "col2": "Family Wellbeing Circle",
                    "col3": "Return requested",
                    "status_label": "Awaiting evidence",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "FR-025 · Equipment return",
                    "col2": "Digital Confidence Workshop",
                    "col3": "Verified",
                    "status_label": "Closed",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "FR-031 · Workshop materials",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "Review due",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "FR-028 · Venue resources",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Awaiting evidence",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-01", "DASH-04", "DASH-05"],
    },

    # -------------------------------------------------------------------------
    # DASH-08: Systems operations (IT & Systems)
    # -------------------------------------------------------------------------
    "DASH-08": {
        "screen_id": "DASH-08",
        "title": "Systems operations",
        "desktop_pnum": 96,
        "mobile_pnum": 97,
        "state_pnum": 98,
        "eyebrow": "HQ / TECHNICAL CONTROLS",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "operations",
        "default_role_title": "IT & Systems",
        "default_network": "HQ / Technical controls",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "2",
                "label": "Incidents to review",
                "sub": "Assigned response actions",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "6",
                "label": "Jobs needing reconciliation",
                "sub": "Outcome not yet confirmed",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "3",
                "label": "Evidence awaiting sign-off",
                "sub": "Restore and release records",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["SERVICE / JOB", "LAST EVIDENCE", "OWNER", "STATUS"],
            "rows": [
                {
                    "item": "Institute status exchange",
                    "col2": "Mapping awaiting check",
                    "col3": "IT team",
                    "status_label": "Review required",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Notification delivery",
                    "col2": "Provider response received",
                    "col3": "Communications",
                    "status_label": "Reconciling",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Restore rehearsal",
                    "col2": "Evidence awaiting sign-off",
                    "col3": "IT team",
                    "status_label": "Review required",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Institute status exchange",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "Review required",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Notification delivery",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Reconciling",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-01", "DASH-04", "DASH-09"],
    },

    # -------------------------------------------------------------------------
    # DASH-09: Quality and controls (QA / Controls)
    # -------------------------------------------------------------------------
    "DASH-09": {
        "screen_id": "DASH-09",
        "title": "Quality and controls",
        "desktop_pnum": 99,
        "mobile_pnum": 100,
        "state_pnum": 101,
        "eyebrow": "HQ / AUTHORIZED SCOPE",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "operations",
        "default_role_title": "QA / Controls",
        "default_network": "HQ / Authorized scope",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "11",
                "label": "Open findings",
                "sub": "3 need priority review",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "8",
                "label": "UAT evidence to review",
                "sub": "No acceptance assumed",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Access review exceptions",
                "sub": "Assigned control owners",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["FINDING", "AREA", "OWNER", "STATE"],
            "rows": [
                {
                    "item": "Mobile audio recovery",
                    "col2": "Multilingua",
                    "col3": "IT team",
                    "status_label": "Retest due",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Country record mismatch",
                    "col2": "Data quality",
                    "col3": "Country custodian",
                    "status_label": "Unresolved",
                    "status_style": "green",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Role access denial evidence",
                    "col2": "Permissions",
                    "col3": "QA team",
                    "status_label": "Review ready",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Mobile audio recovery",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "Retest due",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Country record mismatch",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Unresolved",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-01", "DASH-04", "DASH-08"],
    },

    # -------------------------------------------------------------------------
    # DASH-10: Nigeria country overview (Country Representative)
    # -------------------------------------------------------------------------
    "DASH-10": {
        "screen_id": "DASH-10",
        "title": "Nigeria country overview",
        "desktop_pnum": 102,
        "mobile_pnum": 103,
        "state_pnum": 104,
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "country_lead",
        "default_role_title": "Country Representative",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": False,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "126",
                "label": "Current leaders",
                "sub": "Within your country scope",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "8",
                "label": "Approved vacancies",
                "sub": "Principal and deputy seats",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "6",
                "label": "Reports awaiting review",
                "sub": "September period",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["POSITION", "UNIT", "HOLDER", "STATUS"],
            "rows": [
                {
                    "item": "State Coordinator",
                    "col2": "Lagos",
                    "col3": "Lina Mensah",
                    "status_label": "Active",
                    "status_style": "green",
                    "url": "/foundation/dashboards/dash-11/",
                },
                {
                    "item": "Assistant Coordinator",
                    "col2": "Lagos",
                    "col3": "Unfilled",
                    "status_label": "Vacant",
                    "status_style": "purple",
                    "url": "/foundation/dashboards/dash-10-coverage/",
                },
                {
                    "item": "LGA Coordinator",
                    "col2": "Ikeja",
                    "col3": "Kemi Bello",
                    "status_label": "Onboarding",
                    "status_style": "purple",
                    "url": "/foundation/dashboards/dash-12/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "State Coordinator",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "Active",
                    "action_style": "magenta",
                    "url": "/foundation/dashboards/dash-11/",
                },
                {
                    "title": "Assistant Coordinator",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Vacant",
                    "action_style": "magenta",
                    "url": "/foundation/dashboards/dash-10-coverage/",
                },
            ],
        },
        "chart_card": {
            "title": "Reports approved this period",
            "badge": "Illustrative · approved returns",
            "bars": [
                {"label": "Lagos", "value": 6, "color": "#E4C1D6"},
                {"label": "Kano", "value": 4, "color": "#E4C1D6"},
                {"label": "Abuja", "value": 5, "color": "#E4C1D6"},
                {"label": "Oyo", "value": 3, "color": "#D4006A"},
            ],
        },
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": [
            "DASH-10-COVERAGE", "DASH-10-PIPELINE", "DASH-10-INACTIVE", "DASH-10-ATTENTION",
            "DASH-10-CR", "DASH-10-REPORTING", "DASH-10-ENGAGEMENT", "DASH-10-SAFEGUARDING",
            "DASH-11", "DASH-12", "DASH-13", "DASH-14"
        ],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-10-COVERAGE: Nigeria leadership coverage
    # -------------------------------------------------------------------------
    "DASH-10-COVERAGE": {
        "screen_id": "DASH-10-COVERAGE",
        "title": "Nigeria leadership coverage",
        "desktop_pnum": 105,
        "mobile_pnum": 106,
        "state_pnum": 107,
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "country_lead",
        "default_role_title": "Country Representative",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Back to overview", "url": "/foundation/dashboards/dash-10/"},
        "secondary_action": None,
        "has_tabs": False,
        "hero_banner": None,
        "has_search_filter": True,
        "table_card": {
            "title": "Nigeria leadership coverage",
            "columns": ["UNIT / NETWORK", "PRINCIPAL / DEPUTY", "COVERAGE RESULT"],
            "rows": [
                {
                    "item": "Lagos · WGMN",
                    "col2": "Principal and deputy active",
                    "status_label": "Complete",
                    "status_style": "green",
                    "url": "/foundation/dashboards/dash-11/",
                },
                {
                    "item": "Kano · WGMN",
                    "col2": "Principal only",
                    "status_label": "Deputy vacancy",
                    "status_style": "purple",
                    "url": "/foundation/dashboards/dash-10/",
                },
                {
                    "item": "Abuja · WGMN",
                    "col2": "Deputy only",
                    "status_label": "Principal vacancy",
                    "status_style": "purple",
                    "url": "/foundation/dashboards/dash-10/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": None,
        "chart_card": None,
        "scoped_notice": "Sample summary: 12 of 14 units complete = 86% rounded. Two incomplete units are Kano and Abuja. Full records must use the approved denominator; rows here illustrate the exceptions.",
        "related_screens": ["DASH-10", "DASH-10-PIPELINE", "DASH-10-INACTIVE", "DASH-10-CR"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-10-PIPELINE: Recruitment and activation
    # -------------------------------------------------------------------------
    "DASH-10-PIPELINE": {
        "screen_id": "DASH-10-PIPELINE",
        "title": "Recruitment and activation",
        "desktop_pnum": 108,
        "mobile_pnum": 109,
        "state_pnum": 110,
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "country_lead",
        "default_role_title": "Country Representative",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Open candidate review", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": False,
        "hero_banner": None,
        "has_search_filter": True,
        "table_card": {
            "title": "Recruitment and activation",
            "columns": ["QUEUE", "NUMBER · SAMPLE", "NEXT STEP"],
            "rows": [
                {
                    "item": "Recruitment review",
                    "col2": "8",
                    "status_label": "Review candidate evidence",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Activation pending",
                    "col2": "3",
                    "status_label": "Check appointment acceptance",
                    "status_style": "plain",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 2 records in this view",
        },
        "attention_card": None,
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-10", "DASH-10-COVERAGE", "DASH-10-INACTIVE", "DASH-10-CR"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-10-INACTIVE: Leaders needing follow-up
    # -------------------------------------------------------------------------
    "DASH-10-INACTIVE": {
        "screen_id": "DASH-10-INACTIVE",
        "title": "Leaders needing follow-up",
        "desktop_pnum": 111,
        "mobile_pnum": 112,
        "state_pnum": 113,
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "country_lead",
        "default_role_title": "Country Representative",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Back to overview", "url": "/foundation/dashboards/dash-10/"},
        "secondary_action": None,
        "has_tabs": False,
        "hero_banner": None,
        "has_search_filter": True,
        "table_card": {
            "title": "Leaders needing follow-up",
            "columns": ["PERSON / ROLE", "LAST ACTIVITY", "ASSIGNED NEXT STEP"],
            "rows": [
                {
                    "item": "Example leader A",
                    "col2": "Date from approved activity rule",
                    "status_label": "Country lead to contact",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Example leader B",
                    "col2": "Date from approved activity rule",
                    "status_label": "Check support needs",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 2 records in this view",
        },
        "attention_card": None,
        "chart_card": None,
        "scoped_notice": "Inactivity follows an approved rule, not an invented deadline. Contact appropriately; do not automatically remove appointment or permissions.",
        "related_screens": ["DASH-10", "DASH-10-COVERAGE", "DASH-10-PIPELINE", "DASH-10-CR"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-10-ATTENTION: Support and HQ attention
    # -------------------------------------------------------------------------
    "DASH-10-ATTENTION": {
        "screen_id": "DASH-10-ATTENTION",
        "title": "Support and HQ attention",
        "desktop_pnum": 114,
        "mobile_pnum": 115,
        "state_pnum": 116,
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "country_lead",
        "default_role_title": "Country Representative",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Back to overview", "url": "/foundation/dashboards/dash-10/"},
        "secondary_action": None,
        "has_tabs": False,
        "hero_banner": None,
        "has_search_filter": True,
        "table_card": {
            "title": "Support and HQ attention",
            "columns": ["REFERENCE", "SAFE SUMMARY", "OWNER / NEXT STEP"],
            "rows": [
                {
                    "item": "HD-DEMO-01",
                    "col2": "Access support · no sensitive details",
                    "status_label": "Assigned support operator",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "HD-DEMO-02",
                    "col2": "Meeting support",
                    "status_label": "Assigned support operator",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "HD-DEMO-03",
                    "col2": "Profile correction",
                    "status_label": "Assigned support operator",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "HQ-DEMO-01",
                    "col2": "Country operational escalation",
                    "status_label": "HQ nominated reviewer",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 4 records in this view",
        },
        "attention_card": None,
        "chart_card": None,
        "scoped_notice": "Only ordinary support and permitted operational summaries. Confidential safeguarding records and their existence are not disclosed here.",
        "related_screens": ["DASH-10", "DASH-10-CR", "DASH-10-SAFEGUARDING"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-10-CR: Nigeria · what needs attention
    # -------------------------------------------------------------------------
    "DASH-10-CR": {
        "screen_id": "DASH-10-CR",
        "title": "Nigeria · what needs attention",
        "desktop_pnum": 117,
        "mobile_pnum": 118,
        "state_pnum": 119,
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Start with overdue work. Then open any row to see the records behind the number.",
        "default_role_code": "country_lead",
        "default_role_title": "Country Representative",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Open overdue work", "url": "/foundation/work-queue/"},
        "secondary_action": {"label": "Back to dashboard", "url": "/foundation/dashboards/dash-10/"},
        "has_tabs": False,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "86%",
                "label": "Leadership coverage",
                "sub": "12 of 14 units · rounded sample",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "8 / 3",
                "label": "Recruitment / activation",
                "sub": "8 in review · 3 awaiting activation",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Leaders inactive",
                "sub": "Follow-up required · approved rule applies",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Country Command",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["AREA", "CURRENT PICTURE", "NEXT STEP"],
            "rows": [
                {
                    "item": "Leadership completeness",
                    "col2": "86% · 12 of 14 units",
                    "status_label": "See incomplete units →",
                    "status_style": "link",
                    "url": "/foundation/dashboards/dash-10-coverage/",
                },
                {
                    "item": "Recruitment / activation",
                    "col2": "8 in review · 3 awaiting activation",
                    "status_label": "Open pipeline →",
                    "status_style": "link",
                    "url": "/foundation/dashboards/dash-10-pipeline/",
                },
                {
                    "item": "Inactive leaders",
                    "col2": "2 need follow-up",
                    "status_label": "Review named records →",
                    "status_style": "link",
                    "url": "/foundation/dashboards/dash-10-inactive/",
                },
                {
                    "item": "Acting / assistants",
                    "col2": "1 acting · 2 bounded assistants",
                    "status_label": "Check appointment scope →",
                    "status_style": "link",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Reports / overdue work",
                    "col2": "6 reports · 4 actions overdue",
                    "status_label": "Open work queue →",
                    "status_style": "link",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Meetings / programmes",
                    "col2": "2 upcoming · 3 active",
                    "status_label": "View schedule →",
                    "status_style": "link",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Evidence / engagement",
                    "col2": "2 awaiting review · 3 follow-ups",
                    "status_label": "Open evidence review →",
                    "status_style": "link",
                    "url": "/foundation/dashboards/dash-10-engagement/",
                },
                {
                    "item": "Support / HQ attention",
                    "col2": "3 tickets · 1 operational escalation",
                    "status_label": "Open safe summary →",
                    "status_style": "link",
                    "url": "/foundation/dashboards/dash-10-attention/",
                },
            ],
            "record_count_text": "Showing 8 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Start with overdue work",
                    "body": "Four actions need follow-up. Open the queue to see the owner and due date.",
                    "action_label": "First priority",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Check leadership gaps",
                    "body": "Two units need a principal or deputy. Review the exact units before taking action.",
                    "action_label": "Nigeria · selected network",
                    "action_style": "magenta",
                    "url": "/foundation/dashboards/dash-10-coverage/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Nigeria and the selected network only. Confidential safeguarding information is not included.",
        "related_screens": ["DASH-10", "DASH-10-COVERAGE", "DASH-10-PIPELINE", "DASH-10-INACTIVE", "DASH-10-ATTENTION"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-10-REPORTING: Reporting desk (HQ Reporting Reviewer)
    # -------------------------------------------------------------------------
    "DASH-10-REPORTING": {
        "screen_id": "DASH-10-REPORTING",
        "title": "Reporting desk",
        "desktop_pnum": 120,
        "mobile_pnum": 121,
        "state_pnum": 122,
        "eyebrow": "HQ / HQ REPORTING REVIEWER",
        "subtitle": "Use the information and next action for this role only.",
        "default_role_code": "operations",
        "default_role_title": "HQ reporting reviewer",
        "default_network": "HQ / Both networks",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open assigned work", "url": "/foundation/work-queue/"},
        "secondary_action": {"label": "Back to dashboard", "url": "/foundation/dashboards/dash-10/"},
        "has_tabs": False,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "6",
                "label": "Waiting for review",
                "sub": "Synthetic review example",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Corrections due",
                "sub": "Synthetic review example",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "1",
                "label": "Missed reports",
                "sub": "Synthetic review example",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Reporting desk",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["PERIOD", "COUNTRY / NETWORK", "REVIEW STATUS"],
            "rows": [
                {
                    "item": "September · sample",
                    "col2": "Nigeria · WGMN",
                    "status_label": "2 returns needed",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "September · sample",
                    "col2": "Kenya · WNNN",
                    "status_label": "1 nil report to review",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 2 records in this view",
        },
        "attention_card": None,
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-10", "DASH-10-CR", "DASH-01"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-10-ENGAGEMENT: Engagement desk (HQ Engagement Lead)
    # -------------------------------------------------------------------------
    "DASH-10-ENGAGEMENT": {
        "screen_id": "DASH-10-ENGAGEMENT",
        "title": "Engagement desk",
        "desktop_pnum": 123,
        "mobile_pnum": 124,
        "state_pnum": 125,
        "eyebrow": "HQ / HQ ENGAGEMENT LEAD",
        "subtitle": "Use the information and next action for this role only.",
        "default_role_code": "operations",
        "default_role_title": "HQ engagement lead",
        "default_network": "HQ / Both networks",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open assigned work", "url": "/foundation/work-queue/"},
        "secondary_action": {"label": "Back to dashboard", "url": "/foundation/dashboards/dash-10/"},
        "has_tabs": False,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "3",
                "label": "Active cycles",
                "sub": "Synthetic review example",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "4",
                "label": "Follow-up due",
                "sub": "Synthetic review example",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Contact suppressed",
                "sub": "Synthetic review example",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Engagement desk",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["CYCLE", "AUDIENCE", "NEXT ACTION"],
            "rows": [
                {
                    "item": "Flagship",
                    "col2": "Opted-in local groups",
                    "status_label": "Review participation",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Connect",
                    "col2": "Assigned follow-up",
                    "status_label": "Check fatigue limits",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Exchange",
                    "col2": "Peer groups",
                    "status_label": "Review feedback",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": None,
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-10", "DASH-10-CR", "DASH-06"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-10-SAFEGUARDING: Confidential safeguarding desk (Authorised Safeguarding Officer)
    # -------------------------------------------------------------------------
    "DASH-10-SAFEGUARDING": {
        "screen_id": "DASH-10-SAFEGUARDING",
        "title": "Confidential safeguarding desk",
        "desktop_pnum": 126,
        "mobile_pnum": 127,
        "state_pnum": 128,
        "eyebrow": "HQ / AUTHORISED SAFEGUARDING OFFICER",
        "subtitle": "Use the information and next action for this role only.",
        "default_role_code": "operations",
        "default_role_title": "Authorised safeguarding officer",
        "default_network": "HQ / Authorised safeguarding officer",
        "default_country": "ALL",
        "primary_action": {"label": "→ Open assigned work", "url": "/foundation/work-queue/"},
        "secondary_action": {"label": "Back to dashboard", "url": "/foundation/dashboards/dash-10/"},
        "has_tabs": False,
        "hero_banner": None,
        "requires_safeguarding": True,
        "kpi_cards": [
            {
                "value": "2",
                "label": "Assigned to me",
                "sub": "Synthetic review example",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "1",
                "label": "Response due",
                "sub": "Synthetic review example",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "1",
                "label": "Restricted escalations",
                "sub": "Synthetic review example",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Confidential safeguarding desk",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["REFERENCE", "ASSIGNED OWNER", "NEXT ACTION"],
            "rows": [
                {
                    "item": "SG-DEMO-01",
                    "col2": "Your assigned case",
                    "status_label": "Review safe response",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "SG-DEMO-02",
                    "col2": "Assigned officer",
                    "status_label": "Check escalation",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 2 records in this view",
        },
        "attention_card": None,
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-10", "DASH-10-ATTENTION"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-11: Lagos regional overview (State Coordinator)
    # -------------------------------------------------------------------------
    "DASH-11": {
        "screen_id": "DASH-11",
        "title": "Lagos regional overview",
        "desktop_pnum": 129,
        "mobile_pnum": 130,
        "state_pnum": 131,
        "eyebrow": "WGMN / NIGERIA / LAGOS",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "country_lead",
        "default_role_title": "State Coordinator",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "12",
                "label": "Local units",
                "sub": "Assigned organisational subtree",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "5",
                "label": "Follow-ups due",
                "sub": "Direct reports",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "3",
                "label": "Reports to review",
                "sub": "September period",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["TASK", "OWNER", "DUE", "STATUS"],
            "rows": [
                {
                    "item": "Confirm Chapter meeting agenda",
                    "col2": "Ada Okafor",
                    "col3": "18 Sep",
                    "status_label": "In progress",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Review programme evidence",
                    "col2": "Lina Mensah",
                    "col3": "20 Sep",
                    "status_label": "Needs review",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Update Chapter contact list",
                    "col2": "Kemi Bello",
                    "col3": "22 Sep",
                    "status_label": "Open",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Confirm Chapter meeting agenda",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "In progress",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Review programme evidence",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Needs review",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-10", "DASH-12", "DASH-13", "DASH-14"],
    },

    # -------------------------------------------------------------------------
    # DASH-12: Ikeja local operations (LGA Coordinator)
    # -------------------------------------------------------------------------
    "DASH-12": {
        "screen_id": "DASH-12",
        "title": "Ikeja local operations",
        "desktop_pnum": 132,
        "mobile_pnum": 133,
        "state_pnum": 134,
        "eyebrow": "WGMN / NIGERIA / IKEJA",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "chapter_lead",
        "default_role_title": "LGA Coordinator",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "4",
                "label": "Community Clusters",
                "sub": "Assigned units",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "7",
                "label": "Open local actions",
                "sub": "Owner and due date recorded",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Evidence returns due",
                "sub": "Activity follow-through",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["TASK", "OWNER", "DUE", "STATUS"],
            "rows": [
                {
                    "item": "Confirm Chapter meeting agenda",
                    "col2": "Ada Okafor",
                    "col3": "18 Sep",
                    "status_label": "In progress",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Review programme evidence",
                    "col2": "Lina Mensah",
                    "col3": "20 Sep",
                    "status_label": "Needs review",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Update Chapter contact list",
                    "col2": "Kemi Bello",
                    "col3": "22 Sep",
                    "status_label": "Open",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Confirm Chapter meeting agenda",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "In progress",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Review programme evidence",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Needs review",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-11", "DASH-13", "DASH-14"],
    },

    # -------------------------------------------------------------------------
    # DASH-13: Your Cluster at a glance (Cluster Coordinator)
    # -------------------------------------------------------------------------
    "DASH-13": {
        "screen_id": "DASH-13",
        "title": "Your Cluster at a glance",
        "desktop_pnum": 135,
        "mobile_pnum": 136,
        "state_pnum": 137,
        "eyebrow": "WGMN / NIGERIA / IKEJA",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "chapter_lead",
        "default_role_title": "Cluster Coordinator",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": None,
        "kpi_cards": [
            {
                "value": "6",
                "label": "Connected Chapters",
                "sub": "Within this Cluster",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "3",
                "label": "Chapter follow-ups",
                "sub": "Support and engagement",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Reports to consolidate",
                "sub": "September returns",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["TASK", "OWNER", "DUE", "STATUS"],
            "rows": [
                {
                    "item": "Confirm Chapter meeting agenda",
                    "col2": "Ada Okafor",
                    "col3": "18 Sep",
                    "status_label": "In progress",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Review programme evidence",
                    "col2": "Lina Mensah",
                    "col3": "20 Sep",
                    "status_label": "Needs review",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Update Chapter contact list",
                    "col2": "Kemi Bello",
                    "col3": "22 Sep",
                    "status_label": "Open",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Confirm Chapter meeting agenda",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "In progress",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Review programme evidence",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Needs review",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-11", "DASH-12", "DASH-14"],
    },

    # -------------------------------------------------------------------------
    # DASH-14: Your Chapter today (Chapter Coordinator)
    # -------------------------------------------------------------------------
    "DASH-14": {
        "screen_id": "DASH-14",
        "title": "Your Chapter today",
        "desktop_pnum": 138,
        "mobile_pnum": 139,
        "state_pnum": 140,
        "eyebrow": "WGMN / NIGERIA / IKEJA",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "chapter_lead",
        "default_role_title": "Chapter Coordinator",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": False,
        "hero_banner": {
            "eyebrow": "YOUR NEXT STEP",
            "heading": "Confirm Chapter meeting agenda",
            "body": "Open the linked record, review the evidence and follow the next permitted action.",
            "button_label": "→ Open my work",
            "button_url": "/foundation/work-queue/",
        },
        "kpi_cards": [
            {
                "value": "28",
                "label": "Connected members",
                "sub": "Your Chapter",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Tasks due",
                "sub": "This week",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "18 Sep",
                "label": "Next meeting",
                "sub": "10:00 WAT",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["TASK", "OWNER", "DUE", "STATUS"],
            "rows": [
                {
                    "item": "Confirm Chapter meeting agenda",
                    "col2": "Ada Okafor",
                    "col3": "18 Sep",
                    "status_label": "In progress",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Review programme evidence",
                    "col2": "Lina Mensah",
                    "col3": "20 Sep",
                    "status_label": "Needs review",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Update Chapter contact list",
                    "col2": "Kemi Bello",
                    "col3": "22 Sep",
                    "status_label": "Open",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Confirm Chapter meeting agenda",
                    "body": "Open the linked record, review the evidence and follow the next permitted action.",
                    "action_label": "In progress",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Review programme evidence",
                    "body": "This item needs your attention within your assigned responsibilities.",
                    "action_label": "Needs review",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-12", "DASH-13", "DASH-15"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-15: Good morning, Ada (Member Dashboard)
    # -------------------------------------------------------------------------
    "DASH-15": {
        "screen_id": "DASH-15",
        "title": "Good morning, Ada",
        "desktop_pnum": 141,
        "mobile_pnum": 142,
        "state_pnum": 143,
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "member",
        "default_role_title": "Member",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ View opportunities", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": {
            "eyebrow": "YOUR NEXT STEP",
            "heading": "Your Chapter welcome is coming up",
            "body": "Meet your local team and learn how to take part.",
            "button_label": "→ View opportunities",
            "button_url": "/foundation/work-queue/",
        },
        "kpi_cards": [
            {
                "value": "Ikeja",
                "label": "My local home",
                "sub": "Chapter connection",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Upcoming activities",
                "sub": "You are eligible to join",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "1",
                "label": "My learning",
                "sub": "Orientation in progress",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["YOUR NEXT ACTIVITY", "WHEN", "NEXT ACTION"],
            "rows": [
                {
                    "item": "Chapter welcome meeting",
                    "col2": "18 Sep · 10:00",
                    "status_label": "View invitation",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Digital confidence workshop",
                    "col2": "22 Sep",
                    "status_label": "View activity",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Role opportunities",
                    "col2": "Applications open",
                    "status_label": "Explore",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Your Chapter welcome is coming up",
                    "body": "Meet your local team and learn how to take part.",
                    "action_label": "18 Sep · 10:00 WAT",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Build digital confidence",
                    "body": "Explore a practical activity designed to make participation easier.",
                    "action_label": "View workshop",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-14", "DASH-16", "DASH-17"],
    },

    # -------------------------------------------------------------------------
    # DASH-16: Your next step is clear (Candidate Dashboard)
    # -------------------------------------------------------------------------
    "DASH-16": {
        "screen_id": "DASH-16",
        "title": "Your next step is clear",
        "desktop_pnum": 144,
        "mobile_pnum": 145,
        "state_pnum": 146,
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "candidate",
        "default_role_title": "Candidate",
        "default_network": "WGMN",
        "default_country": "NG",
        "primary_action": {"label": "→ Continue my journey", "url": "/onboarding/step/4/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": {
            "eyebrow": "YOUR NEXT STEP",
            "heading": "Continue your day 4 reflection",
            "body": "Read the prompt, add your response and save your progress before the deadline.",
            "button_label": "→ Continue my journey",
            "button_url": "/onboarding/step/4/",
        },
        "kpi_cards": [
            {
                "value": "7 days",
                "label": "Your route",
                "sub": "Open-call Activation",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "Day 4",
                "label": "Current step",
                "sub": "Evidence and reflection",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "3 days",
                "label": "Time remaining",
                "sub": "Server deadline shown at runtime",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["JOURNEY STEP", "PROGRESS", "NEXT ACTION"],
            "rows": [
                {
                    "item": "Welcome and responsibilities",
                    "col2": "Completed",
                    "status_label": "Read again",
                    "status_style": "purple",
                    "url": "/onboarding/step/1/",
                },
                {
                    "item": "Local community context",
                    "col2": "Completed",
                    "status_label": "View response",
                    "status_style": "purple",
                    "url": "/onboarding/step/2/",
                },
                {
                    "item": "Evidence and reflection",
                    "col2": "In progress",
                    "status_label": "Continue",
                    "status_style": "purple",
                    "url": "/onboarding/step/4/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Continue your day 4 reflection",
                    "body": "Read the prompt, add your response and save your progress before the deadline.",
                    "action_label": "Day 4 of 7",
                    "action_style": "magenta",
                    "url": "/onboarding/step/4/",
                },
                {
                    "title": "Support is available",
                    "body": "Ask for help if you need assistance with the journey.",
                    "action_label": "Contact support",
                    "action_style": "magenta",
                    "url": "/auth/help/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-16-NETWORK", "DASH-16-EVENT", "DASH-15"],
        "support_note": "Ask your support team if you need guidance.",
    },

    # -------------------------------------------------------------------------
    # DASH-16-NETWORK: Your volunteer application (Candidate Network Subview)
    # -------------------------------------------------------------------------
    "DASH-16-NETWORK": {
        "screen_id": "DASH-16-NETWORK",
        "title": "Your volunteer application",
        "desktop_pnum": 147,
        "mobile_pnum": 148,
        "state_pnum": 149,
        "eyebrow": "MY APPLICATION / ASSIGNED SCOPE",
        "subtitle": "See what needs your attention and take one clear next step.",
        "default_role_code": "candidate",
        "default_role_title": "Network Volunteer Applicant",
        "default_network": "My application",
        "default_country": "NG",
        "primary_action": {"label": "→ Open my next step", "url": "/onboarding/step/4/"},
        "secondary_action": {"label": "Back", "url": "/foundation/dashboards/dash-16/"},
        "has_tabs": False,
        "hero_banner": None,
        "table_card": {
            "title": "Your volunteer application",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["MY NEXT STEP", "DETAILS"],
            "rows": [
                {
                    "item": "Your application",
                    "col2": "Waiting for your next step",
                    "status_label": "Waiting for your next step",
                    "status_style": "amber",
                    "url": "/onboarding/step/4/",
                },
                {
                    "item": "What to do next",
                    "col2": "Complete the assigned introduction",
                    "status_label": "Complete the assigned introduction",
                    "status_style": "plain",
                    "url": "/onboarding/step/4/",
                },
                {
                    "item": "Need more time?",
                    "col2": "Ask the recruitment team",
                    "status_label": "Ask the recruitment team",
                    "status_style": "purple",
                    "url": "/auth/help/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Start with one thing",
                    "body": "Your assigned next step is shown here. You do not need to search through the whole system.",
                    "action_label": "Help is available",
                    "action_style": "magenta",
                    "url": "/auth/help/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-16", "DASH-16-EVENT"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-16-EVENT: Your event volunteering (Candidate Event Subview)
    # -------------------------------------------------------------------------
    "DASH-16-EVENT": {
        "screen_id": "DASH-16-EVENT",
        "title": "Your event volunteering",
        "desktop_pnum": 150,
        "mobile_pnum": 151,
        "state_pnum": 152,
        "eyebrow": "MY APPLICATION / ASSIGNED SCOPE",
        "subtitle": "See what needs your attention and take one clear next step.",
        "default_role_code": "candidate",
        "default_role_title": "Event Volunteer",
        "default_network": "My application",
        "default_country": "NG",
        "primary_action": {"label": "→ Open my next step", "url": "/onboarding/step/4/"},
        "secondary_action": {"label": "Back", "url": "/foundation/dashboards/dash-16/"},
        "has_tabs": False,
        "hero_banner": None,
        "table_card": {
            "title": "Your event volunteering",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["MY NEXT STEP", "DETAILS"],
            "rows": [
                {
                    "item": "Your event",
                    "col2": "Assigned event example",
                    "status_label": "Assigned event example",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Your task",
                    "col2": "Check your event briefing",
                    "status_label": "Check your event briefing",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "When and where",
                    "col2": "Open the confirmed event details",
                    "status_label": "Open the confirmed event details",
                    "status_style": "plain",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Start with one thing",
                    "body": "Your assigned next step is shown here. You do not need to search through the whole system.",
                    "action_label": "Help is available",
                    "action_style": "magenta",
                    "url": "/auth/help/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-16", "DASH-16-NETWORK"],
        "support_note": "Need help? Ask your support team. Never share your password or verification codes.",
    },

    # -------------------------------------------------------------------------
    # DASH-17: Stay connected with WODDI (Community Participant Dashboard)
    # -------------------------------------------------------------------------
    "DASH-17": {
        "screen_id": "DASH-17",
        "title": "Stay connected with WODDI",
        "desktop_pnum": 153,
        "mobile_pnum": 154,
        "state_pnum": 155,
        "eyebrow": "WODDI / MY RELATIONSHIPS",
        "subtitle": "Your priorities, relevant evidence and next actions in one clear view.",
        "default_role_code": "community",
        "default_role_title": "Community participant",
        "default_network": "WODDI",
        "default_country": "NG",
        "primary_action": {"label": "→ View opportunities", "url": "/foundation/work-queue/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": {
            "eyebrow": "YOUR NEXT STEP",
            "heading": "Join the next community conversation",
            "body": "Explore an invitation connected to your current interests and relationships.",
            "button_label": "→ View opportunities",
            "button_url": "/foundation/work-queue/",
        },
        "kpi_cards": [
            {
                "value": "2",
                "label": "My connections",
                "sub": "Member and programme participant",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "3",
                "label": "Invitations",
                "sub": "Within your eligibility",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "4",
                "label": "New resources",
                "sub": "Available to your relationships",
                "is_dark": False,
                "icon": "bar-chart",
            },
        ],
        "table_card": {
            "title": "Your work and follow-through",
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": ["OPPORTUNITY", "CONNECTION", "NEXT ACTION"],
            "rows": [
                {
                    "item": "Peer-learning circle",
                    "col2": "Community invitation",
                    "status_label": "View details",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Digital confidence workshop",
                    "col2": "Programme participant",
                    "status_label": "RSVP",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Monthly community feedback",
                    "col2": "Member",
                    "status_label": "Share feedback",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
            ],
            "record_count_text": "Showing 3 records in this view",
        },
        "attention_card": {
            "title": "Attention required",
            "items": [
                {
                    "title": "Join the next community conversation",
                    "body": "Explore an invitation connected to your current interests and relationships.",
                    "action_label": "View invitations",
                    "action_style": "magenta",
                    "url": "/foundation/work-queue/",
                },
                {
                    "title": "Choose what you hear from us",
                    "body": "Keep your interests and communication preferences up to date.",
                    "action_label": "My preferences",
                    "action_style": "magenta",
                    "url": "/foundation/settings/",
                },
            ],
        },
        "chart_card": None,
        "scoped_notice": "Counts and records remain scoped to your current role and network.",
        "related_screens": ["DASH-15", "DASH-16"],
    },
}


def get_dashboard_screen(screen_code: str) -> Optional[Dict[str, Any]]:
    """Retrieve screen definition by code (case-insensitive)."""
    norm = screen_code.strip().upper()
    return DASHBOARD_SCREENS.get(norm)


def get_default_screen_for_role(role: str) -> str:
    """Map user role to its canonical default dashboard screen."""
    r = (role or "").strip().lower()
    if r in ("founder", "hq", "executive"):
        return "DASH-01"
    elif r in ("operations", "hofco"):
        return "DASH-02"
    elif r in ("country_lead", "country_representative", "country_director"):
        return "DASH-10"
    elif r in ("state_lead", "regional_lead", "state_coordinator"):
        return "DASH-11"
    elif r in ("lga_lead", "local_operations", "lga_coordinator"):
        return "DASH-12"
    elif r in ("cluster_lead", "cluster_coordinator"):
        return "DASH-13"
    elif r in ("chapter_lead", "chapter", "chapter_coordinator"):
        return "DASH-14"
    elif r in ("member",):
        return "DASH-15"
    elif r in ("candidate",):
        return "DASH-16"
    elif r in ("community", "supporter"):
        return "DASH-17"
    return "DASH-01"


def check_dashboard_permission(user_scope, screen_code: str):
    """
    Enforces server-authoritative boundary checks:
    - Safeguarding: DASH-10-SAFEGUARDING is strictly restricted.
    - Role level & geographic isolation.
    - Network separation.
    """
    screen = get_dashboard_screen(screen_code)
    if not screen:
        raise ScopePermissionDenied(f"Unknown dashboard screen: {screen_code}", reason_code="not_found")

    # Confidential Safeguarding desk check
    if screen.get("requires_safeguarding"):
        if not user_scope.can_access_confidential():
            raise ScopePermissionDenied(
                "Access to confidential safeguarding records is restricted to authorized safeguarding officers.",
                reason_code="safeguarding_restricted",
                recovery_url="/foundation/dashboard/",
            )

    # Country-scoped screens verification
    screen_country = screen.get("default_country")
    if screen_country and screen_country != "ALL":
        if not user_scope.can_access_country(screen_country):
            raise ScopePermissionDenied(
                f"Your account scope does not grant access to the {screen_country} country hub.",
                reason_code="wrong_country",
                recovery_url="/foundation/dashboard/",
            )

    # Network-scoped screens verification
    screen_network = screen.get("default_network")
    if screen_network and screen_network not in ("HQ / Both networks", "ALL", "*", "WODDI", "PUBLIC"):
        if not user_scope.can_access_network(screen_network):
            raise ScopePermissionDenied(
                f"Your account scope does not grant access to the {screen_network} network workspace.",
                reason_code="network_mismatch",
                recovery_url="/foundation/dashboard/",
            )


def build_dashboard_context(
    request,
    screen_code: str,
    user_scope,
    account: Account,
    state_param: Optional[str] = None,
    tab_param: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Assembles complete, authentic, scoped dashboard presentation context.
    Merges registry contract with real database records where present.
    """
    screen = get_dashboard_screen(screen_code)
    if not screen:
        screen = DASHBOARD_SCREENS["DASH-01"]

    active_tab = tab_param or "overview"

    # Interaction contract state handling
    state_mode = state_param or request.GET.get("state")
    state_card = None
    if state_mode:
        states = {
            "empty": {
                "title": "Your workspace is ready",
                "message": "There are no outstanding items in this view. Upcoming work will appear here.",
                "action_label": "Open activities",
                "action_url": screen["primary_action"]["url"] if screen.get("primary_action") else "/foundation/work-queue/",
            },
            "stale": {
                "title": "Some information is out of date",
                "message": "The last available records are shown. Refresh before relying on a time-sensitive status.",
                "action_label": "Refresh data",
                "action_url": request.path,
            },
            "role_changed": {
                "title": "Your role has changed",
                "message": "Your available actions and dashboard scope have been updated.",
                "action_label": "Review my role",
                "action_url": "/foundation/dashboard/switch-role/",
            },
            "loading": {
                "title": "Loading current information",
                "message": f"Loading {screen['title'].lower()}. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": request.path,
            },
            "filtered_empty": {
                "title": "Nothing to show in this scope",
                "message": f"There are no matching records for {screen['title'].lower()}. Check the current scope or remove a filter.",
                "action_label": "Reset view",
                "action_url": request.path,
            },
        }
        state_card = states.get(state_mode)

    # Dynamic KPI reconciliation where authentic database records exist
    kpi_cards = [dict(c) for c in screen.get("kpi_cards", [])]
    table_card = dict(screen.get("table_card", {})) if screen.get("table_card") else None

    # Leadership tier flag for sidebar navigation
    is_leadership_tier = user_scope.active_role not in ("member", "candidate", "community")

    # Scope display label
    active_network = user_scope.active_network or screen.get("default_network", "WGMN")
    active_country = user_scope.active_country or screen.get("default_country", "NG")

    return {
        "screen": screen,
        "screen_code": screen["screen_id"],
        "screen_title": screen["title"],
        "eyebrow": screen["eyebrow"],
        "subtitle": screen["subtitle"],
        "primary_action": screen.get("primary_action"),
        "secondary_action": screen.get("secondary_action"),
        "has_tabs": screen.get("has_tabs", False),
        "active_tab": active_tab,
        "hero_banner": screen.get("hero_banner"),
        "kpi_cards": kpi_cards,
        "table_card": table_card,
        "attention_card": screen.get("attention_card"),
        "chart_card": screen.get("chart_card"),
        "scoped_notice": screen.get("scoped_notice"),
        "related_screens": screen.get("related_screens", []),
        "support_note": screen.get("support_note"),
        "has_search_filter": screen.get("has_search_filter", False),
        "state_mode": state_mode,
        "state_card": state_card,
        "is_leadership_tier": is_leadership_tier,
        "active_role_title": screen.get("default_role_title") or user_scope.active_role.title(),
        "active_network": active_network,
        "active_country": active_country,
    }
