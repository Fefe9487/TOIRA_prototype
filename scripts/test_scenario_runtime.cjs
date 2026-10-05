/* Exercise the actual assessment-page parser and legacy state migration. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const repo = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(repo, 'New.html'), 'utf8');
for (const [, code] of html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/g)) {
  if (code.trim()) new vm.Script(code);
}
function extract(name) {
  const start = html.indexOf(`        function ${name}(`);
  assert(start >= 0, name);
  const end = html.indexOf('\n        }', start);
  assert(end > start, name);
  return html.slice(start, end + '\n        }'.length);
}
const names = ['controlBodyKey', 'controlLane', 'scoreLaneOf', 'controlIdOf', 'avoidTextById',
  'scenariosFromMapDoc', 'attachScenarioMaps', 'probabilityFromLinkedControls', 'migrateScenarioSelections'];
const context = vm.createContext({});
vm.runInContext("const DATA_VER = '20261005h';\n" + names.map(extract).join('\n'), context);
const read = name => JSON.parse(fs.readFileSync(path.join(repo, name), 'utf8'));
const library = read('tasksLibrary.json');
const maps = read('scenarioMaps.json');
const migration = read('scenarioMigration.json');
let groups = 0, hazards = 0, controls = 0;
for (const [id, task] of Object.entries(library)) {
  task.id = id;
  context.attachScenarioMaps(task, maps.maps);
  for (const group of task.hazardGroups) {
    assert.deepEqual(Array.from(group.scenarios, s => s.text), group.hazardItems);
    assert(group.scenarios.every(s => /^S[1-5]$/.test(s.severity) && s.controls.length));
    groups += 1;
    hazards += group.scenarios.length;
    controls += group.scenarios.reduce((n, s) => n + s.controls.length, 0);
    for (const scenario of group.scenarios) {
      assert.equal(context.probabilityFromLinkedControls(scenario.controls, {}), 'P5');
    }
  }
}
assert.equal(groups, 1400);
assert.equal(hazards, 6193);
assert.equal(controls, 18334);
const manualTask = library['人工搬運作業'];
const manualGroupIndex = manualTask.hazardGroups.findIndex(g => g.groupName === '職業病');
assert.equal(manualTask.hazardGroups[manualGroupIndex].scenarios.length, 5);
const group = manualTask.hazardGroups[manualGroupIndex];
const corrupted = {...maps.maps.find(g => g.taskName === manualTask.taskName && g.groupName === '職業病')};
corrupted.hazardControlMap = [{...corrupted.hazardControlMap[0], hazardItem: '不一致'}];
assert.throws(() => context.scenariosFromMapDoc(group, corrupted), /情境文字與作業庫不一致/);
const key = `${manualTask.id}_${manualGroupIndex}`;
const original = {scenarios: [0], scenarioManual: {0: {isManual: true, manualS: 'S3', manualP: 'P2'}},
  scenarioExtras: {0: [{text: '原有自訂措施', lane: '工程改善', done: true}]}, customScenarios: [], avoids: [0]};
const snapshot = {dataVersion: '20261005g', userSelections: {[key]: structuredClone(original)}};
context.migrateScenarioSelections(snapshot, [manualTask], migration);
const state = snapshot.userSelections[key];
assert.deepEqual(Array.from(state.scenarios), [0, 1, 2, 3, 4]);
assert.equal(Object.keys(state.scenarioManual).length, 0);
assert.equal(Object.keys(state.scenarioExtras).length, 0);
assert.equal(state.customScenarios[0].selected, false);
assert.equal(state.customScenarios[0].manualS, 'S3');
assert.equal(state.customScenarios[0].measures[0], '原有自訂措施');
assert.equal(state.scenarioMigrationBackup.scenarioExtras[0][0].done, true);
assert.deepEqual(state.avoids, [0]);
const migratedOnce = JSON.stringify(snapshot);
context.migrateScenarioSelections(snapshot, [manualTask], migration);
assert.equal(JSON.stringify(snapshot), migratedOnce);
// An exact hazard moved from index 1 to index 2 in chemical intake.
const chemical = library['化學品入料作業'];
const chemicalIndex = chemical.hazardGroups.findIndex(g => g.groupName === '職業病');
const change = migration.groups.find(g => g.taskName === chemical.taskName && g.groupName === '職業病');
const newIndex = change.exactOldIndices.findIndex(i => i !== null && i !== change.exactOldIndices.indexOf(i));
assert(newIndex >= 0);
const oldIndex = change.exactOldIndices[newIndex];
const exactState = {scenarios: [oldIndex], scenarioManual: {[oldIndex]: {isManual: true, manualS: 'S4', manualP: 'P3'}},
  scenarioExtras: {[oldIndex]: [{text: '保留措施', done: true}]}};
const exactSnapshot = {userSelections: {[`${chemical.id}_${chemicalIndex}`]: exactState}};
context.migrateScenarioSelections(exactSnapshot, [chemical], migration);
assert(exactState.scenarios.includes(newIndex));
assert.equal(exactState.scenarioManual[newIndex].manualP, 'P3');
assert.equal(exactState.scenarioExtras[newIndex][0].done, true);
assert.equal(exactState.customScenarios.length, 0);
assert.throws(() => context.migrateScenarioSelections({dataVersion: '20261005g'}, [], null), /原儲存資料已保留/);
assert.throws(() => context.migrateScenarioSelections({dataVersion: 'unknown'}, [], migration), /另行核對/);
console.log(JSON.stringify({groups, hazards, controls, exactTextJoin: true, legacySplitMigration: true,
  legacyExactIndexMigration: true, migrationIdempotent: true, corruptMapRejected: true}, null, 2));
