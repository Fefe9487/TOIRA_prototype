#!/usr/bin/env python3
"""Validate exact joins, control IDs, metadata, and historical repair invariants.

Run: python scripts/validate_scenario_maps.py --annotation ../evluate_risk_assessment
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def validate(repo, annotation=None):
    library = read(repo / 'tasksLibrary.json')
    maps = read(repo / 'scenarioMaps.json')
    groups = {(t['taskName'], g['groupName']): g for t in library.values() for g in t['hazardGroups']}
    seen = set()
    hazards = cores = controls = 0
    for doc in maps['maps']:
        key = doc['taskName'], doc['groupName']
        assert key in groups and key not in seen, f'Broken/duplicate group join: {key}'
        seen.add(key)
        group = groups[key]
        rows = doc['hazardControlMap']
        assert [r['hazardItem'] for r in rows] == group['hazardItems'], f'Hazard text/order mismatch: {key}'
        for i, row in enumerate(rows, 1):
            assert set(row) == {'hazardId', 'hazardItem', 'severity', 'controlRefs', 'coreControlRefs'}
            assert row['hazardId'] == f'H{i}', (key, 'hazardId', i)
            assert type(row['severity']) is int and 1 <= row['severity'] <= 5, (key, i, 'severity')
            refs, core_refs = row['controlRefs'], row['coreControlRefs']
            assert refs and len(refs) == len(set(refs)), (key, i, 'missing/duplicate controls')
            assert len(core_refs) == len(set(core_refs)) and set(core_refs) <= set(refs), (key, i, 'core refs')
            assert all(re.fullmatch(r'A[1-9]\d*', r) and int(r[1:]) <= len(group['AvoidItems'])
                       and group['AvoidItems'][int(r[1:]) - 1].strip() for r in refs), (key, i, 'control IDs')
            hazards += 1
            cores += bool(core_refs)
            controls += len(refs)
    assert seen == set(groups), 'Missing library groups'
    assert maps['counts']['groups'] == len(groups)
    assert maps['counts']['hazards'] == hazards
    assert maps['counts']['coreHazards'] == cores
    for name in ['New.html', 'Selection.html']:
        assert re.search(r"const DATA_VER = '([^']+)'", (repo / name).read_text()).group(1) == maps['version']
    report = read(repo / 'SCENARIO_TEXT_REPAIR.json')
    assert report['version'] == maps['version']
    assert hashlib.sha256((repo / 'tasksLibrary.json').read_bytes()).hexdigest() == report['sources']['tasksLibrarySha256']
    base = report['sources']['prototypeCommit']
    old = json.loads(subprocess.check_output(['git', '-C', str(repo), 'show', f'{base}:scenarioMaps.json']))
    old_docs = {(g['taskName'], g['groupName']): g for g in old['maps']}
    changed = {(g['taskName'], g['groupName']): g for g in report['groups']}
    preserved_rows = reconstructed = 0
    for doc in maps['maps']:
        key = doc['taskName'], doc['groupName']
        prior = old_docs[key]
        if key not in changed:
            assert doc == prior, f'Unrelated group changed: {key}'
            continue
        audit = changed[key]
        assert len(audit['rows']) == len(doc['hazardControlMap'])
        old_rows = {r['hazardId']: r for r in prior['hazardControlMap']}
        for row, evidence in zip(doc['hazardControlMap'], audit['rows']):
            assert all(row[k] == evidence[k] for k in row)
            sources = [old_rows[h] for h in evidence['sourceHazardIds']]
            if evidence['method'] == 'exact-text-preserved':
                assert {k: v for k, v in row.items() if k != 'hazardId'} == {k: v for k, v in sources[0].items() if k != 'hazardId'}
                preserved_rows += 1
            else:
                assert row['severity'] == max(s['severity'] for s in sources)
                historical_cores = {r for s in sources for r in s['coreControlRefs']}
                assert row['coreControlRefs'] == [r for r in row['controlRefs'] if r in historical_cores]
                reconstructed += 1
    assert len(changed) == 60 and reconstructed == 197
    migration = read(repo / 'scenarioMigration.json')
    assert migration['toVersion'] == maps['version'] and migration['fromVersion'] == old['version']
    for item in migration['groups']:
        key = item['taskName'], item['groupName']
        assert item['oldHazardItems'] == [r['hazardItem'] for r in old_docs[key]['hazardControlMap']]
        assert len(item['newSourceIndices']) == len(groups[key]['hazardItems']) == len(item['exactOldIndices'])
        for index, sources in enumerate(item['newSourceIndices']):
            assert sources and all(0 <= s < len(item['oldHazardItems']) for s in sources)
            exact = item['exactOldIndices'][index]
            if exact is not None:
                assert groups[key]['hazardItems'][index] == item['oldHazardItems'][exact]
    if annotation:
        assert (annotation / 'scenarioMaps.json').read_bytes() == (repo / 'scenarioMaps.json').read_bytes()
        expert_library = read(annotation / 'data/library.json')
        assert expert_library['dataVersion'] == maps['version']
        assert re.search(r'const DATA_VER = "([^"]+)"', (annotation / 'index.html').read_text()).group(1) == maps['version']
        for task in expert_library['tasks']:
            for group in task['hazardGroups']:
                key = task['taskName'], group['groupName']
                assert group['hazardItems'] == groups[key]['hazardItems']
                assert group['AvoidItems'] == groups[key]['AvoidItems']
                doc = next(d for d in maps['maps'] if (d['taskName'], d['groupName']) == key)
                expected = [f"S{r['severity']}" for r in doc['hazardControlMap']]
                assert group['hazardSeverities'] == expected, (key, 'annotator severity')
                assert group['sourceSeverities'] == expected
                assert group['severitySources'] == ['scenarioMaps'] * len(expected)
        for name in ['data/assignments.json', 'data/library_full.json', 'data/library_fat.json']:
            prior = subprocess.check_output(['git', '-C', str(annotation), 'show', f"{report['sources']['expertCommit']}:{name}"])
            assert prior == (annotation / name).read_bytes(), f'Historical/review data changed: {name}'
    return {'version': maps['version'], 'tasks': len(library), 'groups': len(groups), 'hazards': hazards,
            'controlReferences': controls, 'hazardTextMismatches': 0, 'invalidControlRefs': 0,
            'changedGroups': 60, 'unchangedGroups': len(groups) - 60, 'reconstructedRows': reconstructed,
            'preservedRowsInChangedGroups': preserved_rows, 'rowsWithoutHistoricalApplicableCore': hazards - cores,
            'annotationSynchronized': bool(annotation)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annotation', type=Path)
    args = parser.parse_args()
    print(json.dumps(validate(Path(__file__).resolve().parents[1], args.annotation.resolve() if args.annotation else None),
                     ensure_ascii=False, indent=2))
