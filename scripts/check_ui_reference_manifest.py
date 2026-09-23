"""Verify frozen UI reference bytes; not a substitute for visual acceptance."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs' / 'approved-ui' / 'stage-02'


def main():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    expected = {f'AUTH-{screen:02d}-{variant}.html' for screen in range(1, 10)
                for variant in ('desktop', 'mobile', 'states')}
    recorded = manifest['files']
    actual = {p.name for p in BASE.glob('AUTH-*.html')}
    assert manifest['canonical_screens'] == 9
    assert set(manifest['variants_per_screen']) == {'desktop', 'mobile', 'states'}
    assert actual == expected, 'Canonical reference coverage changed'
    assert expected.issubset(recorded), 'Reference manifest is incomplete'
    for relative, expected_hash in recorded.items():
        target = (BASE / relative).resolve()
        assert target.is_relative_to(BASE.resolve()), 'Reference path escaped baseline'
        assert target.is_file(), f'Missing approved reference: {relative}'
        assert hashlib.sha256(target.read_bytes()).hexdigest() == expected_hash, (
            f'Approved reference changed without versioned approval: {relative}')
    print(f'Approved reference integrity: {len(expected)} screens/variants, {len(recorded)} files verified')
    print('Visual/state acceptance still requires Playwright/reference review and Rex approval.')


if __name__ == '__main__':
    main()
