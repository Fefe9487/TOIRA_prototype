#!/usr/bin/env python3
"""Batch candidate review with an already-configured local OpenAI-compatible model (Strata / LM Studio).

The model only produces structured candidates under audit/local_ai/. Nothing here writes
tasksLibrary.json or scenarioMaps.json; Cursor/reviewers decide what to apply.

Connection is never guessed:
  --base-url  or env LOCAL_AI_BASE_URL / LM_STUDIO_BASE_URL   (e.g. http://<lan-host>:1234/v1)
  --key-file  or env LOCAL_AI_KEY_FILE                         (file holding the bearer key)
  --model     or env LOCAL_AI_MODEL; when omitted, the single model listed by /v1/models is used.

Modes:
  unreferenced  classify AvoidItems not referenced by any scenario as A/B/C/D (one batch per task chunk)
  consistency   task name / description / equipment keyword consistency (one batch per task)

Run:
  python scripts/local_ai_review.py unreferenced
  python scripts/local_ai_review.py consistency --tasks 油壓升降平台作業
"""
import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / 'audit' / 'local_ai'
MAX_UNREF_PER_BATCH = 18

UNREF_PROMPT = """你是台灣職業安全衛生資料品質審查助理。只做資料比對，不判斷法規適用性。
以下是一項作業的部分危害群組。每組列出：情境（H編號）、已被情境引用的措施（A編號）、以及「未被任何情境引用」的措施。
請逐一分類每一條未引用措施：
A＝該作業／設備確實需要的必要安全裝置或必要措施，但目前沒有情境引用它（應補引用到某情境）
B＝已有意思相同或涵蓋它的已引用措施（重複或被拆句取代）
C＝不適用於這項作業或這種設備（例如混入其他設備、其他作業的措施）
D＝合理的補充措施，但目前沒有直接對應的情境

規則：
1. evidence 必須逐字引用輸入中的原文片段（至少 8 個字），不可改寫。
2. equivalentIds、targetHazardIds 只能使用輸入中出現過的編號，格式為「群組名/A3」「群組名/H2」。
3. 不得引用或編造法規條號、設備規格。
4. B 類要填 equivalentIds；A 類要填 targetHazardIds；C 類在 reason 說明混入了什麼設備或作業。
5. 只輸出 JSON，不要任何說明文字。

輸出格式：
{"items":[{"id":"群組名/A5","category":"A|B|C|D","equivalentIds":[],"targetHazardIds":[],"evidence":"原文片段","reason":"30字內","confidence":0.0,"requiresLegalReview":false}]}

作業名稱：{taskName}
作業說明：{taskdescribe}

{groups}
"""

CONSISTENCY_PROMPT = """你是台灣職業安全衛生資料品質審查助理。只找出資料中的具體問題，不判斷法規最終適用性。
請檢查這一項作業：
1. equipment_mismatch：情境或措施提到的設備，與作業名稱／說明的設備類型不一致（例如貨用設備卻寫載人、把起重機吊掛用具檢查放進非起重作業）。
2. scope_conflict：作業說明的範圍與情境內容互相矛盾，或同一作業混合多種法規分類不同的設備。
3. duplicate_hazard：同一群組內意思相同的情境。
4. duplicate_control：同一群組內意思相同的措施。
5. wording：明顯錯字、冗詞、語句不通或設備名稱不一致。
6. label_mismatch：措施末尾控制層級標籤與內容明顯不符（例如純管理行為卻標工程改善）。

規則：
- evidence 必須逐字引用輸入原文（至少 8 個字）。
- affectedIds 只能用輸入中出現的編號（「群組名/H2」「群組名/A3」，或 "taskName"、"taskdescribe"）。
- 不得編造法規條號、設備特性或不存在的編號。沒有問題就輸出空陣列。
- 最多列 12 項，優先列 severity 高者。只輸出 JSON。

輸出格式：
{"issues":[{"taskName":"{taskName}","issueType":"equipment_mismatch","severity":"high|medium|low","evidence":"原文片段","suggestion":"建議修改方向","affectedIds":[],"confidence":0.0,"requiresLegalReview":true}]}

作業名稱：{taskName}
作業說明：{taskdescribe}

{groups}
"""

LABEL_PROMPT = """你是台灣職業安全衛生資料品質審查助理。下列每條防護措施末尾都標「工程改善」，請判斷標籤是否合理。

判斷原則（只看措施本身的主要作用）：
- 工程改善：改變設備、設施、場所或製程本身的實體措施，設置後不靠人員每次執行也持續有效。例如設置護罩、裝設連鎖、加裝局部排氣、改用低危害設備、鋪設止滑地坪、補足照明、調整工作台高度。
- 管理控制：依賴人員執行的程序、檢查、確認、禁止、限制、標示、清潔整理、維修保養、教育訓練或作業安排。例如作業前確認、異常時停用、禁止進入、保持通道淨空、拆卸前先釋放能量。
- 個人防護：要求人員穿戴防護具。
- 一句同時有實體措施與管理行為時，以句子要求的主要屏障判斷；實體設備只是被檢查或維持的對象時，屬管理控制。

規則：evidence 必須逐字引用該措施原文（至少 6 字）；id 只能用輸入中的編號；只輸出 JSON。

輸出格式：
{"items":[{"id":"L12","label":"工程改善|管理控制|個人防護","evidence":"原文片段","reason":"20字內","confidence":0.0}]}

{items}
"""
LABELS = {'工程改善', '管理控制', '個人防護'}
LABEL_BATCH = 30
CATEGORIES = {'A', 'B', 'C', 'D'}
ISSUE_TYPES = {'equipment_mismatch', 'scope_conflict', 'duplicate_hazard', 'duplicate_control', 'wording', 'label_mismatch'}
SEVERITIES = {'high', 'medium', 'low'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def load_data(library_path, maps_path):
    library = read(library_path)
    maps = read(maps_path)
    docs = {(d['taskName'], d['groupName']): d for d in maps['maps']}
    return library, docs


def referenced(doc):
    return {r for row in doc['hazardControlMap'] for r in row['controlRefs']}


def id_texts(task, docs):
    """All addressable IDs of one task -> original text."""
    out = {'taskName': task['taskName'], 'taskdescribe': task['taskdescribe']}
    for g in task['hazardGroups']:
        for i, h in enumerate(g['hazardItems'], 1):
            out[f"{g['groupName']}/H{i}"] = h
        for i, a in enumerate(g['AvoidItems'], 1):
            out[f"{g['groupName']}/A{i}"] = a
    return out


def build_unreferenced_batches(library, docs, only=None):
    batches = []
    for name, task in library.items():
        if only and name not in only:
            continue
        chunks, current, count = [], [], 0
        for g in task['hazardGroups']:
            doc = docs[(name, g['groupName'])]
            used = referenced(doc)
            unref = [i for i in range(1, len(g['AvoidItems']) + 1) if f'A{i}' not in used]
            if not unref:
                continue
            if current and count + len(unref) > MAX_UNREF_PER_BATCH:
                chunks.append(current)
                current, count = [], 0
            current.append((g, unref, used))
            count += len(unref)
        if current:
            chunks.append(current)
        for n, chunk in enumerate(chunks, 1):
            lines, targets = [], []
            for g, unref, used in chunk:
                gn = g['groupName']
                lines.append(f"### 群組：{gn}")
                lines += [f"{gn}/H{i} {h}" for i, h in enumerate(g['hazardItems'], 1)]
                lines.append('已引用措施：')
                lines += [f"{gn}/A{i} {a}" for i, a in enumerate(g['AvoidItems'], 1) if f'A{i}' in used]
                lines.append('未引用措施（請分類）：')
                lines += [f"{gn}/A{i} {g['AvoidItems'][i - 1]}" for i in unref]
                lines.append('')
                targets += [f"{gn}/A{i}" for i in unref]
            batches.append({'batchId': f"unref::{name}::{n}", 'taskName': name, 'targets': targets,
                            'prompt': UNREF_PROMPT.replace('{taskName}', name)
                            .replace('{taskdescribe}', task['taskdescribe']).replace('{groups}', '\n'.join(lines))})
    return batches


def build_consistency_batches(library, docs, only=None):
    batches = []
    for name, task in library.items():
        if only and name not in only:
            continue
        lines = []
        for g in task['hazardGroups']:
            gn = g['groupName']
            used = referenced(docs[(name, gn)])
            lines.append(f"### 群組：{gn}")
            lines += [f"{gn}/H{i} {h}" for i, h in enumerate(g['hazardItems'], 1)]
            lines += [f"{gn}/A{i} {a}" for i, a in enumerate(g['AvoidItems'], 1) if f'A{i}' in used]
            lines.append('')
        batches.append({'batchId': f"consistency::{name}", 'taskName': name, 'targets': [],
                        'prompt': CONSISTENCY_PROMPT.replace('{taskName}', name)
                        .replace('{taskdescribe}', task['taskdescribe']).replace('{groups}', '\n'.join(lines))})
    return batches


def build_label_batches(candidates):
    """candidates from audit/label_candidates.json; ids L1..Ln are stable within that file."""
    batches = []
    for start in range(0, len(candidates), LABEL_BATCH):
        chunk = candidates[start:start + LABEL_BATCH]
        lines, targets = [], {}
        for n, c in enumerate(chunk, start + 1):
            lid = f'L{n}'
            targets[lid] = c
            lines.append(f"{lid}（{c['taskName']}／{c['groupName']}）{c['text']}")
        batches.append({'batchId': f'labels::{start // LABEL_BATCH + 1}', 'taskName': f'labels-{start // LABEL_BATCH + 1}',
                        'targets': list(targets), 'candidates': targets,
                        'prompt': LABEL_PROMPT.replace('{items}', '\n'.join(lines))})
    return batches


def validate_labels(obj, batch, _ids):
    errors, valid, seen = [], [], set()
    items = obj.get('items')
    if not isinstance(items, list):
        return [], ['items missing']
    for it in items:
        lid = it.get('id') if isinstance(it, dict) else None
        problems = []
        if lid not in batch['candidates']:
            problems.append(f'unknown id {lid}')
        elif it.get('label') not in LABELS:
            problems.append(f'bad label {it.get("label")}')
        elif not evidence_ok(it.get('evidence', ''), [batch['candidates'][lid]['text']]):
            problems.append('evidence not verbatim')
        if not isinstance(it.get('confidence') if isinstance(it, dict) else None, (int, float)):
            problems.append('confidence missing')
        if problems:
            errors.append(f'{lid}: ' + '; '.join(problems))
        elif lid not in seen:
            seen.add(lid)
            c = batch['candidates'][lid]
            valid.append({**it, 'taskName': c['taskName'], 'groupName': c['groupName'], 'controlId': c['id'], 'text': c['text']})
    missing = [t for t in batch['targets'] if t not in seen]
    return valid, errors + ([f'missing {len(missing)} targets: {missing[:10]}'] if missing else [])


class Client:
    def __init__(self, base_url, key, model, timeout):
        self.base_url, self.key, self.model, self.timeout = base_url.rstrip('/'), key, model, timeout

    def _req(self, path, payload=None):
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8') if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, method='POST' if data else 'GET',
                                     headers={'Authorization': f'Bearer {self.key}', 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req, timeout=self.timeout) as res:
            return json.loads(res.read().decode('utf-8'))

    def models(self):
        return [m['id'] for m in self._req('/models').get('data', [])]

    def chat(self, prompt, max_tokens):
        res = self._req('/chat/completions', {
            'model': self.model, 'temperature': 0, 'max_tokens': max_tokens,
            'messages': [{'role': 'system', 'content': '只輸出有效 JSON。'}, {'role': 'user', 'content': prompt}]})
        return res['choices'][0]['message'].get('content') or '', res.get('usage', {})


def parse_json(text):
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text)
    start = text.find('{')
    end = text.rfind('}')
    if start < 0 or end < start:
        raise ValueError('no JSON object')
    return json.loads(text[start:end + 1])


def norm(s):
    return re.sub(r'[\s，。、；：「」（）()]', '', s or '')


def evidence_ok(evidence, texts):
    ev = norm(evidence)
    return len(ev) >= 6 and any(ev in norm(t) for t in texts)


def validate_unref(obj, batch, ids):
    errors, valid = [], []
    items = obj.get('items')
    if not isinstance(items, list):
        return [], ['items missing']
    seen = set()
    for it in items:
        problems = []
        if not isinstance(it, dict):
            errors.append('item not object')
            continue
        iid = it.get('id')
        if iid not in batch['targets']:
            problems.append(f'unknown/non-target id {iid}')
        if it.get('category') not in CATEGORIES:
            problems.append(f'bad category {it.get("category")}')
        for key in ('equivalentIds', 'targetHazardIds'):
            vals = it.get(key, [])
            if not isinstance(vals, list) or any(v not in ids for v in vals):
                problems.append(f'{key} has unknown ids {vals}')
        if it.get('category') == 'B' and not it.get('equivalentIds'):
            problems.append('B without equivalentIds')
        if it.get('category') == 'A' and not it.get('targetHazardIds'):
            problems.append('A without targetHazardIds')
        if not isinstance(it.get('confidence'), (int, float)):
            problems.append('confidence missing')
        refs = [ids.get(iid, '')] + [ids[v] for v in it.get('equivalentIds', []) + it.get('targetHazardIds', []) if v in ids]
        if not evidence_ok(it.get('evidence', ''), refs or list(ids.values())):
            problems.append('evidence not verbatim')
        if problems:
            errors.append(f'{iid}: ' + '; '.join(problems))
        elif iid not in seen:
            seen.add(iid)
            valid.append(it)
    missing = [t for t in batch['targets'] if t not in seen]
    return valid, errors + ([f'missing {len(missing)} targets'] if missing else [])


def validate_consistency(obj, batch, ids):
    errors, valid = [], []
    issues = obj.get('issues')
    if not isinstance(issues, list):
        return [], ['issues missing']
    for it in issues:
        problems = []
        if not isinstance(it, dict):
            errors.append('issue not object')
            continue
        if it.get('issueType') not in ISSUE_TYPES:
            problems.append(f'bad issueType {it.get("issueType")}')
        if it.get('severity') not in SEVERITIES:
            problems.append('bad severity')
        aff = it.get('affectedIds', [])
        if not isinstance(aff, list) or any(a not in ids for a in aff):
            problems.append(f'unknown affectedIds {aff}')
        if not isinstance(it.get('confidence'), (int, float)) or not isinstance(it.get('requiresLegalReview'), bool):
            problems.append('confidence/requiresLegalReview missing')
        refs = [ids[a] for a in aff if a in ids] or list(ids.values())
        if not evidence_ok(it.get('evidence', ''), refs):
            problems.append('evidence not verbatim')
        if problems:
            errors.append('; '.join(problems))
        else:
            it['taskName'] = batch['taskName']
            valid.append(it)
    return valid, errors


def run_batch(client, batch, ids, mode, max_tokens, retries):
    record = {'batchId': batch['batchId'], 'taskName': batch['taskName'], 'mode': mode, 'model': client.model,
              'attempts': [], 'status': 'failed', 'valid': [], 'errors': []}
    prompt = batch['prompt']
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            text, usage = client.chat(prompt, max_tokens)
            obj = parse_json(text)
            validator = {'unreferenced': validate_unref, 'consistency': validate_consistency, 'labels': validate_labels}[mode]
            valid, errors = validator(obj, batch, ids)
        except Exception as exc:  # noqa: BLE001 - recorded and retried
            text, usage, valid, errors = locals().get('text', ''), {}, [], [f'{type(exc).__name__}: {exc}']
        record['attempts'].append({'seconds': round(time.time() - t0, 1), 'usage': usage, 'errors': errors[:20],
                                   'raw': text[:20000]})
        if valid and not errors:
            record.update(status='ok', valid=valid, errors=[])
            return record
        if valid:
            record.update(status='partial', valid=valid, errors=errors)
        if attempt < retries:
            prompt = batch['prompt'] + '\n\n上一次輸出有下列問題，請修正後重新輸出完整 JSON：\n' + '\n'.join(errors[:15])
    if record['status'] == 'failed':
        record['errors'] = record['attempts'][-1]['errors']
    return record


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('mode', choices=['unreferenced', 'consistency', 'labels'])
    ap.add_argument('--base-url', default=os.environ.get('LOCAL_AI_BASE_URL') or os.environ.get('LM_STUDIO_BASE_URL'))
    ap.add_argument('--key-file', default=os.environ.get('LOCAL_AI_KEY_FILE'))
    ap.add_argument('--model', default=os.environ.get('LOCAL_AI_MODEL'))
    ap.add_argument('--tasks', nargs='*')
    ap.add_argument('--tasks-file', type=Path, help='UTF-8 file, one task name per line')
    ap.add_argument('--library', type=Path, default=REPO / 'tasksLibrary.json', help='review a fixed snapshot')
    ap.add_argument('--maps', type=Path, default=REPO / 'scenarioMaps.json')
    # The shared local server is slow and can run out of memory; keep requests strictly sequential.
    ap.add_argument('--workers', type=int, default=1, choices=[1])
    ap.add_argument('--retries', type=int, default=1)
    ap.add_argument('--max-tokens', type=int, default=12000)
    ap.add_argument('--timeout', type=int, default=900)
    ap.add_argument('--limit', type=int)
    ap.add_argument('--redo-failed', action='store_true')
    args = ap.parse_args()
    if not args.base_url or not args.key_file:
        sys.exit('Set --base-url/--key-file (or LOCAL_AI_BASE_URL / LOCAL_AI_KEY_FILE); local AI stage skipped.')
    key = Path(args.key_file).read_text(encoding='utf-8').strip()
    client = Client(args.base_url, key, args.model, args.timeout)
    available = client.models()
    if not client.model:
        if len(available) != 1:
            sys.exit(f'Pick --model from {available}')
        client.model = available[0]
    elif client.model not in available:
        sys.exit(f'Model {client.model} not served; available: {available}')

    library, docs = load_data(args.library, args.maps)
    wanted = list(args.tasks or [])
    if args.tasks_file:
        wanted += [n.strip() for n in args.tasks_file.read_text(encoding='utf-8').splitlines() if n.strip()]
    unknown = [n for n in wanted if n not in library]
    if unknown:
        sys.exit(f'Unknown tasks: {unknown}')
    only = set(wanted) if wanted else None
    if args.mode == 'labels':
        batches = build_label_batches(read(REPO / 'audit' / 'label_candidates.json'))
    else:
        batches = (build_unreferenced_batches if args.mode == 'unreferenced' else build_consistency_batches)(library, docs, only)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f'{args.mode}.jsonl'
    done = {}
    if out_path.exists():
        for line in out_path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                rec = json.loads(line)
                done[rec['batchId']] = rec
    todo = [b for b in batches if b['batchId'] not in done or (args.redo_failed and done[b['batchId']]['status'] != 'ok')]
    if args.limit:
        todo = todo[:args.limit]
    print(f'model={client.model} batches={len(batches)} todo={len(todo)}', flush=True)
    lock = threading.Lock()
    ids_by_task = {name: id_texts(task, docs) for name, task in library.items()}

    def work(batch):
        ids = ids_by_task.get(batch['taskName'], {})
        return run_batch(client, batch, ids, args.mode, args.max_tokens, args.retries)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(work, b): b for b in todo}
        for n, fut in enumerate(as_completed(futures), 1):
            rec = fut.result()
            with lock:
                done[rec['batchId']] = rec
                with out_path.open('w', encoding='utf-8') as fh:
                    for r in done.values():
                        fh.write(json.dumps(r, ensure_ascii=False) + '\n')
            print(f"[{n}/{len(todo)}] {rec['status']:7s} {rec['batchId']} valid={len(rec['valid'])} "
                  f"t={sum(a['seconds'] for a in rec['attempts'])}s", flush=True)


if __name__ == '__main__':
    main()
