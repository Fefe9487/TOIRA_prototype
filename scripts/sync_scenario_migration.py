#!/usr/bin/env python3
"""Keep scenarioMigration.json (20261005g -> 20261005h index map) aligned when scenarios are appended to its groups.

A scenario appended after 20261005h has no source in old saves: newSourceIndices gets [] and exactOldIndices null,
and its index is recorded in appendedIndices so validate_scenario_maps.py accepts the empty source.

Run: python scripts/sync_scenario_migration.py [--check]
"""
import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    library = json.loads((REPO / 'tasksLibrary.json').read_text(encoding='utf-8'))
    path = REPO / 'scenarioMigration.json'
    migration = json.loads(path.read_text(encoding='utf-8'))
    changed = []
    for item in migration['groups']:
        group = next(g for g in library[item['taskName']]['hazardGroups'] if g['groupName'] == item['groupName'])
        n_old, n_now = len(item['newSourceIndices']), len(group['hazardItems'])
        assert n_now >= n_old, (item['taskName'], item['groupName'], 'scenarios removed; needs a real migration')
        if n_now > n_old:
            item['newSourceIndices'] += [[] for _ in range(n_now - n_old)]
            item['exactOldIndices'] += [None] * (n_now - n_old)
            item['appendedIndices'] = sorted(set(item.get('appendedIndices', [])) | set(range(n_old, n_now)))
            changed.append(f"{item['taskName']}／{item['groupName']}: +{n_now - n_old}")
    if args.check:
        print('out of date:' if changed else 'current', changed)
        sys.exit(1 if changed else 0)
    if changed:
        with path.open('w', encoding='utf-8', newline='\r\n') as fh:
            fh.write(json.dumps(migration, ensure_ascii=False, indent=2) + '\n')
    print(changed or 'already current')


if __name__ == '__main__':
    main()
