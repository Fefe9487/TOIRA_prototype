#!/usr/bin/env python3
"""Cursor-side review of local-AI control-lane suggestions (audit/local_ai/labels.jsonl).

Accepted downgrade to 管理控制: AI says 管理控制 with confidence >= 0.8 and the sentence has no physical-provision cue.
Accepted change to 個人防護: AI says 個人防護 and the sentence is about wearing protective equipment.
Everything else stays 工程改善; AI 管理控制 suggestions blocked by a cue or with low confidence go to the expert queue.
Writes audit/label_review.json.

Run: python scripts/review_label_candidates.py
"""
import collections
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MIN_CONFIDENCE = 0.8
# A physical item is provided or installed: keep 工程改善 even if the sentence also has procedural parts.
PHYSICAL = re.compile(r'設[^定計法備想]|裝設|安裝|加裝|裝置|警報|屏|照明|燈|地坪|止滑|防滑|護套|護角|導流|圍堵|集液|排水|隔熱|遮陽|遮蔽|通風|排氣|'
                      r'過濾|固定式|架|台車|推車|輔具|墊|欄|網|蓋|罩|鋪|改用|改採|選用|更換為|密閉|配置')
PPE = re.compile(r'穿戴|配戴|佩戴|穿著|戴上|手套|護目|面罩|口罩|呼吸防護|安全帽|安全鞋|耳塞|耳罩|防護衣|圍裙|袖套')


def main():
    recs = [json.loads(l) for l in (REPO / 'audit' / 'local_ai' / 'labels.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    candidates = json.loads((REPO / 'audit' / 'label_candidates.json').read_text(encoding='utf-8'))
    decided = {}
    for r in recs:
        for v in r['valid']:
            body = re.sub(r'[（(][^）)]*[）)]\s*$', '', v['text'])
            if v['label'] == '管理控制' and v['confidence'] >= MIN_CONFIDENCE and not PHYSICAL.search(body):
                decision, to, note = 'accepted', '管理控制', '無實體設置線索，屬人員執行的程序或檢查'
            elif v['label'] == '管理控制':
                cue = PHYSICAL.search(body)
                decision, to, note = 'pending', None, (f'句中有實體設置線索「{cue.group(0)}」' if cue else f'AI 信心 {v["confidence"]} 不足') + '，待專家'
            elif v['label'] == '個人防護' and PPE.search(body):
                decision, to, note = 'accepted', '個人防護', '內容為穿戴防護具'
            elif v['label'] == '個人防護':
                decision, to, note = 'pending', None, 'AI 判個人防護但句中沒有防護具，待專家'
            else:
                decision, to, note = 'rejected', None, 'AI 判為工程改善，維持'
            decided[(v['taskName'], v['groupName'], v['controlId'])] = {
                'taskName': v['taskName'], 'groupName': v['groupName'], 'id': v['controlId'], 'text': v['text'],
                'aiLabel': v['label'], 'confidence': v['confidence'], 'aiReason': v.get('reason', ''),
                'decision': decision, 'newLabel': to, 'note': note}
    items = []
    for c in candidates:
        key = (c['taskName'], c['groupName'], c['id'])
        item = decided.get(key) or {'taskName': c['taskName'], 'groupName': c['groupName'], 'id': c['id'], 'text': c['text'],
                                    'aiLabel': None, 'decision': 'pending', 'newLabel': None, 'note': 'AI 無有效輸出'}
        item['core'] = c['core']
        items.append(item)
    summary = collections.Counter((i['decision'], i['newLabel']) for i in items)
    out = {'candidates': len(items), 'summary': {f'{d}:{n}': k for (d, n), k in summary.items()},
           'coreChanged': sum(1 for i in items if i['decision'] == 'accepted' and i['core']), 'items': items}
    (REPO / 'audit' / 'label_review.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k != 'items'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
