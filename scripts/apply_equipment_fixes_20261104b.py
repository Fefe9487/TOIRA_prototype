#!/usr/bin/env python3
"""Apply the 20261104b equipment-classification / mandatory-device fixes.

Every edit asserts the current text first, so the script refuses to run twice or on drifted data.
Writes tasksLibrary.json, scenarioMaps.json, industryMapping.json and audit/equipment_fixes_20261104b.json
(change log + the TASK_RENAMES / AVOID_INDEX_REMAP_20261104B / CONTROL_KEY_RENAMES_20261104B tables that
New.html embeds for saved-project migration).

Run: python scripts/apply_equipment_fixes_20261104b.py [--dry-run]
"""
import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VERSION = '20261104b'
LABEL_RE = re.compile(r'[（(【]\s*(消除|取代|工程改善|工程控制|行政管理|管理控制|個人防護具|個人防護)\s*[）)】]\s*$')


def body_key(text):
    """Mirror of New.html controlBodyKey(): saved checkbox states are keyed by this."""
    return re.sub(r'\s+', '', LABEL_RE.sub('', text or '')).strip()


class Editor:
    def __init__(self):
        self.library = json.loads((REPO / 'tasksLibrary.json').read_text(encoding='utf-8'))
        self.maps = json.loads((REPO / 'scenarioMaps.json').read_text(encoding='utf-8'))
        self.industry = json.loads((REPO / 'industryMapping.json').read_text(encoding='utf-8'))
        self.log = []
        self.renames = {}
        self.avoid_remap = {}
        self.key_renames = {}

    # ---- lookup -------------------------------------------------------------------------------
    def group(self, task, group):
        g = next(g for g in self.library[task]['hazardGroups'] if g['groupName'] == group)
        doc = next(d for d in self.maps['maps'] if d['taskName'] == task and d['groupName'] == group)
        return g, doc

    def note(self, kind, task, group, ident, before, after, reason):
        self.log.append({'kind': kind, 'taskName': task, 'groupName': group, 'id': ident,
                         'before': before, 'after': after, 'reason': reason})

    # ---- task level -----------------------------------------------------------------------------
    def rename_task(self, old, new, reason):
        assert old in self.library and new not in self.library, (old, new)
        self.library = {(new if k == old else k): v for k, v in self.library.items()}
        self.library[new]['taskName'] = new
        for d in self.maps['maps']:
            if d['taskName'] == old:
                d['taskName'] = new
        rows = 0
        for row in self.industry:
            if row['taskId'] == old:
                row['taskId'] = new
                rows += 1
        self.renames[old] = new
        self.note('rename_task', new, None, 'taskName', old, new, f'{reason}（industryMapping {rows} 列同步）')

    def set_describe(self, task, old, new, reason):
        t = self.library[task]
        assert t['taskdescribe'] == old, (task, t['taskdescribe'])
        t['taskdescribe'] = new
        self.note('describe', task, None, 'taskdescribe', old, new, reason)

    def replace_in_task(self, task, old, new, reason, expect):
        """Literal term replacement in description, hazards, controls and core reasons of one task."""
        t = self.library[task]
        n = 0
        if old in t['taskdescribe']:
            before = t['taskdescribe']
            t['taskdescribe'] = before.replace(old, new)
            n += 1
            self.note('term', task, None, 'taskdescribe', before, t['taskdescribe'], reason)
        for g in t['hazardGroups']:
            _, doc = self.group(task, g['groupName'])
            for i, h in enumerate(g['hazardItems']):
                if old in h:
                    self._set_hazard(task, g, doc, i, h.replace(old, new), reason, 'term')
                    n += 1
            for i, a in enumerate(g['AvoidItems']):
                if old in a:
                    self._set_control(task, g, i, a.replace(old, new), reason, 'term')
                    n += 1
            if old in g.get('核心理由', ''):
                before = g['核心理由']
                g['核心理由'] = before.replace(old, new)
                n += 1
                self.note('term', task, g['groupName'], '核心理由', before, g['核心理由'], reason)
        assert n == expect, (task, old, n, expect)

    # ---- hazards --------------------------------------------------------------------------------
    def _set_hazard(self, task, g, doc, index, text, reason, kind='hazard'):
        before = g['hazardItems'][index]
        row = doc['hazardControlMap'][index]
        assert row['hazardItem'] == before
        g['hazardItems'][index] = text
        row['hazardItem'] = text
        self.note(kind, task, g['groupName'], f'H{index + 1}', before, text, reason)

    def set_hazard(self, task, group, hid, old, new, reason):
        g, doc = self.group(task, group)
        i = int(hid[1:]) - 1
        assert g['hazardItems'][i] == old, (task, group, hid, g['hazardItems'][i])
        self._set_hazard(task, g, doc, i, new, reason)

    def append_hazard(self, task, group, text, severity, refs, cores, reason):
        g, doc = self.group(task, group)
        assert text not in g['hazardItems']
        sibling = doc['hazardControlMap'][-1]
        row = {'hazardId': f"H{len(g['hazardItems']) + 1}", 'hazardItem': text, 'severity': severity,
               'controlRefs': refs, 'coreControlRefs': cores}
        for key in ('ruleSeverity', 'ruleSeverityBasis'):
            if key in sibling:
                row[key] = sibling[key]
        assert set(cores) <= set(refs) and all(int(r[1:]) <= len(g['AvoidItems']) for r in refs)
        g['hazardItems'].append(text)
        doc['hazardControlMap'].append(row)
        self.note('append_hazard', task, group, row['hazardId'], None, text,
                  f"{reason}；S{severity}，引用 {','.join(refs)}，必要設施 {','.join(cores) or '無'}")
        return row['hazardId']

    # ---- controls -------------------------------------------------------------------------------
    def _set_control(self, task, g, index, text, reason, kind='control'):
        before = g['AvoidItems'][index]
        if LABEL_RE.search(before) and LABEL_RE.search(text):
            assert LABEL_RE.search(before).group(1) == LABEL_RE.search(text).group(1), 'lane change not allowed'
        g['AvoidItems'][index] = text
        old_key, new_key = body_key(before), body_key(text)
        if old_key != new_key:
            self.key_renames.setdefault(task, {})[old_key] = new_key
        self.note(kind, task, g['groupName'], f'A{index + 1}', before, text, reason)

    def set_control(self, task, group, aid, old, new, reason):
        g, _ = self.group(task, group)
        i = int(aid[1:]) - 1
        assert g['AvoidItems'][i] == old, (task, group, aid, g['AvoidItems'][i])
        self._set_control(task, g, i, new, reason)

    def append_control(self, task, group, text, reason):
        g, _ = self.group(task, group)
        assert body_key(text) not in {body_key(a) for a in g['AvoidItems']}, (task, group, text)
        g['AvoidItems'].append(text)
        aid = f"A{len(g['AvoidItems'])}"
        self.note('append_control', task, group, aid, None, text, reason)
        return aid

    def add_ref(self, task, group, hid, aid, core, reason):
        _, doc = self.group(task, group)
        row = doc['hazardControlMap'][int(hid[1:]) - 1]
        assert aid not in row['controlRefs'], (task, group, hid, aid)
        row['controlRefs'].append(aid)
        if core:
            row['coreControlRefs'].append(aid)
        self.note('add_ref', task, group, hid, None, aid + ('（必要設施）' if core else ''), reason)

    def delete_controls(self, task, group, ids, reason, replace=None):
        """Delete AvoidItems; refs to a deleted id move to replace[id] (or must not exist). Group-local renumbering."""
        replace = replace or {}
        g, doc = self.group(task, group)
        drop = sorted(int(a[1:]) for a in ids)
        old_n = len(g['AvoidItems'])
        for row in doc['hazardControlMap']:
            refs, cores = [], []
            for r in row['controlRefs']:
                if r in ids:
                    assert r in replace, (task, group, row['hazardId'], r, 'deleted control still referenced')
                r = replace.get(r, r)
                if r not in refs:
                    refs.append(r)
            for r in row['coreControlRefs']:
                r = replace.get(r, r)
                if r not in cores:
                    cores.append(r)
            row['controlRefs'], row['coreControlRefs'] = refs, cores
        table, new_index = [], 0
        for i in range(1, old_n + 1):
            if i in drop:
                table.append(int(replace[f'A{i}'][1:]) - 1 if f'A{i}' in replace else None)
            else:
                table.append(new_index)
                new_index += 1
        # Replacement targets are expressed in old numbering; map them through the table.
        table = [table[t] if (t is not None and i + 1 in drop) else t for i, t in enumerate(table)]
        for i in reversed(drop):
            self.note('delete_control', task, group, f'A{i}', g['AvoidItems'][i - 1], replace.get(f'A{i}'), reason)
            del g['AvoidItems'][i - 1]
        renum = {f'A{i + 1}': f'A{t + 1}' for i, t in enumerate(table) if t is not None and i + 1 not in drop}
        for row in doc['hazardControlMap']:
            row['controlRefs'] = [renum[r] for r in row['controlRefs']]
            row['coreControlRefs'] = [renum[r] for r in row['coreControlRefs']]
        if table != list(range(old_n)):
            self.avoid_remap[f'{task}\u0000{group}'] = table

    def merge_exact_duplicates(self, reason):
        merged = 0
        for task, t in self.library.items():
            for g in t['hazardGroups']:
                seen, dup = {}, {}
                for i, a in enumerate(g['AvoidItems'], 1):
                    if a in seen:
                        dup[f'A{i}'] = seen[a]
                    else:
                        seen[a] = f'A{i}'
                if dup:
                    self.delete_controls(task, g['groupName'], list(dup), reason, replace=dup)
                    merged += len(dup)
        return merged

    # ---- output ---------------------------------------------------------------------------------
    def finish(self, dry_run):
        for task, table in self.key_renames.items():
            for old in list(table):
                new = table[old]
                while new in table and table[new] != new:
                    new = table[new]
                table[old] = new
        too_long = [c for c in self.log if c['kind'] in ('control', 'term', 'append_control') and c['id'].startswith('A')
                    and len(body_key(c['after'])) > 100]
        assert not too_long, [(c['taskName'], c['groupName'], c['id']) for c in too_long]
        hazards = sum(len(d['hazardControlMap']) for d in self.maps['maps'])
        core = sum(bool(r['coreControlRefs']) for d in self.maps['maps'] for r in d['hazardControlMap'])
        self.maps['counts']['hazards'] = hazards
        self.maps['counts']['coreHazards'] = core
        self.maps['equipmentAudit'] = (f'{VERSION}：設備分類與必要設施稽核修正，見 '
                                       'docs/TOIRA_作業設備分類與必要設施稽核報告.md 與 audit/equipment_fixes_20261104b.json')
        out = {'version': VERSION, 'taskRenames': self.renames, 'avoidIndexRemap': self.avoid_remap,
               'controlKeyRenames': self.key_renames, 'changes': self.log}
        if dry_run:
            print(json.dumps({k: v for k, v in out.items() if k != 'changes'}, ensure_ascii=False, indent=1))
            print(len(self.log), 'changes')
            return
        (REPO / 'tasksLibrary.json').write_text(json.dumps(self.library, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (REPO / 'scenarioMaps.json').write_text(json.dumps(self.maps, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (REPO / 'industryMapping.json').write_text(json.dumps(self.industry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (REPO / 'audit').mkdir(exist_ok=True)
        (REPO / 'audit' / f'equipment_fixes_{VERSION}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        print(len(self.log), 'changes written')


def apply(e):
    # ---------------- P0 油壓升降平台作業：限定為僅供物料升降，不推定可載人 ----------------
    T = '油壓升降平台作業'
    R0 = '設備型式無法由作業資料確定是否具合法載人用途，作業範疇限定為僅供物料升降，人員搭乘改列違規情境'
    e.set_describe(T,
        '本作業使用油壓升降平台，將物料或人員於不同高度間進行垂直升降與轉運。人員於啟用前檢查平台本體、油壓系統、控制器與安全裝置，確認載重與重心後再進行進出料、升降定位與對位操作。作業完成後應將平台復位、停機並執行點檢與清潔。作業範圍包括平台檢查、載物進出、升降定位、轉運及收尾點檢。',
        '本作業使用僅供物料升降的油壓升降平台（含剪叉式升降台及跨樓層貨物升降平台），將物料於不同高度間進行垂直升降與轉運，人員不隨平台升降。人員於啟用前確認設備銘牌標示的用途與額定載重，檢查平台本體、油壓系統、控制器與安全裝置，確認載重與重心後再進行進出料、升降定位與對位操作。作業完成後應將平台復位、停機並執行點檢與清潔。作業範圍包括平台檢查、載物進出、升降定位、轉運及收尾點檢；人員升降應改用合法載人設備，不在本作業範圍。',
        R0)
    e.set_control(T, '墜落、滾落', 'A5',
        '進出及升降前將推車煞車、物料固定且不得超出平台邊界；非額定載人設備禁止搭乘，載人時護欄與門閂須關閉。(行政管理)',
        '進出及升降前將推車煞車、物料固定且不得超出平台邊界；平台僅供物料升降，禁止人員搭乘或隨物料升降。(行政管理)', R0)
    e.set_hazard(T, '墜落、滾落', 'H5',
        '油壓缸、止回防墜閥或承載結構失效，造成平台突然下沉或傾斜，人員在平台、臨邊或救援時失衡墜落。',
        '油壓缸、止回防墜閥或承載結構失效，造成平台突然下沉或傾斜，人員在平台邊緣裝卸、臨邊或救援時失衡墜落。', R0)
    e.set_hazard(T, '衝撞', 'H2',
        '人員搭乘平台或在平台內作業時，未確認上方及側方淨高與淨距，遭管線、門框或其他固定障礙物撞擊。',
        '人員違規搭乘平台隨物料升降，或於平台未停止時探身進入平台，遭管線、門框或其他固定障礙物撞擊。', R0)
    e.set_control(T, '衝撞', 'A3',
        '搭乘平台前確認上方及側方淨空，升降中禁止探身或將肢體伸出平台。(行政管理)',
        '平台僅供物料升降，禁止人員搭乘；升降中人員不得探身或將肢體伸入平台行程範圍。(行政管理)', R0)
    e.set_hazard(T, '被撞', 'H4',
        '檢查、清潔或故障處置時平台未停機隔離，或人員搭乘時平台突啟、急停及載物位移，遭活動部件或物料撞擊。',
        '檢查、清潔或故障處置時平台未停機隔離，或人員違規搭乘時平台突啟、急停及載物位移，遭活動部件或物料撞擊。', R0)
    e.set_hazard(T, '職業病', 'H2',
        '平台長時間站立、震動或啟停衝擊，且油壓泵浦、導向或減振系統異常未改善，可能造成下肢疲勞及腰背慢性傷害。',
        '操作人員長時間站立操作及反覆在平台邊裝卸，且油壓泵浦、導向或減振系統異常造成啟停衝擊未改善，可能造成下肢疲勞及腰背慢性傷害。', R0)
    a = e.append_control(T, '墜落、滾落',
        '跨樓層使用的貨物升降平台，依搬器尺寸及積載荷重確認是否屬簡易提升機或升降機，並依相關規定管理。(行政管理)',
        '起重升降機具安全規則第2條：搬器順沿軌道鉛直升降者屬升降機，僅搬運貨物且搬器底面積1平方公尺以下或頂高1.2公尺以下者屬簡易提升機')
    e.add_ref(T, '墜落、滾落', 'H1', a, False, '跨樓層井道型設備的法定分類確認，作為支撐措施')

    # ---------------- P1-1 備料與簡易升降機操作作業 → 簡易提升機 ----------------
    T0, T = '備料與簡易升降機操作作業', '備料與簡易提升機操作作業'
    e.rename_task(T0, T, '法定名稱為「簡易提升機」（起重升降機具安全規則第2條第7款）')
    R1 = '統一使用法定名稱「簡易提升機」'
    e.replace_in_task(T, '簡易升降機', '簡易提升機', R1, expect=3)
    e.replace_in_task(T, '升降機', '簡易提升機', R1 + '（本作業的升降設備即簡易提升機）', expect=11)
    e.set_describe(T, e.library[T]['taskdescribe'], e.library[T]['taskdescribe'].replace(
        '並操作簡易提升機完成物料垂直運輸。',
        '並操作簡易提升機（僅以搬運貨物為目的，搬器底面積一平方公尺以下或頂高一點二公尺以下，不得搭乘人員）完成物料垂直運輸。'),
        '限定為簡易提升機物料搬運（起重升降機具安全規則第2條第7款、第96條）')
    e.set_hazard(T, '被夾、被捲', 'H6',
        '人員搭乘平台或進入平台下方、升降通道時，平台或物料移動可能造成壓夾。',
        '人員違規搭乘搬器或進入平台下方、升降通道時，平台或物料移動可能造成壓夾。', '簡易提升機不得搭乘人員（第96條），改為違規情境')
    e.set_hazard(T, '被撞', 'H4',
        '人員搭乘簡易提升機或停留在平台、樓層開口及運行範圍時，可能被平台、推車或物料撞擊。',
        '人員違規搭乘簡易提升機或停留在平台、樓層開口及運行範圍時，可能被平台、推車或物料撞擊。', '簡易提升機不得搭乘人員（第96條），改為違規情境')
    e.set_control(T, '墜落、滾落', 'A2',
        '簡易提升機僅供物料運送，禁止人員搭乘、停留或跨越護欄；故障時不得自行開門、攀爬或進入井道。(行政管理)',
        '簡易提升機僅供搬運貨物，禁止人員搭乘、停留或跨越護欄；檢修須搭乘時先採防墜落及防飛落措施。(行政管理)',
        '起重升降機具安全規則第96條本文及但書')
    a = e.append_control(T, '被夾、被捲',
        '簡易提升機設置過捲預防裝置及其他安全裝置並維持其效能，失效時停用修復。(工程改善)',
        '起重升降機具安全規則第95條；原作業庫只在未引用的檢查措施提到過捲預防裝置')
    e.add_ref(T, '被夾、被捲', 'H4', a, True, '法定安全裝置列為必要設施（第95條）')
    e.add_ref(T, '被夾、被捲', 'H4', 'A2', False, '原未引用的作業前測試（含過捲預防裝置、制動）補引用；職業安全衛生管理辦法第25條、第57條')

    # ---------------- P1-2 使用升降機上下料件作業 ----------------
    T = '使用升降機上下料件作業'
    R2 = '升降機的法定安全裝置為終點極限開關、緊急停止裝置及制動器；過捲預防裝置是簡易提升機與起重機的用語'
    old = e.library[T]['taskdescribe']
    e.set_describe(T, old, old + '本作業的升降機指搬器順沿軌道鉛直升降、依設計載貨或客貨兩用的升降機；僅搬運貨物且搬器底面積一平方公尺以下或頂高一點二公尺以下者屬簡易提升機，另依簡易提升機作業評估。',
        '界定一般升降機與簡易提升機的適用界線（起重升降機具安全規則第2條）')
    e.set_control(T, '被夾、被捲', 'A1',
        '作業前測試門連鎖、防夾、平層、終點極限、急停及過捲預防裝置。(行政管理)',
        '作業前測試門連鎖、防夾、平層、終點極限開關及緊急停止裝置。(行政管理)', R2)
    e.set_control(T, '被夾、被捲', 'A2',
        '作業前檢查升降機制動器、控制、鋼索或吊鏈與導軌；發現異常或遭旁路時立即停用。(行政管理)',
        '發現升降機制動、控制、鋼索或導軌異常或遭旁路時立即停用，由升降機維護人員處理。(行政管理)',
        '鋼索、導軌屬每月定期檢查項目（職業安全衛生管理辦法第22條），使用者改為異常停用')
    a_eng = e.append_control(T, '被夾、被捲',
        '升降機設置終點極限開關、緊急停止裝置及其他安全裝置並維持其效能，失效時停用修復。(工程改善)',
        '職業安全衛生設施規則第96條；起重升降機具安全規則第77條')
    e.append_hazard(T, '被夾、被捲',
        '終點極限開關、緊急停止裝置或制動器失效時，車廂超越停止位置或無法及時停止，可能將裝卸人員夾於車廂與樓板或門框之間。',
        5, [a_eng, 'A1', 'A2'], [a_eng], '原作業庫缺少升降機法定安全裝置失效的情境，A1、A2 原未引用')
    a78 = e.append_control(T, '被夾、被捲',
        '設計上專供載貨用之升降機不得搭載人員，車廂移動前裝卸人員應退出車廂。(行政管理)',
        '起重升降機具安全規則第78條（限設計上專供載貨用者）')
    e.add_ref(T, '被夾、被捲', 'H4', a78, False, '載貨用升降機人員隨載荷搭乘的夾壓風險')

    # ---------------- P1-4 高處繩索接近作業：移除誤植的起重吊掛用具檢查 ----------------
    e.delete_controls('高處繩索接近作業', '物體飛落', ['A7', 'A8'],
        '未引用且屬起重升降機具吊掛用具（鋼索、吊鏈、吊鉤、卸克）檢查，與繩索接近作業的人員繩索系統不同')

    # ---------------- P1-5 人字臂起重機 → 人字臂起重桿 ----------------
    T0, T = '人字臂起重機組裝與拆卸作業', '人字臂起重桿組裝與拆卸作業'
    e.rename_task(T0, T, '法定名稱為「人字臂起重桿」（起重升降機具安全規則第2條第3款；職業安全衛生設施規則第21-3條「人字臂起重桿組拆作業」）')
    e.replace_in_task(T, '人字臂起重機', '人字臂起重桿', '統一使用法定名稱', expect=3)
    e.set_hazard(T, '感電', 'H4',
        '起重機通電試車及控制功能測試時，因控制盤、端子或馬達回路帶電部位外露，或未管制人員進入測試區而發生感電。',
        '人字臂起重桿通電試車及控制功能測試時，因控制盤、端子或馬達回路帶電部位外露，或未管制人員進入測試區而發生感電。',
        '試車對象是人字臂起重桿本體，非輔助起重機')
    RQ = ('人字臂起重桿吊升荷重三公噸以上才屬危險性機械並須檢查合格證（危險性機械及設備安全檢查規則第3條、第36條）；'
          '操作資格依荷重分為危險性機械操作人員訓練或技能檢定（教育訓練規則第12條）與特殊作業教育訓練（第14條）')
    e.set_control(T, '物體飛落', 'A10',
        '組拆前確認人字臂起重桿檢查合格證仍在有效期限內，並由持有效操作證的人員操作。(行政管理)',
        '人字臂起重桿由依吊升荷重受相應訓練或技能檢定合格者操作；三公噸以上者確認檢查合格證有效。(行政管理)', RQ)
    e.set_control(T, '物體飛落', 'A11',
        '人字臂起重桿合格證逾期，或操作證不符時，不得組拆或吊掛。(行政管理)',
        '人字臂起重桿檢查合格證逾期，或操作人員資格不符時，不得組拆或吊掛。(行政管理)', RQ)
    a_eng = e.append_control(T, '物體飛落',
        '吊升裝置及起伏裝置設置過捲預防裝置及動力遮斷時能自行制動的制動裝置，失效時停止吊升。(工程改善)',
        '起重升降機具安全規則第43條（絞車為動力者除外）、第52條')
    a_chk = e.append_control(T, '物體飛落',
        '試運轉前確認過捲預防裝置間距、制動裝置及吊桿傾斜角指示裝置功能正常，異常不得吊升荷物。(行政管理)',
        '起重升降機具安全規則第44條、第55條；職業安全衛生管理辦法第54條')
    e.append_hazard(T, '物體飛落',
        '組裝完成後試運轉或試吊時，過捲預防裝置未設置、間距未調整或制動裝置失效，吊具捲過頭撞擊吊桿前端槽輪或荷物失控下降，造成鋼索斷裂及吊物飛落。',
        5, [a_eng, a_chk, 'A1', 'A8'], [a_eng, 'A8'], '原作業庫沒有過捲預防裝置與制動裝置的情境及引用')

    # ---------------- P1-6 高空作業車 → 高空工作車 ----------------
    T0, T = '高空作業車作業', '高空工作車作業'
    e.rename_task(T0, T, '法定名稱為「高空工作車」（職業安全衛生設施規則第128-1條至第128-9條）')
    e.replace_in_task(T, '高空作業車', '高空工作車', '統一使用法定名稱', expect=4)
    e.replace_in_task('外牆造景美化作業', '高空作業車', '高空工作車', '統一使用法定名稱', expect=1)
    e.set_control(T, '墜落、滾落', 'A8',
        '完成高空工作車特殊作業訓練並持有效操作證才可操作，乘員不得超過額定人數。(行政管理)',
        '由經高空工作車操作人員特殊作業安全衛生教育訓練者操作，工作台乘員不得超過額定人數。(行政管理)',
        '職業安全衛生設施規則第128-9條；教育訓練規則第14條第6款（特殊作業教育訓練，非操作證照）')
    e.set_control(T, '墜落、滾落', 'A2',
        '應使用全身背負式安全帶，掛鉤只能連接製造商指定錨錠點，不得掛於護欄或其他非指定構件。(個人防護)',
        '工作台上人員佩戴安全帽及符合CNS 14253-1的全身背負式安全帶，掛鉤僅連接製造商指定錨錠點。(個人防護)',
        '職業安全衛生設施規則第128-1條第7款')
    e.set_control(T, '墜落、滾落', 'A9',
        '升高平台前應確認地面平整及承載力足夠，完成煞車、外伸撐座或輪擋設置並確認荷重及製造商風速限制。(行政管理)',
        '升高平台前確認地面承載力足夠，有外伸撐座者依原廠設計完全伸出並施加煞車，確認荷重及風速限制。(行政管理)',
        '職業安全衛生設施規則第128-1條第2款、第5款')
    e.set_hazard(T, '墜落、滾落', 'H2',
        '高空工作車停於坡地、鬆軟或承載力不足地面，或因煞車、外伸撐座、防失穩裝置失效及超載偏載而翻覆，可能造成平台人員墜落。',
        '高空工作車停於坡地、鬆軟或承載力不足地面，或因煞車、外伸撐座、傾斜警報或荷重限制等安全裝置失效及超載偏載而翻覆，可能造成平台人員墜落。',
        '「防失穩裝置」非通用用語，改為具體安全裝置')
    e.set_control(T, '被夾、被捲', 'A4',
        '使用前應測試控制搖桿、液壓閥、急停、緊急下降及防夾功能，發現卡滯或誤動作時立即停用。(行政管理)',
        '使用前應測試控制搖桿、液壓閥、緊急停止及緊急下降裝置，發現卡滯或誤動作時立即停用。(行政管理)',
        '高空工作車無通用的「防夾功能」，改為緊急停止及緊急下降裝置')
    e.set_control(T, '被撞', 'A3',
        '使用前確認煞車、轉向、離合器、行走警示、輪胎、操作裝置及作業裝置；油壓、安全裝置或連鎖異常立即停用。(行政管理)',
        '每日作業前檢點制動裝置、操作裝置及作業裝置之性能，異常時立即停用並通報修復。(行政管理)',
        '職業安全衛生管理辦法第50-1條')
    e.add_ref(T, '被撞', 'H4', 'A3', False, '原未引用的作業前檢點補引用至制動或轉向失效情境')
    e.delete_controls(T, '墜落、滾落', ['A10'], '與 A2 重複（僅掛點用語不同），引用改指 A2', replace={'A10': 'A2'})

    # ---------------- 其他作業：高空工作車、堆高機的資格用語 ----------------
    RS = '高空工作車、荷重一公噸以上堆高機的操作資格是特殊作業安全衛生教育訓練（設施規則第128-9條、第126條），不是「操作證」'
    e.set_control('外牆造景美化作業', '墜落、滾落', 'A8',
        '高空工作車由持有效操作證人員操作。(行政管理)',
        '高空工作車由經特殊作業安全衛生教育訓練人員操作。(行政管理)', RS)
    e.set_control('外牆造景美化作業', '墜落、滾落', 'A12',
        '高空工作車由持有效操作證人員操作；逾期未檢查或檢查不合格不得使用。(行政管理)',
        '高空工作車由經特殊作業安全衛生教育訓練人員操作；未依規定檢查或檢查異常不得使用。(行政管理)', RS)
    e.set_control('道路維護作業', '墜落、滾落', 'A3',
        '禁止以車斗或材料堆作為站立平台，高處改用合格梯具或高空工作車，未持高空工作車操作證者不得升高。(行政管理)',
        '禁止以車斗或材料堆作為站立平台，高處改用合格梯具或高空工作車，未受高空工作車特殊作業訓練者不得操作。(行政管理)', RS)
    e.set_control('道路維護作業', '墜落、滾落', 'A15',
        '高空工作車限由受訓且持有效操作證者操作，無證者禁止升高。(行政管理)',
        '高空工作車限由經特殊作業安全衛生教育訓練人員操作，未受訓者禁止操作。(行政管理)', RS)
    e.set_control('堆高機駕駛與搬運作業', '被撞', 'A5',
        '完成堆高機特殊作業訓練並持有效操作證才得出車，車輛須有安全標示（TS標章）。(行政管理)',
        '荷重一公噸以上堆高機由經特殊作業安全衛生教育訓練人員操作，車輛須有安全標示（TS標章）。(行政管理)', RS)

    # ---------------- 「吊籠」誤指鋼筋籠或物料吊運籠 ----------------
    RG = '法定「吊籠」專指供人員升降施工之設備（起重升降機具安全規則第2條第6款），此處實指鋼筋籠或物料吊運籠'
    e.set_control('柱狀基礎建構作業(連續壁)', '墜落、滾落', 'A6',
        '禁止站在導牆頂、槽口護蓋或鋼筋籠上作業；護欄因吊籠或導管拆除前須先完成防墜繫掛，未繫掛不得拆護欄。(行政管理)',
        '禁止站在導牆頂、槽口護蓋或鋼筋籠上作業；吊放鋼筋籠或導管需拆護欄時，須先完成防墜繫掛才可拆除。(行政管理)', RG)
    e.set_control('柱狀基礎建構作業(連續壁)', '物體倒塌、崩塌', 'A6',
        '成槽後應在允許敞槽時間內完成吊籠與水中混凝土澆置；逾時先補漿並經主管確認穩定才可繼續。(行政管理)',
        '成槽後應在允許敞槽時間內完成吊放鋼筋籠與水中混凝土澆置；逾時先補漿並經主管確認穩定才可繼續。(行政管理)', RG)
    e.set_control('樁式基礎作業', '物體倒塌、崩塌', 'A6',
        '成孔後應在允許敞孔時間內完成吊籠與灌注；逾時先檢孔、補漿，經主管確認孔壁穩定才得繼續。(行政管理)',
        '成孔後應在允許敞孔時間內完成吊放鋼筋籠與灌注；逾時先檢孔、補漿，經主管確認孔壁穩定才得繼續。(行政管理)', RG)
    e.set_control('施工架組拆與高處作業', '物體飛落', 'A7',
        '拆除構件使用吊袋、吊籠或繩索傳遞至地面，禁止直接向下拋擲扣件、短料或小型構件。(行政管理)',
        '拆除構件使用吊袋、物料吊運籠或繩索傳遞至地面，禁止直接向下拋擲扣件、短料或小型構件。(行政管理)', RG)
    e.set_control('移動式起重機吊掛作業', '物體飛落', 'A5',
        '散裝物、小型零件及鬆散附掛件使用有門鎖的吊籠、料斗或封閉容器，並固定內容物。(工程改善)',
        '散裝物、小型零件及鬆散附掛件使用有門鎖的物料吊運籠、料斗或封閉容器，並固定內容物。(工程改善)', RG)
    e.set_control('高壓氣體容器操作與檢修作業', '衝撞', 'A2',
        '吊運鋼瓶應置於額定吊籠或使用適用專用吊具，起吊前應確認吊具及連接點完整無損。(行政管理)',
        '吊運鋼瓶應置於額定鋼瓶吊運籠或使用適用專用吊具，起吊前應確認吊具及連接點完整無損。(行政管理)', RG)

    # ---------------- 同一群組內逐字重複的措施 ----------------
    n = e.merge_exact_duplicates('同一群組內措施逐字重複；引用與必要設施標記併入第一條，勾選鍵本來就相同')
    print('merged exact duplicates:', n)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    e = Editor()
    apply(e)
    e.finish(args.dry_run)


if __name__ == '__main__':
    main()
