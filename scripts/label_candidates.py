#!/usr/bin/env python3
"""List referenced controls labelled 工程改善／工程控制 whose sentence has no engineering action.

Deterministic pre-filter for the local-AI label review (local_ai_review.py labels). Writes audit/label_candidates.json.

Run: python scripts/label_candidates.py
"""
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENG_LABEL = re.compile(r'[（(](工程改善|工程控制)[）)]\s*$')
# Physical change to equipment, layout or process; a sentence with none of these is a review candidate.
ENGINEERING = re.compile(
    r'設置|裝設|加裝|安裝|增設|架設|鋪設|設有|配置[^人]|改用|改採|採用|選用|換用|更換為|替代|取代|密閉|自動|連鎖|聯鎖|局部排氣|'
    r'排氣裝置|護罩|護欄|護蓋|護圍|圍籬|防護網|安全網|擋板|止擋|止滑|隔音|減振|消音|隔熱|接地|漏電|斷路器|感測|偵測|'
    r'警報器|防爆|固定式|機械式|導軌|支撐架|支架|吊具|夾具|治具|輔具|台車|推車|升降台|捲揚|輸送|遮蔽|屏障|隔離設施|'
    r'防止脫落裝置|過捲|限位|緊急停止|急停|制動|墊木|墊板|通風')


def main():
    library = json.loads((REPO / 'tasksLibrary.json').read_text(encoding='utf-8'))
    maps = json.loads((REPO / 'scenarioMaps.json').read_text(encoding='utf-8'))
    docs = {(d['taskName'], d['groupName']): d for d in maps['maps']}
    out, total = [], 0
    for name, task in library.items():
        for g in task['hazardGroups']:
            rows = docs[(name, g['groupName'])]['hazardControlMap']
            used = {r for row in rows for r in row['controlRefs']}
            core = {r for row in rows for r in row['coreControlRefs']}
            for i, a in enumerate(g['AvoidItems'], 1):
                if f'A{i}' not in used or not ENG_LABEL.search(a):
                    continue
                total += 1
                if not ENGINEERING.search(ENG_LABEL.sub('', a)):
                    out.append({'taskName': name, 'groupName': g['groupName'], 'id': f'A{i}', 'text': a,
                                'core': f'A{i}' in core})
    (REPO / 'audit').mkdir(exist_ok=True)
    (REPO / 'audit' / 'label_candidates.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({'referencedEngineeringControls': total, 'candidates': len(out),
                      'coreCandidates': sum(c['core'] for c in out),
                      'tasks': len({c['taskName'] for c in out})}, ensure_ascii=False))


if __name__ == '__main__':
    main()
