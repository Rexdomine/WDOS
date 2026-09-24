"""Unconfigured policy fails closed. Operator-provided policy is never seeded from previews."""
import hashlib
import json
from copy import deepcopy
from django.conf import settings


def current_policy():
    value = getattr(settings, 'WDOS_ONBOARDING_POLICY', None)
    if not isinstance(value, dict):
        return None
    required = ['version', 'approval_reference', 'privacy_notice', 'review_role', 'review_function']
    if any(not isinstance(value.get(k), str) or not value[k].strip() for k in required):
        return None
    result = deepcopy(value)
    for key in required:
        result[key] = result[key].strip()
    if len(result['version']) > 100 or len(result['approval_reference']) > 500:
        return None
    for collection, keys in [('eligibility', ['code', 'label', 'network', 'basis']), ('homes', ['code', 'label', 'network', 'country', 'region', 'district', 'kind'])]:
        rows = value.get(collection)
        if not isinstance(rows, list) or not rows:
            return None
        seen = set()
        normalized_rows = []
        for row in rows:
            if not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip() for k in keys):
                return None
            normalized = dict(row)
            for key in keys:
                normalized[key] = normalized[key].strip()
            if normalized['network'] not in ('WGMN', 'WNNN') or normalized['code'] in seen:
                return None
            seen.add(normalized['code'])
            normalized_rows.append(normalized)
        result[collection] = normalized_rows
        if collection == 'homes' and any(r['kind'] not in ('chapter', 'virtual') for r in normalized_rows):
            return None
    result['digest'] = hashlib.sha256(json.dumps(result, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()
    return result
