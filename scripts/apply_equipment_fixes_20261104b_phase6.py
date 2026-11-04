#!/usr/bin/env python3
"""Phase 6 of 20261104b: remaining wording candidates from the equipment-task consistency pass, accepted after Cursor review.

Run once: python scripts/apply_equipment_fixes_20261104b_phase6.py [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_equipment_fixes_20261104b import REPO, Editor  # noqa: E402

RW = '本地 AI 一致性候選經 Cursor 複核採納'


def apply(e):
    e.replace_in_task('移動式起重機吊掛作業', '煞車及過負載裝置失效', '煞車及過負荷預防裝置失效',
                      RW + '：統一為法定用語「過負荷預防裝置」（起重升降機具安全規則第32條）', expect=1)
    e.replace_in_task('高空工作車作業', '長件、工具或吊運物料固定不良', '長件、工具或搬上工作台的物料固定不良',
                      RW + '：高空工作車不得作主要用途以外使用（設施規則第128-1條第6款），避免寫成吊運設備', expect=1)
    e.replace_in_task('鑄造模具吊掛作業', '排除夾滯', '排除卡滯', RW + '：錯字', expect=1)
    e.replace_in_task('高壓鍋爐操作作業', '噴及眼臉與手部', '噴及眼睛、臉部與手部', RW + '：錯字', expect=1)
    e.replace_in_task('高處繩索接近作業', '徒手拉掣受力繩索', '徒手拉扯受力繩索', RW + '：錯字', expect=1)
    e.replace_in_task('鋼筋吊運作業', '達風速或雷雨立即停吊', '達停止作業風速或遇雷雨立即停吊', RW + '：語句不完整', expect=1)


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
        c['phase'] = 6
    e.finish(args.dry_run)


if __name__ == '__main__':
    main()
