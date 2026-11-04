#!/usr/bin/env python3
"""Phase 5 of 20261104b: wording / scope candidates from the local-AI consistency pass accepted after Cursor review.

Control-lane (label) suggestions are NOT applied here: changing a lane changes P scoring and is left to experts.

Run once: python scripts/apply_equipment_fixes_20261104b_phase5.py [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_equipment_fixes_20261104b import REPO, Editor  # noqa: E402

RW = '本地 AI 一致性候選經 Cursor 複核採納：用語修正，意思與控制層級不變'


def apply(e):
    e.replace_in_task('備料與簡易提升機操作作業', '停留在平台行程及吊運範圍內', '停留在搬器行程範圍內',
                      RW + '；簡易提升機沒有吊運範圍', expect=1)
    e.replace_in_task('使用升降機上下料件作業', '車門護門尚在動作時', '車門或護門尚在動作時', RW, expect=1)
    e.replace_in_task('吊掛熔融金屬澆鑄桶作業', '才可近距解鉤', '才可近距離解鉤', RW, expect=2)
    e.replace_in_task('堆高機駕駛與搬運作業', '調整後視及操作介面', '調整後視鏡及操作介面', RW, expect=1)
    e.replace_in_task('塔式起重機升高及拆卸作業', '塔吊', '塔式起重機', RW + '；統一使用作業名稱的設備用語', expect=2)

    T = '油壓升降平台作業'
    old = e.library[T]['taskdescribe']
    e.set_describe(T, old, old.replace('作業範圍包括平台檢查、載物進出、升降定位、轉運及收尾點檢；',
                                       '作業範圍包括平台檢查、載物進出、升降定位、轉運、收尾點檢，以及清潔、排除卡料與故障處置時的停機隔離；'),
                   '本地 AI 一致性候選經 Cursor 複核採納：既有被夾 H3、H4 情境涵蓋清潔與維修，作業範圍補列')
    T = '營建用升降機組裝、拆卸及維修作業'
    old = e.library[T]['taskdescribe']
    e.set_describe(T, old, old.replace('再依序進行基礎安裝、導軌架組立、',
                                       '再依序進行基礎安裝、導軌架組立（必要時以吊車吊運標準節及組件）、'),
                   '本地 AI 一致性候選經 Cursor 複核採納：既有物體飛落 H1 為吊車吊運情境，作業說明補列')


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
        c['phase'] = 5
    e.finish(args.dry_run)


if __name__ == '__main__':
    main()
