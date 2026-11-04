#!/usr/bin/env python3
"""Apply the 2026-11-04 expert decisions on the audit report (section 9), round 20261104d.

1  split 剪叉式升降台作業 out of 油壓升降平台作業 (new task; 油壓 keeps floor-to-floor cargo lifts)
2  游離輻射作業 職業病 A3 personal dosimeter: 個人防護 -> 管理控制
3  remove industryMapping HH-004 (crane personnel platform is not the 設施規則21-3 吊籠作業); CY-003 stays in 營造業
4  import 建築物外牆吊籠清洗及維護作業 from the cursor-jsa draft and list it under 危險性作業／具墜落危險之作業
6  crane inspection certificate / operator qualification controls become conditional on the 3-tonne threshold
9  設備管路原地循環清洗作業: heat-illness scenario; 吊掛熔融金屬澆鑄桶作業 scope includes pouring and slag removal
10 異常氣壓作業 職業病 A4 supply-air quality referenced by a new supply-air contamination scenario

Appends to audit/equipment_fixes_20261104b.json (phase 7) so New.html migration tables stay in one place.
Run once: python scripts/apply_expert_decisions_20261104d.py [--dry-run]
"""
import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_equipment_fixes_20261104b import LABEL_RE, REPO, Editor, body_key  # noqa: E402

DRAFT = REPO.parent / 'gen4' / 'out' / 'cursor-jsa' / '建築物外牆吊籠清洗及維護作業' / '作業表.json'
PHASE = 7


def rule_table(maps):
    """Most common (ruleSeverity, basis) per hazard type across the library."""
    table = collections.defaultdict(collections.Counter)
    for doc in maps['maps']:
        for r in doc['hazardControlMap']:
            if 'ruleSeverity' in r and '待專家' not in str(r.get('ruleSeverityBasis')):
                table[doc['groupName']][(r['ruleSeverity'], r['ruleSeverityBasis'])] += 1
    return {k: v.most_common(1)[0][0] for k, v in table.items()}


def add_task(e, name, describe, groups, reason):
    """groups: [(groupName, core, coreReason, AvoidItems, [(hazard, severity, refs, cores)])]"""
    assert name not in e.library
    rules = rule_table(e.maps)
    hazard_groups = []
    for gname, core, why, avoids, rows in groups:
        assert all(len(body_key(a)) <= 100 and LABEL_RE.search(a) for a in avoids), (name, gname)
        rs, basis = rules[gname]
        map_rows = []
        for i, (hazard, sev, refs, cores) in enumerate(rows, 1):
            assert set(cores) <= set(refs) and all(int(r[1:]) <= len(avoids) for r in refs), (name, gname, i)
            map_rows.append({'hazardId': f'H{i}', 'hazardItem': hazard, 'severity': sev, 'controlRefs': refs,
                             'coreControlRefs': cores, 'ruleSeverity': rs, 'ruleSeverityBasis': basis})
        used = {r for row in map_rows for r in row['controlRefs']}
        assert used == {f'A{i}' for i in range(1, len(avoids) + 1)}, (name, gname, 'every control referenced')
        hazard_groups.append({'groupName': gname, 'severitylevel': f"S{max(r['severity'] for r in map_rows)}",
                              'hazardItems': [r['hazardItem'] for r in map_rows], 'AvoidItems': avoids,
                              '核心重點': core, '核心理由': why, 'ruleSeverity': rs})
        e.maps['maps'].append({'taskName': name, 'groupName': gname, 'hazardControlMap': map_rows})
    e.library[name] = {'taskName': name, 'taskdescribe': describe, 'hazardGroups': hazard_groups}
    e.note('add_task', name, None, 'taskName', None,
           f"{len(hazard_groups)} 組、{sum(len(g['hazardItems']) for g in hazard_groups)} 則情境、"
           f"{sum(len(g['AvoidItems']) for g in hazard_groups)} 條措施", reason)


def next_id(rows, prefix):
    nums = [int(r['id'].split('-')[1]) for r in rows if r['id'].startswith(prefix + '-')]
    return f'{prefix}-{max(nums) + 1:03d}'


def scissor_lift(e):
    T = '油壓升降平台作業'
    old = e.library[T]['taskdescribe']
    e.set_describe(T, old, old.replace(
        '本作業使用僅供物料升降的油壓升降平台（含剪叉式升降台及跨樓層貨物升降平台），將物料於不同高度間進行垂直升降與轉運，人員不隨平台升降。',
        '本作業使用僅供物料升降的跨樓層或不同高度間貨物油壓升降平台，將物料於不同高度間進行垂直升降與轉運，人員不隨平台升降；'
        '固定在同一作業位置調整工件高度的剪叉式升降台另依「剪叉式升降台作業」評估。'),
        '專家決定：剪叉式升降台另列；跨樓層平台不再區分升降機或簡易提升機，危害情境相近')
    name = '剪叉式升降台作業'
    add_task(e, name,
        '本作業使用固定在作業位置的剪叉式升降台（油壓或電動驅動，僅供物料或工件升降，不載人），調整棧板、工件或物料的作業高度以便裝卸、加工或包裝。'
        '人員於使用前確認額定載重、護裙或護罩、緊急停止及防止下降裝置，放置並固定物料後操作升降，完成後將平台降至最低位置並停機。'
        '作業範圍包括使用前檢查、物料放置與固定、升降操作，以及清潔、排除卡料與維修時的停機支撐。人員升降應改用合法載人設備；跨樓層物料升降另依「油壓升降平台作業」評估。',
        [
            ('被夾、被捲', True, '剪叉臂交叉點與平台下方是主要夾點，升起狀態下作業未支撐時，平台下降可造成全身壓傷。', [
                '剪叉臂及平台下方周邊設置防夾護裙或觸壓式停止裝置，平台下降受阻時自動停止。(工程改善)',
                '升降台設置可鎖定升起平台的安全支撐桿或機械止擋，並維持完整可用。(工程改善)',
                '清潔、排除卡料或維修前先降下平台；須在升起狀態作業時，先停機、斷電、洩壓並放置安全支撐桿才可進入下方。(管理控制)',
                '平台與鄰近機台、輸送帶及牆柱保持足夠間距或加裝固定護欄，避免升降時形成夾點。(工程改善)',
                '控制器採持續按壓式並加裝防誤觸護蓋，於操作位置設置可立即操作的緊急停止裝置。(工程改善)',
                '升降前確認平台周邊及下方無人，手腳離開剪叉臂與平台邊緣後才操作；多人作業由一人指揮操作。(管理控制)',
                '使用前測試緊急停止、上下限位、防止下降閥及護裙觸壓停止功能，異常時立即停用。(管理控制)',
            ], [
                ('平台下降時，人員手腳或身體位於剪叉臂交叉點、平台與底座或地面之間，遭剪切或夾壓。', 5, ['A1', 'A6', 'A7'], ['A1']),
                ('清潔、排除卡料或維修時，平台在升起狀態未以安全支撐桿或機械止擋支撐，油壓失壓或誤操作使平台突然下降，夾壓平台下方人員。', 5, ['A2', 'A3', 'A7'], ['A2', 'A3']),
                ('平台邊緣與鄰近輸送帶、機台或牆柱間距不足，升降時人員手部或身體被夾於平台與固定物之間。', 4, ['A4', 'A6'], ['A4']),
                ('控制按鈕或腳踏開關誤觸、卡滯，或多人作業未協調，平台突然升降夾傷正在放置物料的人員。', 5, ['A5', 'A6', 'A7'], ['A5']),
            ]),
            ('物體飛落', False, '物料偏載、堆疊過高或超過額定載重時，升降晃動可使物料由平台滑落擊中人員。', [
                '依銘牌額定載重及荷重分布使用，超重、偏載或尺寸超出平台時不得升降。(管理控制)',
                '平台設置側擋板或止滑台面，物料以束帶或擋塊固定後才升降。(工程改善)',
                '平台升起期間禁止人員停留於平台下方及物料可能掉落範圍。(管理控制)',
                '搬移物料時穿著具護趾的安全鞋，減輕物料掉落砸傷足部。(個人防護)',
            ], [
                ('物料堆疊過高、偏載或未固定，平台升降或停止時晃動，物料由平台邊緣滑落擊中人員。', 4, ['A2', 'A1', 'A4'], ['A2']),
                ('超過額定載重或集中荷重置於平台邊緣，平台傾斜或油壓缸失效下沉，物料傾倒掉落。', 4, ['A1', 'A3', 'A4'], ['A1']),
                ('平台升起時，人員在下方或側邊取放物料，工具或零件由平台掉落擊中人員。', 3, ['A3', 'A4'], ['A3']),
            ]),
            ('墜落、滾落', False, '升降台僅供物料，人員站上平台取放高處物料或設於凹坑的平台升起後留下開口，都可能失足墜落。', [
                '剪叉式升降台僅供物料升降，禁止人員站上平台或搭乘升降；高處取放改用合格工作台或高空工作車。(管理控制)',
                '於平台及操作位置明顯標示額定載重及禁止搭乘。(管理控制)',
                '設於凹坑內的升降台，平台升起時以護欄或護蓋封閉凹坑開口。(工程改善)',
            ], [
                ('人員站上平台搭乘升降或站在平台上取放高處物料，平台升降或晃動時失衡墜落。', 4, ['A1', 'A2'], ['A1']),
                ('平台設於凹坑內，平台升起後凹坑周邊形成開口，人員行經時跌落凹坑。', 3, ['A3'], ['A3']),
            ]),
            ('不當動作', False, '平台高度未配合作業者或硬推重物，反覆彎腰扭轉與突然施力會造成肌肉骨骼傷害。', [
                '依作業者身高與物料位置調整平台高度，使取放位置維持在腰部至胸部之間。(管理控制)',
                '選用具旋轉台面或滾輪台面的升降台，減少推拉及扭轉。(工程改善)',
                '重物以搬運輔具或雙人移位，禁止單人硬推硬拉。(管理控制)',
            ], [
                ('平台高度未調整至適當工作高度，人員反覆彎腰、扭轉或伸臂搬移物料，造成腰背或肩部扭傷。', 3, ['A2', 'A1'], ['A2']),
                ('由平台推拉重物或棧板時施力過大或突然用力，造成急性肌肉拉傷。', 3, ['A3', 'A2'], ['A3']),
            ]),
            ('感電', False, '控制箱、電纜或腳踏開關破損受潮，或維修未斷電，都可能使人員接觸帶電部位。', [
                '升降台電源迴路設置防止感電用漏電斷路器並確實接地。(工程改善)',
                '電纜及腳踏開關線以護套保護並避開車輪輾壓路徑，絕緣破損時停用更換。(管理控制)',
                '油壓泵浦及電氣元件維修由合格電氣人員斷電、上鎖掛牌並驗電後才作業。(管理控制)',
            ], [
                ('控制箱、電纜或腳踏開關絕緣破損、受潮或遭輾壓，人員操作或清潔時接觸帶電部位而感電。', 5, ['A1', 'A2'], ['A1']),
                ('維修油壓泵浦或電氣元件時未斷電上鎖，誤送電造成感電。', 5, ['A3'], ['A3']),
            ]),
            ('跌倒', False, '油壓油洩漏及散落包材使升降台周邊濕滑或有障礙物。', [
                '定期檢查油壓管路及油缸，發現滲漏立即停用修復並清除地面油污。(管理控制)',
                '升降台周邊保持通道淨空，包材及棧板集中放置。(管理控制)',
            ], [
                ('油壓油洩漏或地面散落包材、束帶，人員於升降台周邊行走或搬運時滑倒、絆倒。', 3, ['A1', 'A2'], ['A1']),
            ]),
        ],
        '專家決定：剪叉式升降台另列（固定於作業位置調整工件高度、不載人）')
    rows = e.industry
    added = []
    for r in [r for r in rows if r['taskId'] == '油壓升降平台作業']:
        prefix = r['id'].split('-')[0]
        new = {'id': next_id(rows, prefix), 'Industry': r['Industry'], 'sector': r['sector'], 'category': r['category'], 'taskId': name}
        rows.insert(rows.index(r) + 1, new)
        added.append(new['id'])
    e.note('industry_add', name, None, 'industryMapping', None, '、'.join(added), '比照油壓升降平台作業的行業與類別')


def ionizing_dosimeter(e):
    e.set_control('游離輻射作業', '職業病', 'A3',
        '人員進入管制區時依規定佩戴個人劑量計並確認校正期限及佩戴位置，發現異常劑量立即停工查明。(個人防護)',
        '人員進入管制區時依規定佩戴個人劑量計並確認校正期限及佩戴位置，發現異常劑量立即停工查明。(管理控制)',
        '專家決定：個人劑量計是劑量監測管理，不是防護具', allow_lane=True)


def crane_basket_industry(e):
    before = [r for r in e.industry if r['id'] == 'HH-004']
    assert len(before) == 1 and before[0]['taskId'] == '移動式起重機搭乘設備載人高處作業'
    e.industry.remove(before[0])
    assert any(r['taskId'] == '移動式起重機搭乘設備載人高處作業' and r['sector'] == '營造業' for r in e.industry)
    e.note('industry_remove', '移動式起重機搭乘設備載人高處作業', None, 'HH-004', json.dumps(before[0], ensure_ascii=False), None,
           '專家決定：設施規則第21-3條的吊籠作業指法定吊籠，搭乘設備移出危險性作業；營造業 CY-003 保留')


def gondola(e):
    d = json.loads(DRAFT.read_text(encoding='utf-8'))
    short = {
        ('墜落、滾落', 8): '支架、突樑或吊臂依製造商組配圖選型並依序組裝，F型支架間隔與卸放用鋼索間隔誤差不超過正負十公分；配重依規定數量重量固定，輔助鋼索與建築物緊密結合。(工程改善)',
        ('墜落、滾落', 46): '作業前訂定受困救援程序，指定手動升降操作人員、對講機等通訊方式及搶救器材，確認籠內人員失能或單人搭乘時可由外部操作下降，以及救命用纖維索懸吊時的救援方法。(管理控制)',
        ('被夾、被捲', 17): '台車走行與吊臂迴轉期間，屋頂人員站在走行路徑與迴轉範圍外，不站在台車、吊臂與女兒牆或屋頂設備之間；需靠近時先停止並切斷走行電源、掛牌，確認台車制動後才靠近。(管理控制)',
        ('高低溫接觸', 5): '作業者出現頭暈、噁心、抽筋或大量出汗時先停止作業，將工作台降至地面或屋頂進出位置，完全站上安全位置後才解除防墜器並到陰涼處休息，不得在高處解勾休息或攀出。(管理控制)',
    }
    reasons = {
        '墜落、滾落': '吊籠支撐固定、鋼索、安全裝置或人員勾掛任一失效，人員或工作台自高處墜落，是本作業致命主危害。',
        '物體飛落': '工作台、屋頂架設處及外牆剝落物自數層樓高度落下，可擊中下方人員或行人，須設管制區。',
        '被夾、被捲': '升降裝置鋼索入口與槽輪、工作台與外牆之間及常設型台車走行都會形成夾捲點。',
        '感電': '吊籠電源電纜在清洗潮濕環境漏電，或接近架空電線，電流可經鋼索與金屬工作台通過人員。',
        '被切、割、擦傷': '鋼索斷絲、金屬毛邊及修繕刀具可造成手部割傷。',
        '跌倒': '屋頂與工作台濕滑、負重上下樓梯及雜物占用通道，容易滑倒或絆倒。',
        '不當動作': '人力搬運配重、支架、工作台組件與鋼索捲容易造成腰背扭傷。',
        '有害物接觸': '清潔劑噴濺與霧滴，以及引擎式高壓清洗機排放一氧化碳，可造成灼傷或中毒。',
        '高低溫接觸': '夏季懸吊工作台日照與熱負荷高，熱衰竭停留高處會延誤降溫與送醫。',
        '火災': '工作台上使用引火性溶劑時遇火源起火，懸吊人員無法撤離。',
        '被撞': '地面管制區鄰接車道時，行駛或倒車車輛可能撞擊地面作業人員。',
    }
    groups = []
    for g in d['hazardGroups']:
        gname = g['groupName'][0]
        avoids = [short.get((gname, i), a) for i, a in enumerate(g['AvoidItems'], 1)]
        rows = []
        for r in g['hazardControlMap']:
            refs = [c['controlId'] for c in r['controlRefs']]
            rows.append((r['hazardItem'], r['severity'], refs, [c for c in r['coreControlRefs'] if c in refs]))
        assert [x[0] for x in rows] == g['hazarditems']
        groups.append((gname, gname in ('墜落、滾落', '物體飛落'), reasons[gname], avoids, rows))
    add_task(e, d['taskName'], d['taskdescribe'], groups,
             '專家決定：外牆吊籠新稿（cursor-gondola-20261104-r1）轉入正式作業庫；4 條超過 100 字的措施縮寫，嚴重度與必要設施沿用新稿')
    row = {'id': next_id(e.industry, 'HH'), 'Industry': '危險性作業', 'sector': '危險性作業', 'category': '具墜落危險之作業',
           'taskId': d['taskName']}
    anchor = max(i for i, r in enumerate(e.industry) if r['category'] == '具墜落危險之作業')
    e.industry.insert(anchor + 1, row)
    e.note('industry_add', d['taskName'], None, 'industryMapping', None, row['id'],
           '專家決定：編入危險性作業／具墜落危險之作業（設施規則第21-3條第1款第6目吊籠作業）')


def crane_certificates(e):
    R = ('專家決定依規定辦理：吊升荷重三公噸以上的固定式、移動式起重機及人字臂起重桿才屬危險性機械並須檢查合格證'
         '（危險性機械及設備安全檢查規則第3條）；操作資格依吊升荷重分為危險性機械操作人員訓練或技能檢定（教育訓練規則第12條）'
         '與特殊作業教育訓練（第14條）。塔式起重機不分荷重，不改')
    q = '使用起重機前確認操作人員資格符合吊升荷重要求；吊升荷重三公噸以上者另確認檢查合格證有效。(行政管理)'
    stop = '起重機檢查合格證逾期（三公噸以上者）、操作人員資格不符，或制動、吊具異常時，不得吊運。(行政管理)'
    full = ('吊升荷重三公噸以上的固定式或移動式起重機須有有效檢查合格證；操作人員依吊升荷重具備危險性機械操作訓練、'
            '技能檢定或特殊作業教育訓練，否則不得吊運。(行政管理)')
    for task, ids in [('施工構台組立與拆除作業', ('A6', 'A8', 'A11')), ('鋼筋吊運作業', ('A7', 'A9', 'A11')),
                      ('鋼構構件進場卸運作業', ('A9', 'A11', 'A12'))]:
        g, _ = e.group(task, '物體飛落')
        for aid, new in zip(ids, (q, stop, full)):
            old = g['AvoidItems'][int(aid[1:]) - 1]
            assert '檢查合格證' in old and '操作證' in old, (task, aid, old)
            e.set_control(task, '物體飛落', aid, old, new, R)
    e.set_control('固定式起重機吊掛作業', '物體飛落', 'A9',
        '起吊前確認起重機檢查合格證有效，並檢查過捲預防裝置、制動、離合、控制及警報。(行政管理)',
        '起吊前檢查過捲預防裝置、制動、離合、控制及警報；吊升荷重三公噸以上者另確認檢查合格證有效。(行政管理)', R)
    e.set_control('固定式起重機吊掛作業', '物體飛落', 'A13',
        '起吊前確認起重機檢查合格證有效，並檢查吊鉤舌片、鋼索及吊具。(行政管理)',
        '起吊前檢查吊鉤舌片、鋼索及吊具；吊升荷重三公噸以上者另確認檢查合格證有效。(行政管理)', R)
    e.set_control('移動式起重機吊掛作業', '物體飛落', 'A2',
        '作業前確認起重機檢查合格證仍有效。(行政管理)',
        '吊升荷重三公噸以上的移動式起重機，作業前確認檢查合格證仍有效。(行政管理)', R)
    e.set_control('移動式起重機吊掛作業', '物體飛落', 'A11',
        '移動式起重機作業前確認檢查合格證有效並檢查煞車、起升限位及過負荷預防裝置。(行政管理)',
        '移動式起重機作業前檢查煞車、起升限位及過負荷預防裝置；吊升荷重三公噸以上者另確認檢查合格證有效。(行政管理)', R)
    e.set_control('人字臂起重桿組裝與拆卸作業', '物體飛落', 'A6',
        '組拆前須確認檢查合格證仍有效，設備安全裝置及部件均無異常。(行政管理)',
        '組拆前確認設備安全裝置及部件均無異常；吊升荷重三公噸以上者另確認檢查合格證有效。(行政管理)', R)
    e.set_control('人字臂起重桿組裝與拆卸作業', '物體飛落', 'A7',
        '組拆及吊掛僅由持有效操作證人員執行；逾期或異常不得作業。(行政管理)',
        '組拆及吊掛由依吊升荷重受相應訓練或技能檢定合格人員執行；資格不符或設備異常不得作業。(行政管理)', R)


def heat_and_scope(e):
    T = '設備管路原地循環清洗作業'
    e.append_hazard(T, '職業病',
        '高溫清洗液、蒸汽管線及清洗槽周邊高溫高濕，通風不足且長時間巡檢、接管或拆檢，熱負荷累積可能造成熱衰竭、熱痙攣等熱疾病。',
        4, ['A2', 'A3'], ['A2'],
        '專家決定：原有熱環境措施 A2、A3 沒有情境，新增熱疾病情境並引用',
        extra={'recoveryReview': 'pending', 'severityReviewRequired': True, 'ruleSeverity': 4, 'ruleSeverityBasis': '職業病（待專家覆核）'})
    T = '吊掛熔融金屬澆鑄桶作業'
    old = e.library[T]['taskdescribe']
    e.set_describe(T, old, old.replace(
        '澆注前後應保持吊掛狀態或依流程降放、解鉤，並完成作業後檢點。作業範圍包括吊具選配、起吊、運搬、定位、降放及解鉤。',
        '澆注時以起重機吊持澆鑄桶傾轉澆注，澆注前後清除桶口結渣，並依流程降放、解鉤及完成作業後檢點。'
        '作業範圍包括吊具選配、起吊、運搬、定位、澆注、清渣、降放及解鉤。'),
        '專家決定：作業範圍擴及澆注與清渣（既有情境已涵蓋）')


def supply_air(e):
    e.append_hazard('異常氣壓作業', '職業病',
        '壓縮機吸入口受污染或潤滑油霧、一氧化碳混入供氣，人員在艙內長時間吸入，可能造成呼吸道傷害或慢性中毒。',
        4, ['A4', 'A16'], ['A4'],
        '專家決定：供氣品質檢驗 A4 原未引用，新增供氣污染情境並引用；潛水作業另立作業，本次不納入',
        extra={'recoveryReview': 'pending', 'severityReviewRequired': True, 'ruleSeverity': 4, 'ruleSeverityBasis': '職業病（待專家覆核）'})


def patch_editor():
    orig_set = Editor._set_control

    def _set_control(self, task, g, index, text, reason, kind='control', allow_lane=False):
        if allow_lane:
            before = g['AvoidItems'][index]
            g['AvoidItems'][index] = text
            if body_key(before) != body_key(text):
                self.key_renames.setdefault(task, {})[body_key(before)] = body_key(text)
            self.note('label', task, g['groupName'], f'A{index + 1}', before, text, reason)
            return
        orig_set(self, task, g, index, text, reason, kind)

    def set_control(self, task, group, aid, old, new, reason, allow_lane=False):
        g, _ = self.group(task, group)
        i = int(aid[1:]) - 1
        assert g['AvoidItems'][i] == old, (task, group, aid, g['AvoidItems'][i])
        _set_control(self, task, g, i, new, reason, allow_lane=allow_lane)

    orig_append = Editor.append_hazard

    def append_hazard(self, task, group, text, severity, refs, cores, reason, extra=None):
        hid = orig_append(self, task, group, text, severity, refs, cores, reason)
        if extra:
            _, doc = self.group(task, group)
            doc['hazardControlMap'][-1].update(extra)
        return hid

    Editor._set_control, Editor.set_control, Editor.append_hazard = _set_control, set_control, append_hazard


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    patch_editor()
    e = Editor()
    prior = json.loads((REPO / 'audit' / 'equipment_fixes_20261104b.json').read_text(encoding='utf-8'))
    e.renames, e.avoid_remap, e.key_renames = prior['taskRenames'], prior['avoidIndexRemap'], prior['controlKeyRenames']
    start = len(prior['changes'])
    e.log = prior['changes']
    scissor_lift(e)
    ionizing_dosimeter(e)
    crane_basket_industry(e)
    gondola(e)
    crane_certificates(e)
    heat_and_scope(e)
    supply_air(e)
    for c in e.log[start:]:
        c['phase'] = PHASE
    e.maps['counts']['groups'] = len(e.maps['maps'])
    e.finish(args.dry_run)


if __name__ == '__main__':
    main()
