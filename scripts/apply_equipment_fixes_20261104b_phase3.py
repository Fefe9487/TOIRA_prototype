#!/usr/bin/env python3
"""Phase 3 of 20261104b: local-AI candidates accepted after Cursor review (type A unreferenced controls),
plus the forklift head-guard scenario found while reviewing them.

Run once: python scripts/apply_equipment_fixes_20261104b_phase3.py [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_equipment_fixes_20261104b import REPO, Editor  # noqa: E402


def apply(e):
    T = '紫外線乾燥與烘烤設備操作作業'
    for hid in ('H2', 'H3'):
        e.add_ref(T, '火災', hid, 'A8', False,
                  '本地 AI 候選 A 類經 Cursor 複核採納：乾燥設備開機前確認排氣、溫度測定調整及內部配線，對應超溫與配線過熱情境')
    e.add_ref('營建用升降機組裝、拆卸及維修作業', '物體飛落', 'H1', 'A2', False,
              '本地 AI 候選 A 類經 Cursor 複核採納：吊車吊運構件時確認額定荷重、作業半徑及外伸撐座')

    T, G = '堆高機駕駛與搬運作業', '物體飛落'
    _, doc = e.group(T, G)
    severity = doc['hazardControlMap'][1]['severity']
    a = e.append_control(T, G, '堆高機設置強度及上框開口符合規定的頂蓬，不得拆除或改裝；頂蓬破損變形時停止使用。(工程改善)',
                         '機械設備器具安全標準第79條（註明限使用於貨物掉落無危害駕駛者之虞者除外）')
    e.append_hazard(T, G, '高位舉升、堆疊或取放貨物時，貨物自貨叉或堆疊處掉落，頂蓬缺失、拆除或強度不足，駕駛人頭部遭落物擊中。',
                    severity, [a, 'A3', 'A1', 'A7'], [a],
                    '原群組只有周邊人員被擊中的情境；頂蓬防護駕駛人的事故路徑沒有情境，原未引用的班前檢查（含頂蓬）A3 補引用')


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
        c['phase'] = 3
    e.finish(args.dry_run)


if __name__ == '__main__':
    main()
