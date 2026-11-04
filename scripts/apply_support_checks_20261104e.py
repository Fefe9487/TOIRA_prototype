#!/usr/bin/env python3
"""Expert decision (item 7): link unreferenced supporting-equipment pre-use checks to same-group scenarios that name
the same equipment, as support (non-core) controls. Checks with no such scenario stay unreferenced.

Candidates: audit/unreferenced_controls.json rows with priorityDevices and ruleClass == unclassified.
Run once: python scripts/apply_support_checks_20261104e.py [--dry-run]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_equipment_fixes_20261104b import REPO, Editor  # noqa: E402

EQUIPMENT = {'堆高機': r'堆高機', '起重機': r'起重機|吊車|天車', '高空工作車': r'高空工作車|高空作業車',
             '營建機械': r'挖土機|土方車|夯實|鏟裝|整地機具|車輛|機具', '推車': r'推車|搬運車|台車', '吊籠': r'吊籠'}
PHASE = 8


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    e = Editor()
    prior = json.loads((REPO / 'audit' / 'equipment_fixes_20261104b.json').read_text(encoding='utf-8'))
    e.renames, e.avoid_remap, e.key_renames = prior['taskRenames'], prior['avoidIndexRemap'], prior['controlKeyRenames']
    start = len(prior['changes'])
    e.log = prior['changes']
    rows = [u for u in json.loads((REPO / 'audit' / 'unreferenced_controls.json').read_text(encoding='utf-8'))
            if u['priorityDevices'] and u['ruleClass'] == 'unclassified']
    linked = kept = 0
    for u in rows:
        families = [f for f, rx in EQUIPMENT.items() if re.search(rx, u['text'])]
        g, _ = e.group(u['taskName'], u['groupName'])
        assert g['AvoidItems'][int(u['id'][1:]) - 1] == u['text'], (u['taskName'], u['groupName'], u['id'])
        hits = [f'H{i}' for i, h in enumerate(g['hazardItems'], 1) if any(re.search(EQUIPMENT[f], h) for f in families)]
        if not (families and hits):
            kept += 1
            continue
        linked += 1
        for hid in hits:
            e.add_ref(u['taskName'], u['groupName'], hid, u['id'], False,
                      f"專家決定（第7項）：{'、'.join(families)}使用前檢查補引用至同群組提到同一設備的情境，作為支援措施")
    for c in e.log[start:]:
        c['phase'] = PHASE
    print({'candidates': len(rows), 'linked': linked, 'kept': kept, 'refsAdded': len(e.log) - start})
    e.finish(args.dry_run)


if __name__ == '__main__':
    main()
