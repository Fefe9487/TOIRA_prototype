#!/usr/bin/env python3
"""Deterministic quality audit for tasksLibrary / scenarioMaps / industryMapping / page migration.

Run: python scripts/audit_equipment_quality.py [--json audit/equipment_quality.json] [--strict]

Hard failures (exit 1): duplicate task keys/names, missing groups, scenario text mismatch, invalid or
orphan control refs, core refs outside controlRefs, industryMapping / migration pointing at missing tasks,
renamed task names still present.  Everything else is reported as review candidates; --strict also fails
on mandatory-device coverage gaps.
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAX_CONTROL_CHARS = 100

HAZARD_TYPES = {'墜落、滾落', '跌倒', '衝撞', '物體飛落', '物體倒塌、崩塌', '被撞', '被夾、被捲', '被切、割、擦傷',
                '踩踏', '溺斃', '高低溫接觸', '有害物接觸', '感電', '爆炸', '物體破裂', '火災', '不當動作',
                '職業病', '其他類別風險'}

PRIORITY_DEVICES = {
    '過捲預防裝置': r'過捲',
    '制動器': r'制動|煞車',
    '過負荷預防裝置': r'過負荷|超載預防|荷重限制',
    '安全連鎖': r'連鎖|聯鎖',
    '緊急停止裝置': r'緊急停止|急停',
    '防墜及防脫裝置': r'防墜|防脫|防止脫落|捕捉裝置',
    '壓力釋放與超壓保護': r'安全閥|洩壓|釋壓|破裂板|超壓',
    '火災爆炸及有害氣體監測': r'偵測|監測|測定|警報器|氣體濃度',
}

# Equipment families whose legal category differs. A task "owns" a family when its name or description
# names it; texts of other tasks naming a family they do not own are reported as mixing candidates.
EQUIPMENT = {
    '簡易提升機': r'簡易提升機|簡易升降機',
    '營建用提升機': r'營建用提升機',
    '營建用升降機': r'營建用升降機',
    '升降機': r'(?<!簡易)(?<!營建用)升降機(?!構)',
    '吊籠': r'吊籠',
    '起重機吊掛搭乘設備': r'搭乘設備',
    '固定式起重機': r'固定式起重機|架空起重機|天車',
    '移動式起重機': r'移動式起重機|吊卡車|卡車起重機',
    '塔式起重機': r'塔式起重機',
    '人字臂起重桿': r'人字臂',
    '高空工作車': r'高空工作車|高空作業車',
    '堆高機': r'堆高機',
    '吊掛用具': r'吊掛用具|卸克|卸扣|吊鉤|吊索|吊鏈',
    '油壓升降平台': r'油壓升降平台|升降平台|升降台',
    '游離輻射': r'游離輻射|射源|放射性',
    '鍋爐壓力容器': r'鍋爐|壓力容器',
}
# Families that may legitimately appear as supporting equipment in any task.
GENERIC_SUPPORT = {'堆高機', '高空工作車', '移動式起重機', '油壓升降平台'}
# Families implied by owning another family (e.g. any crane task uses rigging gear).
IMPLIES = {
    '固定式起重機': {'吊掛用具'}, '移動式起重機': {'吊掛用具'}, '塔式起重機': {'吊掛用具', '移動式起重機'},
    '人字臂起重桿': {'吊掛用具', '移動式起重機'}, '吊籠': {'吊掛用具'},
    '起重機吊掛搭乘設備': {'吊掛用具', '移動式起重機', '固定式起重機'},
    '營建用升降機': {'升降機', '吊掛用具'}, '升降機': set(), '簡易提升機': set(),
}

# Mandatory devices / management items per owned equipment, each with its verified legal source.
MANDATORY = {
    '簡易提升機': [
        ('過捲預防裝置', r'過捲', '起重升降機具安全規則第95條；職業安全衛生管理辦法第25條'),
        ('制動性能檢點', r'制動|煞車', '職業安全衛生管理辦法第57條'),
        ('不得搭乘人員', r'禁止(人員)?搭乘|不得搭乘|僅供物料', '起重升降機具安全規則第96條'),
        ('不得超過積載荷重', r'超過額定|超載|額定載重|積載荷重', '起重升降機具安全規則第93條'),
    ],
    '升降機': [
        ('出入口門連鎖', r'連鎖|聯鎖', '職業安全衛生設施規則第93條、第95條'),
        ('終點極限開關／緊急停止', r'終點極限|極限開關|急停|緊急停止', '職業安全衛生設施規則第96條；起重升降機具安全規則第77條'),
        ('設計上專供載貨用者不得搭載人員', r'專供載貨用.*不得搭載人員', '起重升降機具安全規則第78條'),
        ('不得超過積載荷重', r'超過額定|超載|額定(荷|載)重|積載荷重', '起重升降機具安全規則第74條'),
    ],
    '吊籠': [
        ('不得超過積載荷重', r'積載荷重|超載', '起重升降機具安全規則第97條'),
        ('懸吊固定處支撐強度確認', r'強度|結構圖', '起重升降機具安全規則第99條'),
        ('運轉中操作人員不得擅離', r'擅離|不得離開', '起重升降機具安全規則第101條'),
        ('安全帽及全身背負式安全帶', r'全身背負式安全帶', '起重升降機具安全規則第102條'),
        ('下方危險區域管制及警告標示', r'管制|警戒|禁止.*進入', '起重升降機具安全規則第103條'),
        ('惡劣氣候停止作業', r'強風|大雨|風速', '起重升降機具安全規則第104條'),
    ],
    '貨用油壓升降平台': [
        ('禁止人員搭乘', r'禁止(人員)?搭乘|不得搭(載|乘)', '依設備設計用途；屬簡易提升機或載貨用升降機時另依起重升降機具安全規則第96條、第78條'),
        ('不得超過額定載重', r'額定載重|載重|超載', '依製造商銘牌；屬起重升降機具時另依起重升降機具安全規則第74條、第93條'),
    ],
    '人字臂起重桿': [
        ('過捲預防裝置', r'過捲', '起重升降機具安全規則第43條；職業安全衛生管理辦法第54條'),
        ('制動裝置', r'制動', '起重升降機具安全規則第52條'),
    ],
    '高空工作車': [
        ('外伸撐座完全伸出', r'外伸撐座', '職業安全衛生設施規則第128-1條第2款'),
        ('工作台人員安全帽及全身背負式安全帶', r'全身背負式安全帶', '職業安全衛生設施規則第128-1條第7款'),
        ('特殊作業安全衛生教育訓練人員操作', r'特殊作業安全衛生教育訓練', '職業安全衛生設施規則第128-9條'),
        ('每日作業前檢點制動、操作及作業裝置', r'制動', '職業安全衛生管理辦法第50-1條'),
    ],
    '堆高機': [
        ('不得超過最大荷重', r'最大荷重|額定荷重|銘牌荷重|超載', '職業安全衛生設施規則第127條'),
        ('除乘坐席位外不得搭載勞工', r'載人|搭載|搭乘|站在貨叉', '職業安全衛生設施規則第116條第2款、第10款'),
        ('頂蓬', r'頂蓬', '機械設備器具安全標準第79條'),
        ('後扶架（擋貨架）', r'後扶架|擋貨架', '職業安全衛生設施規則第124條'),
    ],
}

# Mandatory coverage is only checked where the task's main equipment is unambiguous.
MANDATORY_SCOPE = {
    '備料與簡易提升機操作作業': ['簡易提升機'],
    '使用升降機上下料件作業': ['升降機'],
    '人字臂起重桿組裝與拆卸作業': ['人字臂起重桿'],
    '高空工作車作業': ['高空工作車'],
    '堆高機駕駛與搬運作業': ['堆高機'],
    '油壓升降平台作業': ['貨用油壓升降平台'],
    '剪叉式升降台作業': ['貨用油壓升降平台'],
    '建築物外牆吊籠清洗及維護作業': ['吊籠'],
}

# Task-name -> owned family overrides, where the name alone is not explicit.
OWNED_OVERRIDE = {
    '油壓升降平台作業': {'油壓升降平台'},
    '備料與簡易提升機操作作業': {'簡易提升機', '油壓升降平台'},
    '使用升降機上下料件作業': {'升降機'},
    '電梯安裝作業': {'升降機'},
    # 20261104a 改寫為起重機吊掛搭乘設備；說明中的「吊籠」只用來區分法定吊籠。
    '移動式起重機搭乘設備載人高處作業': {'起重機吊掛搭乘設備'},
}

LABEL_RE = re.compile(r'[（(]\s*(消除|取代|工程改善|工程控制|行政管理|管理控制|個人防護具|個人防護)[^）)]*[）)]\s*$')


B_RULE_COVERAGE = 0.6


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def bigrams(text):
    s = re.sub(r'[\s，。、；：「」]', '', LABEL_RE.sub('', text or ''))
    return {s[i:i + 2] for i in range(len(s) - 1)}


def body(text):
    return re.sub(r'\s+', '', LABEL_RE.sub('', text or ''))


def page_constants(html):
    ver = re.search(r"const DATA_VER = '([^']+)'", html).group(1)
    renames = {}
    m = re.search(r'const TASK_RENAMES = (\{[\s\S]*?\});', html)
    if m:
        renames = json.loads(m.group(1).replace("'", '"'))
    return ver, renames


def owned_families(task):
    if task['taskName'] in OWNED_OVERRIDE:
        owned = set(OWNED_OVERRIDE[task['taskName']])
    else:
        head = task['taskName'] + task['taskdescribe']
        owned = {fam for fam, rx in EQUIPMENT.items() if re.search(rx, head)}
    for fam in list(owned):
        owned |= IMPLIES.get(fam, set())
    return owned


def audit(repo):
    library = read(repo / 'tasksLibrary.json')
    maps = read(repo / 'scenarioMaps.json')
    industry = read(repo / 'industryMapping.json')
    migration = read(repo / 'scenarioMigration.json')
    new_html = (repo / 'New.html').read_text(encoding='utf-8')
    sel_html = (repo / 'Selection.html').read_text(encoding='utf-8')
    data_ver, renames = page_constants(new_html)
    fail, warn = [], collections.defaultdict(list)
    docs = {}
    for d in maps['maps']:
        key = (d['taskName'], d['groupName'])
        if key in docs:
            fail.append(f'duplicate scenario map group {key}')
        docs[key] = d

    # 1. task identity
    names = collections.Counter(t['taskName'] for t in library.values())
    for k, t in library.items():
        if k != t['taskName']:
            fail.append(f'task key/name differ: {k} / {t["taskName"]}')
    fail += [f'duplicate taskName {n}' for n, c in names.items() if c > 1]
    normed = collections.defaultdict(list)
    for n in names:
        normed[re.sub(r'[與及、／/()（）\s]|作業$', '', n)].append(n)
    warn['nearDuplicateTaskNames'] = [v for v in normed.values() if len(v) > 1]

    # 2-5. groups, scenarios, controls, core refs
    stats = collections.Counter()
    unreferenced = []
    for name, task in library.items():
        gnames = [g['groupName'] for g in task['hazardGroups']]
        if len(gnames) != len(set(gnames)):
            fail.append(f'duplicate group in {name}')
        for g in task['hazardGroups']:
            key = (name, g['groupName'])
            stats['groups'] += 1
            if g['groupName'] not in HAZARD_TYPES:
                warn['nonStandardGroupName'].append(key)
            if not g['hazardItems'] or not g['AvoidItems']:
                fail.append(f'empty hazards/controls {key}')
            doc = docs.get(key)
            if not doc:
                fail.append(f'missing scenario map {key}')
                continue
            rows = doc['hazardControlMap']
            if [r['hazardItem'] for r in rows] != g['hazardItems']:
                fail.append(f'scenario text/order mismatch {key}')
            used = set()
            for i, r in enumerate(rows, 1):
                stats['hazards'] += 1
                refs, cores = r['controlRefs'], r['coreControlRefs']
                stats['controlRefs'] += len(refs)
                for ref in refs:
                    m = re.fullmatch(r'A([1-9]\d*)', ref)
                    if not m or int(m.group(1)) > len(g['AvoidItems']) or not g['AvoidItems'][int(m.group(1)) - 1].strip():
                        fail.append(f'invalid control ref {key} H{i} {ref}')
                if len(refs) != len(set(refs)):
                    fail.append(f'duplicate control ref {key} H{i}')
                if not set(cores) <= set(refs):
                    fail.append(f'core ref outside controlRefs {key} H{i}')
                if not cores:
                    warn['scenarioWithoutCore'].append(f'{name}／{g["groupName"]}／H{i}')
                if len(cores) > 3:
                    warn['scenarioWithManyCores'].append(f'{name}／{g["groupName"]}／H{i}：{len(cores)}')
                used |= set(refs)
            bodies = collections.defaultdict(list)
            used_grams = set().union(*(bigrams(g['AvoidItems'][int(r[1:]) - 1]) for r in used)) if used else set()
            for i, a in enumerate(g['AvoidItems'], 1):
                stats['controls'] += 1
                if not LABEL_RE.search(a):
                    warn['controlWithoutLabel'].append(f'{name}／{g["groupName"]}／A{i}')
                if len(body(a)) > MAX_CONTROL_CHARS:
                    fail.append(f'control body over {MAX_CONTROL_CHARS} chars: {name}／{g["groupName"]}／A{i}')
                bodies[body(a)].append(f'A{i}')
                if f'A{i}' not in used:
                    hits = [dev for dev, rx in PRIORITY_DEVICES.items() if re.search(rx, a)]
                    own = bigrams(a)
                    cov = len(own & used_grams) / len(own) if own else 0.0
                    unreferenced.append({'taskName': name, 'groupName': g['groupName'], 'id': f'A{i}', 'text': a,
                                         'priorityDevices': hits, 'coveredByReferenced': round(cov, 2),
                                         'ruleClass': 'B' if cov >= B_RULE_COVERAGE else 'unclassified'})
            for ids in bodies.values():
                if len(ids) > 1:
                    warn['exactDuplicateControls'].append(f'{name}／{g["groupName"]}：{"、".join(ids)}')
            hz = collections.Counter(re.sub(r'\s+', '', h) for h in g['hazardItems'])
            warn['exactDuplicateHazards'] += [f'{name}／{g["groupName"]}' for h, c in hz.items() if c > 1]
            if g.get('核心重點') and not any(r['coreControlRefs'] for r in rows):
                warn['coreGroupWithoutCoreControl'].append(f'{name}／{g["groupName"]}')
    for key in docs:
        if key[0] not in library or key[1] not in {g['groupName'] for g in library[key[0]]['hazardGroups']}:
            fail.append(f'orphan scenario map {key}')

    # 7. equipment keyword mixing
    for name, task in library.items():
        owned = owned_families(task)
        for g in task['hazardGroups']:
            items = [(f'H{i}', h) for i, h in enumerate(g['hazardItems'], 1)] + [(f'A{i}', a) for i, a in enumerate(g['AvoidItems'], 1)]
            for loc, text in items:
                for fam, rx in EQUIPMENT.items():
                    if fam in owned or fam in GENERIC_SUPPORT or not re.search(rx, text):
                        continue
                    warn['equipmentKeywordConflict'].append({'taskName': name, 'groupName': g['groupName'], 'id': loc,
                                                             'family': fam, 'owned': sorted(owned), 'text': text})
        if re.search(r'物料或人員|人員或物料|可載人|載運人員', task['taskdescribe']) and owned & {'簡易提升機', '油壓升降平台'}:
            fail.append(f'goods-only equipment described as carrying people: {name}')

    # 10. mandatory device coverage (referenced controls only)
    coverage = []
    for name, families in MANDATORY_SCOPE.items():
        task = library.get(name)
        if not task:
            fail.append(f'mandatory scope task missing: {name}')
            continue
        texts = []
        for g in task['hazardGroups']:
            used = {r for row in docs[(name, g['groupName'])]['hazardControlMap'] for r in row['controlRefs']}
            texts += [a for i, a in enumerate(g['AvoidItems'], 1) if f'A{i}' in used]
        for fam in families:
            for item, rx, source in MANDATORY[fam]:
                ok = any(re.search(rx, t) for t in texts)
                coverage.append({'taskName': name, 'equipment': fam, 'item': item, 'source': source, 'covered': ok})

    # 8. history / references
    for row in industry:
        if row['taskId'] not in library:
            fail.append(f'industryMapping {row["id"]} -> missing task {row["taskId"]}')
    for item in migration['groups']:
        if item['taskName'] not in library:
            fail.append(f'scenarioMigration -> missing task {item["taskName"]}')
    for old, new in renames.items():
        if old in library:
            fail.append(f'renamed task still present: {old}')
        if new not in library:
            fail.append(f'rename target missing: {new}')
    sel_ver = re.search(r"const DATA_VER = '([^']+)'", sel_html).group(1)
    if sel_ver != data_ver:
        fail.append(f'DATA_VER differs New={data_ver} Selection={sel_ver}')

    by_task = collections.Counter(u['taskName'] for u in unreferenced)
    report = {
        'dataVersion': data_ver, 'scenarioMapsVersion': maps['version'],
        'counts': {'tasks': len(library), **stats, 'unreferencedControls': len(unreferenced),
                   'tasksWithUnreferenced': len(by_task), 'industryRows': len(industry)},
        'hardFailures': fail,
        'unreferencedPriority': [u for u in unreferenced if u['priorityDevices']],
        'unreferencedByDevice': dict(collections.Counter(d for u in unreferenced for d in u['priorityDevices'])),
        'unreferencedRuleClass': dict(collections.Counter(u['ruleClass'] for u in unreferenced)),
        'unreferencedPriorityRuleClass': dict(collections.Counter(u['ruleClass'] for u in unreferenced if u['priorityDevices'])),
        'mandatoryCoverage': coverage,
        'mandatoryGaps': [c for c in coverage if not c['covered']],
        'warnings': {k: v for k, v in warn.items()},
        'taskRenames': renames,
    }
    return report, unreferenced


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--json', type=Path)
    ap.add_argument('--unreferenced-json', type=Path)
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()
    report, unreferenced = audit(REPO)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    if args.unreferenced_json:
        args.unreferenced_json.parent.mkdir(parents=True, exist_ok=True)
        args.unreferenced_json.write_text(json.dumps(unreferenced, ensure_ascii=False, indent=1), encoding='utf-8')
    summary = {
        'dataVersion': report['dataVersion'], 'counts': report['counts'],
        'hardFailures': report['hardFailures'][:30], 'unreferencedByDevice': report['unreferencedByDevice'],
        'unreferencedRuleClass': report['unreferencedRuleClass'],
        'unreferencedPriorityRuleClass': report['unreferencedPriorityRuleClass'],
        'mandatoryGaps': [f"{g['taskName']}／{g['item']}（{g['source']}）" for g in report['mandatoryGaps']],
        'warningCounts': {k: len(v) for k, v in report['warnings'].items()},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if report['hardFailures'] or (args.strict and report['mandatoryGaps']):
        sys.exit(1)


if __name__ == '__main__':
    main()
