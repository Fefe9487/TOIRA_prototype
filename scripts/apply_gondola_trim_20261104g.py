#!/usr/bin/env python3
"""Replace 建築物外牆吊籠清洗及維護作業 with the trimmed cursor-jsa draft (cursor-gondola-20261104-r3), round 20261104g.

The r1 draft imported in 20261104d had 232 controls; r3 merges same-lane, same-timing controls into 129. Scenarios,
their order and severities are unchanged, so only control indices and checkbox keys need migration.
The old -> new control mapping is read from the draft's qa.json semanticCompression record and its
before-compression snapshot, never guessed from text similarity.

Writes tasksLibrary.json, scenarioMaps.json and audit/gondola_trim_20261104g.json
(AVOID_INDEX_REMAP_20261104G / CONTROL_KEY_RENAMES_20261104G for New.html).
Run once: python scripts/apply_gondola_trim_20261104g.py [--dry-run]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_equipment_fixes_20261104b import LABEL_RE, REPO, body_key  # noqa: E402

VERSION = '20261104g'
TASK = '建築物外牆吊籠清洗及維護作業'
DRAFT_DIR = REPO.parent / 'gen4' / 'out' / 'cursor-jsa' / TASK
# Library texts that 20261104d shortened to stay within 100 characters, keyed by (group, A number).
SHORTENED = {('墜落、滾落', 8), ('墜落、滾落', 46), ('被夾、被捲', 17), ('高低溫接觸', 5)}


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    draft = load(DRAFT_DIR / '作業表.json')
    qa = load(DRAFT_DIR / 'qa.json')
    assert qa['status'] == 'complete' and qa['artifact']['current'], 'draft QA must be complete'
    review = qa['semanticCompression']
    before_dir = (DRAFT_DIR / review['beforeManifest']).parent
    changes = {r['group']: r for r in review['groupReviews']}

    library = load(REPO / 'tasksLibrary.json')
    maps = load(REPO / 'scenarioMaps.json')
    task = library[TASK]
    remap, renames, log = {}, {}, []
    for lib_group, new in zip(task['hazardGroups'], draft['hazardGroups']):
        name = lib_group['groupName']
        assert new['groupName'] == [name], (name, new['groupName'])
        old_draft = load(before_dir / 'groups' / f'{name}.json')['AvoidItems']
        old_lib = lib_group['AvoidItems']
        assert len(old_lib) == len(old_draft), name
        for i, (a, b) in enumerate(zip(old_lib, old_draft), 1):
            assert a == b or (name, i) in SHORTENED, (name, i)
        doc = next(d for d in maps['maps'] if d['taskName'] == TASK and d['groupName'] == name)
        assert [r['hazardItem'] for r in doc['hazardControlMap']] == new['hazarditems'], (name, 'scenarios changed')
        assert lib_group['hazardItems'] == new['hazarditems'], name
        target = {}
        for change in changes[name]['controlChanges']:
            for src in change['from']:
                target[src] = change['to'][0] if change['to'] else None
        new_index = {text: i for i, text in enumerate(new['AvoidItems'])}
        table = []
        for i, text in enumerate(old_draft):
            dest = target.get(text, text)
            table.append(None if dest is None else new_index[dest])
            if dest is not None and body_key(old_lib[i]) != body_key(dest):
                renames[body_key(old_lib[i])] = body_key(dest)
        remap[f'{TASK}\u0000{name}'] = table
        for text in new['AvoidItems']:
            assert LABEL_RE.search(text) and len(body_key(text)) <= 100, (name, text)
        rows = []
        for old_row, row in zip(doc['hazardControlMap'], new['hazardControlMap']):
            assert old_row['severity'] == row['severity'], (name, row['hazardId'])
            refs = [c['controlId'] for c in row['controlRefs']]
            rows.append({'hazardId': row['hazardId'], 'hazardItem': row['hazardItem'], 'severity': row['severity'],
                         'controlRefs': refs, 'coreControlRefs': row['coreControlRefs'],
                         'ruleSeverity': old_row['ruleSeverity'], 'ruleSeverityBasis': old_row['ruleSeverityBasis']})
        log.append({'groupName': name, 'controlsBefore': len(old_lib), 'controlsAfter': len(new['AvoidItems']),
                    'linksBefore': sum(len(r['controlRefs']) for r in doc['hazardControlMap']),
                    'linksAfter': sum(len(r['controlRefs']) for r in rows)})
        lib_group['AvoidItems'] = new['AvoidItems']
        doc['hazardControlMap'] = rows
    maps['counts']['coreHazards'] = sum(bool(r['coreControlRefs']) for d in maps['maps'] for r in d['hazardControlMap'])
    out = {'version': VERSION, 'taskName': TASK,
           'source': {'draft': f'gen4/out/cursor-jsa/{TASK}/作業表.json', 'runId': qa['runId'],
                      'artifactSha256': qa['artifact']['sha256']},
           'reason': '使用者回饋措施過多、像流水帳；以 r3 精簡版取代 20261104d 匯入的 r1 版，情境與嚴重度不變。',
           'avoidIndexRemap': remap, 'controlKeyRenames': {TASK: renames}, 'groups': log}
    print(json.dumps(log, ensure_ascii=False))
    if args.dry_run:
        return
    (REPO / 'tasksLibrary.json').write_text(json.dumps(library, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (REPO / 'scenarioMaps.json').write_text(json.dumps(maps, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (REPO / 'audit' / f'gondola_trim_{VERSION}.json').write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n',
                                                                 encoding='utf-8')
    print('written')


if __name__ == '__main__':
    main()
