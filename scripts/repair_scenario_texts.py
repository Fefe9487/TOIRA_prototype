#!/usr/bin/env python3
"""Rebuild the 60 mismatched groups from pinned history; never edit library text.

Run: python scripts/repair_scenario_texts.py --annotation ../evluate_risk_assessment
Requires both historical commits in the local Git object databases.
"""
import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path

PROTOTYPE_BASE = 'd761bfab5617016a209c75691580850712c75da2'
ANNOTATION_BASE = '8367026b9231fa599d74ad2007c28925cbce158f'
VERSION = '20261005h'
STAMP = '2026-10-05T10:29:11Z'


def historical(repo, commit, name):
    return json.loads(subprocess.check_output(['git', '-C', str(repo), 'show', f'{commit}:{name}']))


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def run(annotation):
    repo = Path(__file__).resolve().parents[1]
    original = historical(repo, PROTOTYPE_BASE, 'scenarioMaps.json')
    library = historical(repo, PROTOTYPE_BASE, 'tasksLibrary.json')
    assert json.loads((repo / 'tasksLibrary.json').read_text()) == library, 'Source library changed; rebase the plan.'
    expert = historical(annotation, ANNOTATION_BASE, 'data/library_full.json')
    expert_groups = {(t['taskName'], g['groupName']): g for t in expert['tasks'] for g in t['hazardGroups']}
    source_groups = {(t['taskName'], g['groupName']): g for t in library.values() for g in t['hazardGroups']}
    plan = json.loads((repo / 'scripts/scenario_reconstruction_plan.json').read_text())
    plans = {(p['taskName'], p['groupName']): p['rows'] for p in plan}
    repaired = copy.deepcopy(original)
    provenance = []
    migrations = []
    for doc in repaired['maps']:
        key = (doc['taskName'], doc['groupName'])
        if key not in plans:
            continue
        group = source_groups[key]
        assert expert_groups[key]['hazardItems'] == group['hazardItems'], key
        old = doc['hazardControlMap']
        old_by_text = {r['hazardItem']: (i, r) for i, r in enumerate(old)}
        new = []
        audit_rows = []
        source_indices = []
        exact_indices = []
        for i, text in enumerate(group['hazardItems']):
            if text in old_by_text:
                old_index, row = old_by_text[text]
                row = copy.deepcopy(row)
                sources = [old_index]
                exact_index = old_index
                method = 'exact-text-preserved'
            else:
                item = plans[key][str(i + 1)]
                sources = [int(h[1:]) - 1 for h in item['sourceHazardIds']]
                assert all(0 <= s < len(old) for s in sources)
                core = {ref for s in sources for ref in old[s]['coreControlRefs']}
                refs = item['controlRefs']
                assert refs and len(refs) == len(set(refs))
                assert all(1 <= int(r[1:]) <= len(group['AvoidItems']) for r in refs)
                row = {'hazardItem': text, 'severity': max(old[s]['severity'] for s in sources),
                       'controlRefs': refs, 'coreControlRefs': [r for r in refs if r in core]}
                exact_index = None
                method = 'reconstructed-from-history-and-current-control-pool'
            row = {'hazardId': f'H{i + 1}', **{k: v for k, v in row.items() if k != 'hazardId'}}
            new.append(row)
            source_indices.append(sources)
            exact_indices.append(exact_index)
            old_refs = {r for s in sources for r in old[s]['controlRefs']}
            audit_rows.append({'hazardId': row['hazardId'], 'hazardItem': text, 'method': method,
                              'sourceHazardIds': [old[s]['hazardId'] for s in sources],
                              'sourceHazardItems': [old[s]['hazardItem'] for s in sources],
                              'severity': row['severity'], 'controlRefs': row['controlRefs'],
                              'coreControlRefs': row['coreControlRefs'],
                              'additionalPoolRefs': [r for r in row['controlRefs'] if r not in old_refs]})
        doc['hazardControlMap'] = new
        provenance.append({'taskName': key[0], 'groupName': key[1], 'oldCount': len(old),
                           'newCount': len(new), 'rows': audit_rows})
        migrations.append({'taskName': key[0], 'groupName': key[1],
                           'oldHazardItems': [r['hazardItem'] for r in old],
                           'newSourceIndices': source_indices, 'exactOldIndices': exact_indices})
    assert len(provenance) == 60
    all_rows = [r for g in repaired['maps'] for r in g['hazardControlMap']]
    repaired.update(version=VERSION, generatedAt=STAMP)
    repaired['counts'].update(groups=len(repaired['maps']), hazards=len(all_rows),
                              coreHazards=sum(bool(r['coreControlRefs']) for r in all_rows),
                              unmatchedLibraryGroups=0)
    report = {'schema': 'toira-scenario-text-repair', 'version': VERSION, 'generatedAt': STAMP,
              'sources': {'prototypeRepository': 'Fefe9487/TOIRA_prototype', 'prototypeCommit': PROTOTYPE_BASE,
                          'expertRepository': 'Fefe9487/evluate_risk_assessment', 'expertCommit': ANNOTATION_BASE,
                          'expertFile': 'data/library_full.json',
                          'tasksLibrarySha256': hashlib.sha256((repo / 'tasksLibrary.json').read_bytes()).hexdigest()},
              'policy': {'hazardText': 'Exact current library text, corroborated by historical expert draft.',
                         'severity': 'Exact rows unchanged; reconstructed rows inherit maximum contributing historical S.',
                         'controls': 'Reviewed linkage to existing AvoidItems only; no new control wording.',
                         'coreControls': 'Intersection with contributing historical core refs; no automatic promotion.',
                         'reviewStatus': 'Structural checks passed separately; reconstructed semantic links await expert review.'},
              'summary': {'changedGroups': 60, 'unchangedGroups': len(repaired['maps']) - 60,
                          'reconstructedRows': sum(r['method'].startswith('reconstructed') for g in provenance for r in g['rows']),
                          'oldHazards': original['counts']['hazards'], 'newHazards': len(all_rows)},
              'groups': provenance}
    migration = {'schema': 'toira-scenario-index-migration', 'fromVersion': original['version'],
                 'toVersion': VERSION, 'groups': migrations}
    write(repo / 'scenarioMaps.json', repaired)
    write(repo / 'scenarioMigration.json', migration)
    write(repo / 'SCENARIO_TEXT_REPAIR.json', report)
    write(annotation / 'scenarioMaps.json', repaired)
    annotation_library = historical(annotation, ANNOTATION_BASE, 'data/library.json')
    maps = {(g['taskName'], g['groupName']): g for g in repaired['maps']}
    for task in annotation_library['tasks']:
        for group in task['hazardGroups']:
            rows = maps[(task['taskName'], group['groupName'])]['hazardControlMap']
            assert group['hazardItems'] == [r['hazardItem'] for r in rows]
            if (task['taskName'], group['groupName']) in plans:
                group['hazardSeverities'] = [f"S{r['severity']}" for r in rows]
                group['severitySources'] = ['scenarioMaps'] * len(rows)
                group['sourceSeverities'] = list(group['hazardSeverities'])
    annotation_library.update(dataVersion=VERSION, syncedOn='2026-10-05', generatedAt=STAMP,
                              sourceCommitBeforeEdit=PROTOTYPE_BASE, sourceCommit=PROTOTYPE_BASE,
                              sourceRepair='SCENARIO_TEXT_REPAIR.json')
    write(annotation / 'data/library.json', annotation_library)
    write(annotation / 'SCENARIO_TEXT_REPAIR.json', report)
    print(json.dumps(report['summary'], ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--annotation', required=True, type=Path)
    run(parser.parse_args().annotation.resolve())
