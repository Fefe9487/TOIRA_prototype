#!/usr/bin/env python3
"""Rename 「吊籠作業」 to 「起重機吊掛搭乘設備載人作業」 (content already revised in 20261104a).

The legal 吊籠 (起重升降機具安全規則第2條第6款) is a different machine; the 20261104a revision rewrote this
task as crane-suspended personnel platforms but kept the old name. Only the task key / taskName,
scenarioMaps.taskName and industryMapping.taskId change; sentences stay byte-identical.
Also records the rename in audit/equipment_fixes_20261104b.json so New.html TASK_RENAMES stays in sync.

Run once: python scripts/rename_crane_basket_task_20261104b.py
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OLD, NEW = '吊籠作業', '起重機吊掛搭乘設備載人作業'


def load(name):
    return json.loads((REPO / name).read_text(encoding='utf-8'))


def main():
    library = load('tasksLibrary.json')
    maps = load('scenarioMaps.json')
    industry = load('industryMapping.json')
    fixes = load('audit/equipment_fixes_20261104b.json')
    assert OLD in library and NEW not in library
    assert '起重機吊掛或直結搭乘設備' in library[OLD]['taskdescribe'], 'expected the 20261104a crane-basket content'
    before = json.dumps(library[OLD], ensure_ascii=False, sort_keys=True)
    library = {(NEW if k == OLD else k): v for k, v in library.items()}
    library[NEW]['taskName'] = NEW
    after = json.loads(before)
    after['taskName'] = NEW
    assert library[NEW] == after
    groups = 0
    for d in maps['maps']:
        if d['taskName'] == OLD:
            d['taskName'] = NEW
            groups += 1
    rows = [r['id'] for r in industry if r['taskId'] == OLD]
    for r in industry:
        if r['taskId'] == OLD:
            r['taskId'] = NEW
    fixes['taskRenames'][OLD] = NEW
    fixes['changes'].append({'kind': 'rename_task', 'taskName': NEW, 'groupName': None, 'id': 'taskName',
                             'before': OLD, 'after': NEW,
                             'reason': '20261104a 已改寫為起重機吊掛搭乘設備載人內容但保留舊名；法定「吊籠」為另一種危險性機械'
                                       f'（起重升降機具安全規則第2條第6款）。情境圖 {groups} 組、industryMapping {len(rows)} 列（{"、".join(rows)}）同步，句子未改'})
    (REPO / 'tasksLibrary.json').write_text(json.dumps(library, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (REPO / 'scenarioMaps.json').write_text(json.dumps(maps, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (REPO / 'industryMapping.json').write_text(json.dumps(industry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (REPO / 'audit/equipment_fixes_20261104b.json').write_text(json.dumps(fixes, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(f'renamed: {groups} scenario groups, industry rows {rows}')


if __name__ == '__main__':
    main()
