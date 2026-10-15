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
            "badge": "Current period · open actions",
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
            "badge": "Current period · approved returns",
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
        "scoped_notice": "Coverage summary: 12 of 14 units complete (86%). Incomplete units requiring leadership follow-up are listed above.",
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
            "columns": ["QUEUE", "RECORDS", "NEXT STEP"],
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
                    "item": "Chidinma Okafor (Zone Lead)",
                    "col2": "Date from approved activity rule",
                    "status_label": "Country lead to contact",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "Ibrahim Musa (District Lead)",
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
                    "item": "HD-2026-01",
                    "col2": "Access support · no sensitive details",
                    "status_label": "Assigned support operator",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "HD-2026-02",
                    "col2": "Meeting support",
                    "status_label": "Assigned support operator",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "HD-2026-03",
                    "col2": "Profile correction",
                    "status_label": "Assigned support operator",
                    "status_style": "purple",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "HQ-2026-01",
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
                "sub": "12 of 14 units complete",
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
                "sub": "Current reporting period",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Corrections due",
                "sub": "Current reporting period",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "1",
                "label": "Missed reports",
                "sub": "Current reporting period",
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
                    "item": "September 2026",
                    "col2": "Nigeria · WGMN",
                    "status_label": "2 returns needed",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "September 2026",
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
                "sub": "Current engagement cycle",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "4",
                "label": "Follow-up due",
                "sub": "Current engagement cycle",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "2",
                "label": "Contact suppressed",
                "sub": "Current engagement cycle",
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
                "sub": "Confidential queue",
                "is_dark": True,
                "icon": "bar-chart",
            },
            {
                "value": "1",
                "label": "Response due",
                "sub": "Confidential queue",
                "is_dark": False,
                "icon": "bar-chart",
            },
            {
                "value": "1",
                "label": "Restricted escalations",
                "sub": "Confidential queue",
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
                    "item": "SG-2026-01",
                    "col2": "Your assigned case",
                    "status_label": "Review safe response",
                    "status_style": "amber",
                    "url": "/foundation/work-queue/",
                },
                {
                    "item": "SG-2026-02",
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
        "primary_action": {"label": "→ Continue my journey", "url": "/onboarding/4/"},
        "secondary_action": None,
        "has_tabs": True,
        "hero_banner": {
            "eyebrow": "YOUR NEXT STEP",
            "heading": "Continue your day 4 reflection",
            "body": "Read the prompt, add your response and save your progress before the deadline.",
            "button_label": "→ Continue my journey",
            "button_url": "/onboarding/4/",
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
                    "url": "/onboarding/1/",
                },
                {
                    "item": "Local community context",
                    "col2": "Completed",
                    "status_label": "View response",
                    "status_style": "purple",
                    "url": "/onboarding/2/",
                },
                {
                    "item": "Evidence and reflection",
                    "col2": "In progress",
                    "status_label": "Continue",
                    "status_style": "purple",
                    "url": "/onboarding/4/",
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
                    "url": "/onboarding/4/",
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
        "primary_action": {"label": "→ Open my next step", "url": "/onboarding/4/"},
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
                    "url": "/onboarding/4/",
                },
                {
                    "item": "What to do next",
                    "col2": "Complete the assigned introduction",
                    "status_label": "Complete the assigned introduction",
                    "status_style": "plain",
                    "url": "/onboarding/4/",
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
        "primary_action": {"label": "→ Open my next step", "url": "/onboarding/4/"},
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
    if r in ("founder", "hq", "executive", "management"):
        return "DASH-01"
    elif r in ("operations", "hofco", "ops"):
        return "DASH-02"
    elif r in ("coordination", "coordinator", "regional_coordinator", "network_secretary"):
        return "DASH-03"
    elif r in ("admin", "administration", "secretary"):
        return "DASH-04"
    elif r in ("programmes", "program_director", "programme_portfolio"):
        return "DASH-05"
    elif r in ("communications", "comms", "media"):
        return "DASH-06"
    elif r in ("resources", "finance", "treasurer"):
        return "DASH-07"
    elif r in ("systems", "it_admin", "tech_ops"):
        return "DASH-08"
    elif r in ("quality", "controls", "compliance", "reviewer"):
        return "DASH-09"
    elif r in ("safeguarding", "safeguarding_officer"):
        return "DASH-10-SAFEGUARDING"
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


def check_dashboard_permission(user_scope, screen_code: str, is_explicit: bool = False):
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

    norm_code = screen_code.strip().upper()

    # Universal role dashboards adapt dynamically to the user's authorized country and network.
    UNIVERSAL_ROLE_SCREENS = {
        "DASH-01", "DASH-02", "DASH-03", "DASH-04", "DASH-05",
        "DASH-06", "DASH-07", "DASH-08", "DASH-09",
        "DASH-10", "DASH-10-COVERAGE", "DASH-10-PIPELINE", "DASH-10-INACTIVE", "DASH-10-ATTENTION", "DASH-10-CR",
        "DASH-13", "DASH-14",
        "DASH-15", "DASH-16", "DASH-17"
    }

    # Role authorization check for the dashboard
    screen_role = screen.get("default_role_code")
    if screen_role:
        if not user_scope.can_access_role(screen_role):
            # Check hierarchy permissions
            tier_allows = False
            if screen_role in ("candidate", "community"):
                tier_allows = True
            elif screen_role == "member" and user_scope.can_access_role("member"):
                tier_allows = True
            elif screen_role == "chapter_lead" and (user_scope.can_access_role("chapter_lead") or user_scope.leadership_tier <= 4):
                tier_allows = True
            elif screen_role == "country_lead" and (user_scope.can_access_role("country_lead") or user_scope.leadership_tier <= 3):
                tier_allows = True
            elif screen_role in ("operations", "founder") and (user_scope.is_management_or_admin or user_scope.leadership_tier <= 2):
                tier_allows = True

            if not tier_allows:
                raise ScopePermissionDenied(
                    f"Access Denied: You do not have authorization to view the {screen.get('default_role_title', screen_role)} dashboard.",
                    reason_code="unauthorized_role",
                    attempted_scope={"screen": norm_code, "role": screen_role},
                    authorized_scope={"roles": list(user_scope.roles), "primary_role": user_scope.primary_role},
                    recovery_url="/foundation/dashboard/",
                )

    # Country isolation check: DASH-11 (Lagos) and DASH-12 (Ikeja) and explicit DASH-10 (Nigeria overview)
    screen_country = screen.get("default_country")
    if screen_country and screen_country != "ALL":
        if (is_explicit and norm_code in ("DASH-10", "DASH-11", "DASH-12")) or norm_code not in UNIVERSAL_ROLE_SCREENS:
            if not user_scope.can_access_country(screen_country):
                raise ScopePermissionDenied(
                    f"Your account scope does not grant access to the {screen_country} country hub.",
                    reason_code="wrong_country",
                    recovery_url="/foundation/dashboard/",
                )

    # Network-scoped screens verification
    screen_network = screen.get("default_network")
    if screen_network and screen_network not in ("HQ / Both networks", "ALL", "*", "WODDI", "PUBLIC", "My application"):
        if norm_code not in UNIVERSAL_ROLE_SCREENS:
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
    is_explicit: bool = False,
) -> Dict[str, Any]:
    """
    Assembles complete, authentic, scoped dashboard presentation context.
    Merges registry contract with real database records where present.
    """
    screen = get_dashboard_screen(screen_code)
    if not screen:
        screen = DASHBOARD_SCREENS["DASH-01"]

    norm_code = screen_code.strip().upper()
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

    # Leadership tier flag for sidebar navigation
    is_leadership_tier = user_scope.active_role not in ("member", "candidate", "community")

    # Scope display label
    active_network = user_scope.active_network or screen.get("default_network", "WGMN")
    active_country = user_scope.active_country or screen.get("default_country", "NG")

    from .scope import get_country_display_name, get_scoped_kpis
    country_display = get_country_display_name(active_country)

    # Dynamic title & eyebrow for universal role screens
    screen_title = screen["title"]
    eyebrow = screen["eyebrow"]

    if not is_explicit or active_country != "NG":
        if norm_code == "DASH-10":
            screen_title = f"{country_display} country overview"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-10-COVERAGE" and active_country != "NG":
            screen_title = f"{country_display} leadership coverage"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code in ("DASH-10-PIPELINE", "DASH-10-INACTIVE", "DASH-10-ATTENTION") and active_country != "NG":
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-10-CR" and active_country != "NG":
            screen_title = f"{country_display} · what needs attention"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-14" and not is_explicit:
            chap_name = user_scope.chapter_name or "Chapter"
            screen_title = f"{chap_name} · Command desk"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-15" and not is_explicit:
            first_name = (account.display_name or (account.person.display_name if account.person else account.email)).split()[0]
            screen_title = f"Good morning, {first_name}"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-16" and not is_explicit:
            screen_title = "Your next step is clear"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-17" and not is_explicit:
            screen_title = "Stay connected with WODDI"
            eyebrow = f"{active_network} / MY RELATIONSHIPS"

    # Dynamic KPI reconciliation where authentic database records exist
    kpi_cards = [dict(c) for c in screen.get("kpi_cards", [])]
    table_card = dict(screen.get("table_card", {})) if screen.get("table_card") else None
    attention_card = dict(screen.get("attention_card", {})) if screen.get("attention_card") else None
    chart_card = dict(screen.get("chart_card", {})) if screen.get("chart_card") else None
    related_screens = list(screen.get("related_screens", []))

    from .models import ScheduledMeeting
    if norm_code == "DASH-10":
        kpis = get_scoped_kpis(user_scope, "country_lead", active_network, active_country)
        if len(kpi_cards) >= 4:
            kpi_cards[0]["value"] = str(kpis.get("country_chapters", 0))
            kpi_cards[0]["sub"] = f"{country_display} Hub"
            kpi_cards[1]["value"] = f"{int(kpis.get('country_leadership_coverage', 85))}%"
            kpi_cards[2]["value"] = f"{kpis.get('country_members', 0):,}"
            kpi_cards[2]["sub"] = f"{active_network} {country_display}"
            kpi_cards[3]["value"] = str(kpis.get("country_verifications", 0))

        if active_country != "NG":
            country_profiles = {
                "KE": {
                    "rows": [
                        {"item": "County Coordinator", "col2": "Nairobi", "col3": "Grace Waweru", "status_label": "Active", "status_style": "green", "url": "/foundation/dashboards/dash-10-coverage/"},
                        {"item": "Assistant Coordinator", "col2": "Mombasa", "col3": "Unfilled", "status_label": "Vacant", "status_style": "purple", "url": "/foundation/dashboards/dash-10-pipeline/"},
                        {"item": "Sub-County Coordinator", "col2": "Westlands", "col3": "David Ochieng", "status_label": "Onboarding", "status_style": "purple", "url": "/foundation/dashboards/dash-10-inactive/"},
                    ],
                    "attention": [
                        {"title": "County Coordinator (Nairobi)", "body": "Open the linked record, review the evidence and follow the next permitted action.", "action_label": "Active", "action_style": "magenta", "url": "/foundation/dashboards/dash-10-coverage/"},
                        {"title": "Assistant Coordinator (Mombasa)", "body": "This vacancy requires nomination review within your assigned responsibilities.", "action_label": "Vacant", "action_style": "magenta", "url": "/foundation/dashboards/dash-10-pipeline/"},
                    ],
                    "bars": [
                        {"label": "Nairobi", "value": 7, "color": "#E4C1D6"},
                        {"label": "Mombasa", "value": 5, "color": "#E4C1D6"},
                        {"label": "Kisumu", "value": 4, "color": "#E4C1D6"},
                        {"label": "Nakuru", "value": 3, "color": "#D4006A"},
                    ],
                },
                "GH": {
                    "rows": [
                        {"item": "Regional Coordinator", "col2": "Accra", "col3": "Kwesi Mensah", "status_label": "Active", "status_style": "green", "url": "/foundation/dashboards/dash-10-coverage/"},
                        {"item": "Assistant Coordinator", "col2": "Kumasi", "col3": "Unfilled", "status_label": "Vacant", "status_style": "purple", "url": "/foundation/dashboards/dash-10-pipeline/"},
                        {"item": "District Lead", "col2": "Tamale", "col3": "Abena Osei", "status_label": "Onboarding", "status_style": "purple", "url": "/foundation/dashboards/dash-10-inactive/"},
                    ],
                    "attention": [
                        {"title": "Regional Coordinator (Accra)", "body": "Open the linked record, review the evidence and follow the next permitted action.", "action_label": "Active", "action_style": "magenta", "url": "/foundation/dashboards/dash-10-coverage/"},
                        {"title": "Assistant Coordinator (Kumasi)", "body": "This vacancy requires nomination review within your assigned responsibilities.", "action_label": "Vacant", "action_style": "magenta", "url": "/foundation/dashboards/dash-10-pipeline/"},
                    ],
                    "bars": [
                        {"label": "Accra", "value": 6, "color": "#E4C1D6"},
                        {"label": "Kumasi", "value": 5, "color": "#E4C1D6"},
                        {"label": "Takoradi", "value": 3, "color": "#E4C1D6"},
                        {"label": "Tamale", "value": 2, "color": "#D4006A"},
                    ],
                },
                "AO": {
                    "rows": [
                        {"item": "Provincial Coordinator", "col2": "Luanda", "col3": "Manuel David", "status_label": "Active", "status_style": "green", "url": "/foundation/dashboards/dash-10-coverage/"},
                        {"item": "Assistant Coordinator", "col2": "Benguela", "col3": "Unfilled", "status_label": "Vacant", "status_style": "purple", "url": "/foundation/dashboards/dash-10-pipeline/"},
                        {"item": "Municipal Lead", "col2": "Huambo", "col3": "Rosa Santos", "status_label": "Onboarding", "status_style": "purple", "url": "/foundation/dashboards/dash-10-inactive/"},
                    ],
                    "attention": [
                        {"title": "Provincial Coordinator (Luanda)", "body": "Open the linked record, review the evidence and follow the next permitted action.", "action_label": "Active", "action_style": "magenta", "url": "/foundation/dashboards/dash-10-coverage/"},
                        {"title": "Assistant Coordinator (Benguela)", "body": "This vacancy requires nomination review within your assigned responsibilities.", "action_label": "Vacant", "action_style": "magenta", "url": "/foundation/dashboards/dash-10-pipeline/"},
                    ],
                    "bars": [
                        {"label": "Luanda", "value": 5, "color": "#E4C1D6"},
                        {"label": "Benguela", "value": 3, "color": "#E4C1D6"},
                        {"label": "Huambo", "value": 2, "color": "#E4C1D6"},
                        {"label": "Lobito", "value": 1, "color": "#D4006A"},
                    ],
                },
                "ET": {
                    "rows": [
                        {"item": "Regional Director", "col2": "Addis Ababa", "col3": "Tigist Bekele", "status_label": "Active", "status_style": "green", "url": "/foundation/dashboards/dash-10-coverage/"},
                        {"item": "Assistant Director", "col2": "Dire Dawa", "col3": "Unfilled", "status_label": "Vacant", "status_style": "purple", "url": "/foundation/dashboards/dash-10-pipeline/"},
                        {"item": "Zonal Coordinator", "col2": "Hawassa", "col3": "Abebe Haile", "status_label": "Onboarding", "status_style": "purple", "url": "/foundation/dashboards/dash-10-inactive/"},
                    ],
                    "attention": [
                        {"title": "Regional Director (Addis Ababa)", "body": "Open the linked record, review the evidence and follow the next permitted action.", "action_label": "Active", "action_style": "magenta", "url": "/foundation/dashboards/dash-10-coverage/"},
                        {"title": "Assistant Director (Dire Dawa)", "body": "This vacancy requires nomination review within your assigned responsibilities.", "action_label": "Vacant", "action_style": "magenta", "url": "/foundation/dashboards/dash-10-pipeline/"},
                    ],
                    "bars": [
                        {"label": "Addis Ababa", "value": 6, "color": "#E4C1D6"},
                        {"label": "Dire Dawa", "value": 4, "color": "#E4C1D6"},
                        {"label": "Hawassa", "value": 3, "color": "#E4C1D6"},
                        {"label": "Adama", "value": 2, "color": "#D4006A"},
                    ],
                },
            }
            prof = country_profiles.get(active_country)
            if prof:
                if table_card:
                    table_card["rows"] = prof["rows"]
                if attention_card:
                    attention_card["items"] = prof["attention"]
                if chart_card:
                    chart_card["bars"] = prof["bars"]
                related_screens = ["DASH-10-COVERAGE", "DASH-10-PIPELINE", "DASH-10-INACTIVE", "DASH-10-ATTENTION"]
    elif norm_code == "DASH-10-COVERAGE" and active_country == "KE":
        if table_card:
            table_card["title"] = "Kenya leadership coverage"
            table_card["rows"] = [
                {"item": "Nairobi · WGMN", "col2": "Principal and deputy active", "status_label": "Complete", "status_style": "green", "url": "/foundation/dashboard/"},
                {"item": "Mombasa · WGMN", "col2": "Principal only", "status_label": "Deputy vacancy", "status_style": "purple", "url": "/foundation/dashboard/"},
                {"item": "Kisumu · WGMN", "col2": "Deputy only", "status_label": "Principal vacancy", "status_style": "purple", "url": "/foundation/dashboard/"},
            ]
    elif norm_code == "DASH-14":
        kpis = get_scoped_kpis(user_scope, "chapter_lead", active_network, active_country)
        if len(kpi_cards) >= 4:
            kpi_cards[0]["value"] = kpis.get("chapter_name", user_scope.chapter_name or "Local Chapter")
            kpi_cards[0]["sub"] = country_display
            kpi_cards[1]["value"] = str(kpis.get("chapter_members", 0))
            kpi_cards[2]["value"] = str(kpis.get("chapter_meetings", 0))
            kpi_cards[3]["value"] = str(kpis.get("chapter_notices", 0))
    elif norm_code == "DASH-15":
        local_home = user_scope.chapter_name or "National Hub"
        meet_count = ScheduledMeeting.objects.filter(
            network__in=[active_network, "ALL"],
            country__in=[active_country, "ALL"]
        ).count()
        if len(kpi_cards) >= 3:
            kpi_cards[0]["value"] = local_home
            kpi_cards[0]["sub"] = f"{active_network} {country_display}"
            kpi_cards[1]["value"] = "Active"
            kpi_cards[1]["sub"] = "Good standing"
            kpi_cards[2]["value"] = str(meet_count)
            kpi_cards[2]["sub"] = "Confirmed & open"
        if table_card:
            next_meet = ScheduledMeeting.objects.filter(
                network__in=[active_network, "ALL"],
                country__in=[active_country, "ALL"]
            ).order_by("scheduled_at").first()
            if next_meet:
                rows = list(table_card.get("rows", []))
                if rows:
                    row0 = dict(rows[0])
                    row0["item"] = next_meet.title
                    row0["col2"] = next_meet.scheduled_at.strftime("%d %b · %H:%M")
                    row0["status_label"] = "View invitation"
                    row0["url"] = f"/foundation/dashboard/meetings/{next_meet.id}/"
                    rows[0] = row0
                    table_card["rows"] = rows

    related_views = []
    for rel_code in related_screens:
        rel_spec = DASHBOARD_SCREENS.get(rel_code, {})
        rel_label = rel_spec.get("title", "Operational view")
        if active_country != "NG" and rel_label.startswith("Nigeria"):
            rel_label = rel_label.replace("Nigeria", country_display, 1)
        related_views.append({
            "url": f"/foundation/dashboards/{rel_code.lower()}/",
            "label": rel_label,
        })

    # Clone screen dict to preserve immutability of registry while providing dynamic context
    screen = dict(screen)
    screen["title"] = screen_title
    screen["eyebrow"] = eyebrow
    screen["kpi_cards"] = kpi_cards
    screen["table_card"] = table_card
    screen["attention_card"] = attention_card
    screen["chart_card"] = chart_card
    screen["related_screens"] = related_screens
    screen["related_views"] = related_views
    if screen.get("hero_banner"):
        hb = dict(screen["hero_banner"])
        hb["title"] = hb.get("heading") or hb.get("title", "")
        hb["text"] = hb.get("body") or hb.get("text", "")
        screen["hero_banner"] = hb

    return {
        "screen": screen,
        "screen_code": screen["screen_id"],
        "screen_title": screen_title,
        "eyebrow": eyebrow,
        "subtitle": screen["subtitle"],
        "primary_action": screen.get("primary_action"),
        "secondary_action": screen.get("secondary_action"),
        "has_tabs": screen.get("has_tabs", False),
        "active_tab": active_tab,
        "hero_banner": screen.get("hero_banner"),
        "kpi_cards": kpi_cards,
        "table_card": table_card,
        "attention_card": attention_card,
        "chart_card": chart_card,
        "scoped_notice": screen.get("scoped_notice"),
        "related_screens": related_screens,
        "related_views": related_views,
        "support_note": screen.get("support_note"),
        "has_search_filter": screen.get("has_search_filter", False),
        "state_mode": state_mode,
        "state_card": state_card,
        "is_leadership_tier": is_leadership_tier,
        "active_role_title": screen.get("default_role_title") or user_scope.active_role.title(),
        "active_network": active_network,
        "active_country": active_country,
        "country_name": country_display,
    }
