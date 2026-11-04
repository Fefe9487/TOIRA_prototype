#!/usr/bin/env python3
"""Summarize local-AI candidates and Cursor review decisions.

Inputs:  audit/local_ai/unreferenced.jsonl, audit/local_ai/consistency.jsonl (from local_ai_review.py)
         audit/local_ai/cursor_review.json  {"decisions": [{"mode", "taskName", "id", "decision", "note"}]}
           decision: accepted | rejected | pending ; id = AI item id (unreferenced) or issue index "#n" (consistency)
Outputs: audit/local_ai/summary.json, audit/local_ai/review_queue.md

AI ids refer to the reviewed snapshot (tasksLibrary.json.bak-equip-20261104); task names are mapped through
taskRenames so the queue shows current names. Group-local control numbers may have shifted where
avoidIndexRemap lists the group.

Run: python scripts/summarize_local_ai.py
"""
import collections
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AI = REPO / 'audit' / 'local_ai'


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]


LABEL = re.compile(r'[（(][^）)]*[）)]\s*$')
B_COVERAGE = 0.6


def bigrams(text):
    s = re.sub(r'[\s，。、；：「」]', '', LABEL.sub('', text or ''))
    return {s[i:i + 2] for i in range(len(s) - 1)}


def b_coverage(snapshot, task, item):
    """Share of the unreferenced sentence's character bigrams found in the cited equivalent sentences."""
    groups = {g['groupName']: g for g in snapshot[task]['hazardGroups']}

    def text(ident):
        group, aid = ident.rsplit('/', 1)
        return groups[group]['AvoidItems'][int(aid[1:]) - 1]
    own = bigrams(text(item['id']))
    other = set().union(*(bigrams(text(i)) for i in item['equivalentIds']))
    return len(own & other) / len(own) if own else 0.0


def current_id(fixes, renames, task, ident):
    """Map a snapshot id (group/A7) to the current task name and control number, or None if deleted."""
    task = renames.get(task, task)
    group, aid = ident.rsplit('/', 1)
    table = fixes['avoidIndexRemap'].get(f'{task}\u0000{group}')
    index = int(aid[1:]) - 1
    if table is not None:
        index = table[index] if index < len(table) else index
        if index is None:
            return None
    return task, group, f'A{index + 1}'


def final_unreferenced(fixes, renames, by_key, snapshot):
    """Final class of every currently unreferenced control: Cursor decision > rule-checked AI B > audit rule B."""
    current = json.loads((REPO / 'audit' / 'unreferenced_controls.json').read_text(encoding='utf-8'))
    decided = {}
    for r in read_jsonl(AI / 'unreferenced.jsonl'):
        for v in r['valid']:
            key = current_id(fixes, renames, r['taskName'], v['id'])
            if not key:
                continue
            d = by_key.get(('unreferenced', key[0], v['id']))
            if d:
                if d['decision'] == 'accepted':
                    decided[key] = v['category']
                elif d['decision'] == 'rejected':
                    m = re.search(r'改判\s*([ABCD])', d['note'])
                    decided[key] = m.group(1) if m else 'pending'
                else:
                    decided[key] = 'pending'
            elif v['category'] == 'B' and b_coverage(snapshot, r['taskName'], v) >= B_COVERAGE:
                decided[key] = 'B'
    counts, priority = collections.Counter(), collections.Counter()
    for u in current:
        key = (u['taskName'], u['groupName'], u['id'])
        cls = decided.get(key) or ('B' if u['ruleClass'] == 'B' else 'unclassified')
        counts[cls] += 1
        if u['priorityDevices']:
            priority[cls] += 1
    return {'total': len(current), 'classes': dict(counts), 'priorityDeviceClasses': dict(priority)}


def main():
    snapshot = json.loads((REPO / 'tasksLibrary.json.bak-equip-20261104').read_text(encoding='utf-8'))
    fixes = json.loads((REPO / 'audit' / 'equipment_fixes_20261104b.json').read_text(encoding='utf-8'))
    renames = fixes['taskRenames']
    review_path = AI / 'cursor_review.json'
    decisions = json.loads(review_path.read_text(encoding='utf-8'))['decisions'] if review_path.exists() else []
    by_key = {(d['mode'], renames.get(d['taskName'], d['taskName']), d['id']): d for d in decisions}
    summary, queue = {}, ['# 本地 AI 候選與 Cursor 複核佇列', '',
                          'AI 只提供候選；「採納」表示 Cursor 依原文與法規複核後已套用或確認分類，「待確認」需職安衛專家判斷。', '']
    for mode in ('unreferenced', 'consistency'):
        recs = read_jsonl(AI / f'{mode}.jsonl')
        status = collections.Counter(r['status'] for r in recs)
        items, decided = [], collections.Counter()
        for r in recs:
            task = renames.get(r['taskName'], r['taskName'])
            for n, v in enumerate(r['valid'], 1):
                ident = v['id'] if mode == 'unreferenced' else f'#{n}'
                d = by_key.get((mode, task, ident))
                if not d and mode == 'unreferenced' and v['category'] == 'B':
                    cov = b_coverage(snapshot, r['taskName'], v)
                    if cov >= B_COVERAGE:
                        d = {'decision': 'accepted', 'note': f'規則複核：等效句字元雙連覆蓋 {cov:.0%}，保留原句不引用'}
                decided[d['decision'] if d else 'unreviewed'] += 1
                items.append((task, ident, v, d))
        cats = collections.Counter(v['category'] for _, _, v, _ in items) if mode == 'unreferenced' else \
            collections.Counter(v['issueType'] for _, _, v, _ in items)
        summary[mode] = {
            'batches': len(recs), 'batchStatus': dict(status),
            'attempts': sum(len(r['attempts']) for r in recs),
            'validOutputs': len(items), 'failedBatches': [r['batchId'] for r in recs if r['status'] == 'failed'],
            'categories': dict(cats), 'cursorDecisions': dict(decided),
            'seconds': round(sum(a['seconds'] for r in recs for a in r['attempts'])),
        }
        queue += [f'## {mode}', '', f"批次 {len(recs)}（{dict(status)}），有效輸出 {len(items)}，Cursor 決定 {dict(decided)}", '']
        for task, ident, v, d in items:
            if mode == 'unreferenced':
                ref = ','.join(v.get('equivalentIds') or v.get('targetHazardIds') or [])
                line = f"- {task}／{ident}：AI={v['category']}（{v['confidence']}）{ref} {v['reason']}"
            else:
                line = f"- {task} {ident}：{v['issueType']}／{v['severity']}（{v['confidence']}）{v['suggestion']}　證據：「{v['evidence']}」"
            line += f"　→ Cursor：{d['decision']}（{d['note']}）" if d else '　→ 未複核'
            queue.append(line)
        queue.append('')
    summary['finalUnreferenced'] = final_unreferenced(fixes, renames, by_key, snapshot)
    (AI / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (AI / 'review_queue.md').write_text('\n'.join(queue) + '\n', encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
