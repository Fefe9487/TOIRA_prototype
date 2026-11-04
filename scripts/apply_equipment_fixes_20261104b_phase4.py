#!/usr/bin/env python3
"""Phase 4 of 20261104b: further local-AI type-A candidates accepted after Cursor review.

Run once: python scripts/apply_equipment_fixes_20261104b_phase4.py [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_equipment_fixes_20261104b import REPO, Editor  # noqa: E402


def apply(e):
    e.add_ref('移動式起重機吊掛作業', '物體倒塌、崩塌', 'H1', 'A2', False,
              '本地 AI 候選 A 類經 Cursor 複核採納：起吊前確認伸臂及外伸撐座無損傷，對應外伸撐座失效致傾覆情境')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    e = Editor()
    prior = json.loads((REPO / 'audit' / 'equipment_fixes_20261104b.json').read_text(encoding='utf-8'))
    e.renames, e.avoid_remap, e.key_renames = prior['taskRenames'], prior['avoidIndexRemap'], prior['controlKeyRenames']
    start = len(prior['changes'])
    e.log = prior['changes']
    apply(e)
    for c in e.log[start:]:
        c['phase'] = 4
    e.finish(args.dry_run)


if __name__ == '__main__':
    main()
