#!/usr/bin/env python3
"""Rewrite the 20261104b migration tables in New.html from audit/equipment_fixes_20261104b.json.

Run: python scripts/sync_migration_tables.py [--check]
"""
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true', help='exit 1 if New.html is out of date')
    args = ap.parse_args()
    fixes = json.loads((REPO / 'audit' / 'equipment_fixes_20261104b.json').read_text(encoding='utf-8'))
    tables = {'TASK_RENAMES': fixes['taskRenames'], 'AVOID_INDEX_REMAP_20261104B': fixes['avoidIndexRemap'],
              'CONTROL_KEY_RENAMES_20261104B': fixes['controlKeyRenames']}
    path = REPO / 'New.html'
    html = path.read_text(encoding='utf-8')
    updated = html
    for name, value in tables.items():
        line = f'        const {name} = {json.dumps(value, ensure_ascii=False, separators=(", ", ": "))};'
        updated, n = re.subn(rf'^        const {name} = .*;$', lambda _: line, updated, count=1, flags=re.M)
        assert n == 1, name
    if args.check:
        sys.exit(0 if updated == html else 1)
    with path.open('w', encoding='utf-8', newline='') as fh:
        fh.write(updated)
    print('New.html tables', 'updated' if updated != html else 'already current')


if __name__ == '__main__':
    main()
