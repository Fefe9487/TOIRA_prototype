#!/usr/bin/env python3
"""Phase 2 of 20261104b: Cursor-reviewed unreferenced mandatory-device checks (type A) and 營建用升降機 搬器 wording.

Appends to audit/equipment_fixes_20261104b.json (same TASK_RENAMES / AVOID_INDEX_REMAP / CONTROL_KEY_RENAMES
tables), so New.html keeps one migration step for 20261104b. Refuses to run twice (asserts current text).

Run once: python scripts/apply_equipment_fixes_20261104b_phase2.py [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_equipment_fixes_20261104b import REPO, Editor  # noqa: E402

RA = '原未引用的作業前檢查涵蓋過捲預防裝置或制動器，同作業沒有其他已引用措施涵蓋，補引用為支撐措施（Cursor 複核 A 類）'


def apply(e):
    e.add_ref('人字臂起重桿組裝與拆卸作業', '墜落、滾落', 'H1', 'A7', False,
              '情境以高空工作車為高處工作台；高空工作車每日作業前檢點制動、操作及作業裝置（管理辦法第50-1條）')
    e.add_ref('吊掛熔融金屬澆鑄桶作業', '物體飛落', 'H3', 'A1', False, RA + '；情境為起重機煞車、限位或起升機構失效')
    e.add_ref('塔式起重機升高及拆卸作業', '物體飛落', 'H2', 'A7', False, RA + '；情境含起重機承載不足致吊物墜落')
    e.add_ref('移動式起重機吊掛作業', '物體飛落', 'H2', 'A3', False, RA + '；情境為煞車及過負載裝置失效致起升失控')
    e.add_ref('鑄造模具吊掛作業', '物體飛落', 'H1', 'A1', False, RA + '；情境為起重機煞車、限位或控制機構失效')
    e.add_ref('電梯安裝作業', '物體飛落', 'H1', 'A6', False, '原未引用的吊運前吊具、鋼索、制動及防脫確認補引用至吊具失效情境')

    T = '營建用升降機組裝、拆卸及維修作業'
    e.replace_in_task(T, '吊籠', '搬器', '營建用升降機的載物載人部分法規稱「搬器」（起重升降機具安全規則第2條第4款；管理辦法第54-1條），'
                      '「吊籠」是另一種危險性機械', expect=EXPECT_HOIST)
    e.add_ref(T, '墜落、滾落', 'H2', 'A8', False, '原未引用的組拆維修前確認搬器及出入口門扉連鎖、制動器補引用至誤啟動情境')

    T = '鋼筋吊運作業'
    e.append_hazard(T, '物體飛落',
        '起重機過捲預防裝置、制動器或過負荷警報失效時，吊具捲過頭撞擊伸臂前端或吊物失控下降，造成鋼筋束墜落擊中人員。',
        5, ['A8', 'A6', 'A10'], ['A8', 'A10'],
        '原作業庫沒有起重機安全裝置失效情境，A8 原未引用；起重升降機具安全規則第27條、第15條（過捲預防裝置）')


EXPECT_HOIST = 0


def main():
    global EXPECT_HOIST
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--expect-hoist', type=int, required=True, help='fields containing 吊籠 in the hoist task')
    args = ap.parse_args()
    EXPECT_HOIST = args.expect_hoist
    e = Editor()
    prior = json.loads((REPO / 'audit' / 'equipment_fixes_20261104b.json').read_text(encoding='utf-8'))
    e.renames, e.avoid_remap, e.key_renames = prior['taskRenames'], prior['avoidIndexRemap'], prior['controlKeyRenames']
    start = len(prior['changes'])
    e.log = prior['changes']
    apply(e)
    for c in e.log[start:]:
        c['phase'] = 2
    e.finish(args.dry_run)


if __name__ == '__main__':
    main()
