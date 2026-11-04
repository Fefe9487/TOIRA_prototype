#!/usr/bin/env python3
"""Expert decision (item 8): apply accepted control-lane changes from audit/label_review.json.

Only the trailing label changes, so saved checkbox keys (sentence without label) stay valid; P scoring of the
affected scenarios changes because the control moves from the engineering lane.
Run once: python scripts/apply_label_review_20261104f.py [--dry-run]
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_equipment_fixes_20261104b import REPO, Editor  # noqa: E402
from apply_expert_decisions_20261104d import patch_editor  # noqa: E402

PHASE = 9
SUFFIX = re.compile(r'[（(](工程改善|工程控制)[）)]\s*$')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    patch_editor()
    e = Editor()
    prior = json.loads((REPO / 'audit' / 'equipment_fixes_20261104b.json').read_text(encoding='utf-8'))
    e.renames, e.avoid_remap, e.key_renames = prior['taskRenames'], prior['avoidIndexRemap'], prior['controlKeyRenames']
    start = len(prior['changes'])
    e.log = prior['changes']
    review = json.loads((REPO / 'audit' / 'label_review.json').read_text(encoding='utf-8'))
    for item in review['items']:
        if item['decision'] != 'accepted':
            continue
        g, _ = e.group(item['taskName'], item['groupName'])
        old = g['AvoidItems'][int(item['id'][1:]) - 1]
        assert old == item['text'] and SUFFIX.search(old), (item['taskName'], item['groupName'], item['id'])
        new = SUFFIX.sub(f"({item['newLabel']})", old)
        e.set_control(item['taskName'], item['groupName'], item['id'], old, new,
                      f"專家決定（第8項）：本地 AI 建議 {item['aiLabel']}（信心 {item['confidence']}），Cursor 複核採納：{item['note']}"
                      + ('；此為必要設施，P 值判定隨之改變' if item['core'] else ''), allow_lane=True)
    for c in e.log[start:]:
        c['phase'] = PHASE
    print('label changes', len(e.log) - start)
    e.finish(args.dry_run)


if __name__ == '__main__':
    main()
