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
const names = ['normalizeSeverity', 'hazardTypeKey', 'statisticalSeverity', 'controlBodyKey', 'controlLane', 'scoreLaneOf', 'controlIdOf', 'avoidTextById',
  'scenariosFromMapDoc', 'attachScenarioMaps', 'probabilityFromLinkedControls', 'remapAvoidSelections', 'renameSnapshotTasks', 'renameControlKeys',
  'applyEquipmentAudit20261104b', 'migrateScenarioSelections'];
const context = vm.createContext({});
const DATA_VER = html.match(/const DATA_VER = '([^']+)'/)[1];
const riskMatrix = html.match(/const riskMatrix = (\{[\s\S]*?\});/)[1];
const severityTable = html.match(/const STAT_SEVERITY_BY_TYPE = (\{[\s\S]*?\});/)[1];
const avoidRemap = html.match(/const AVOID_INDEX_REMAP_20261021A = (\{[\s\S]*?\});/)[1];
const taskRenames = html.match(/const TASK_RENAMES = (\{.*\});/)[1];
const avoidRemapB = html.match(/const AVOID_INDEX_REMAP_20261104B = (\{.*\});/)[1];
const keyRenamesB = html.match(/const CONTROL_KEY_RENAMES_20261104B = (\{.*\});/)[1];
vm.runInContext(`const DATA_VER = '${DATA_VER}';\nconst riskMatrix = ${riskMatrix};\nconst STAT_SEVERITY_BY_TYPE = ${severityTable};\n`
  + `const AVOID_INDEX_REMAP_20261021A = ${avoidRemap};\nconst TASK_RENAMES = ${taskRenames};\n`
  + `const AVOID_INDEX_REMAP_20261104B = ${avoidRemapB};\nconst CONTROL_KEY_RENAMES_20261104B = ${keyRenamesB};\n`
  + names.map(extract).join('\n'), context);
const fixLog = JSON.parse(fs.readFileSync(path.join(repo, 'audit', 'equipment_fixes_20261104b.json'), 'utf8'));
assert.deepEqual(JSON.parse(taskRenames), fixLog.taskRenames);
assert.deepEqual(JSON.parse(avoidRemapB), fixLog.avoidIndexRemap);
assert.deepEqual(JSON.parse(keyRenamesB), fixLog.controlKeyRenames);
function linked(items, checked) {
  return context.probabilityFromLinkedControls(items.map(([key, lane, core]) => ({ key, scoreLane: lane, core })), checked);
}
// 必要設施的工程與個人防護已完成、管理改善未完成 → P3。措施全勾才是 P2。
assert.equal(linked([['eng', 'E', true], ['ppe', 'P', true], ['adm', 'M', false]], { eng: true, ppe: true }), 'P3');
assert.equal(linked([['eng', 'E', true], ['ppe', 'P', true], ['adm', 'M', false]], { eng: true, ppe: true, adm: true }), 'P2');
assert.equal(linked([['eng', 'E', true], ['ppe', 'P', true], ['adm', 'M', false]], {}), 'P5');
assert.equal(linked([['eng', 'E', true], ['ppe', 'P', true], ['adm', 'M', false]], { eng: true }), 'P4');
assert.equal(linked([['eng', 'E', true], ['ppe', 'P', true]], { eng: true, ppe: true }), 'P3');
assert.equal(linked([['adm', 'M', true], ['ppe', 'P', true]], { adm: true, ppe: true }), 'P3');
assert.equal(linked([['eng', 'E', true], ['adm1', 'M', false], ['adm2', 'M', false]], { eng: true, adm1: true }), 'P3');
assert.equal(linked([['eng', 'E', true], ['adm', 'M', false], ['ppe', 'P', false]], { eng: true, adm: true }), 'P3');
assert.equal(linked([['eng', 'E', true], ['adm', 'M', false], ['ppe', 'P', false]], { eng: true, adm: true, ppe: true }), 'P2');
assert.equal(linked([['eng', 'E', true], ['adm', 'M', false], ['ppe1', 'P', false], ['ppe2', 'P', false]], { eng: true, adm: true, ppe1: true }), 'P3');
assert.equal(linked([['eng', 'E', true], ['adm', 'M', true], ['ppe', 'P', true]], { eng: true, adm: true }), 'P4');
assert.equal(linked([['eng', 'E', true], ['ppe', 'P', false]], { ppe: true }), 'P5');
assert.equal(linked([['eng', 'E', false], ['adm', 'M', false]], { eng: true, adm: true }), 'P3');
assert.equal(linked([['eng1', 'E', false], ['eng2', 'E', false]], { eng1: true }), 'P4');
assert.equal(linked([['eng', 'E', false]], {}), 'P5');
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
assert.equal(groups, maps.maps.length);
assert.equal(groups, maps.counts.groups);
assert.equal(hazards, maps.counts.hazards);
assert.equal(controls, maps.maps.reduce((n, doc) => n + doc.hazardControlMap.reduce((m, row) => m + row.controlRefs.length, 0), 0));
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
// 20261021a 刪除滾輪／鍛轤操作作業「高低溫接觸」舊 A3、A9：已勾措施依新編號前移，其他群組不動。
const roller = library['滾輪／鍛轤操作作業'];
const rollerIndex = roller.hazardGroups.findIndex(g => g.groupName === '高低溫接觸');
const otherIndex = roller.hazardGroups.findIndex(g => g.groupName !== '高低溫接觸');
assert.equal(roller.hazardGroups[rollerIndex].AvoidItems.length, 8);
for (const fromVersion of ['20261005h', '20261020a', '20261005g']) {
  const selections = {
    [`${roller.id}_${rollerIndex}`]: {scenarios: [0], avoids: [0, 2, 3, 8, 9]},
    [`${roller.id}_${otherIndex}`]: {scenarios: [], avoids: [2, 8]}
  };
  const remapSnapshot = {dataVersion: fromVersion, userSelections: selections};
  context.migrateScenarioSelections(remapSnapshot, [roller], migration);
  assert.equal(remapSnapshot.dataVersion, DATA_VER);
  assert.deepEqual(Array.from(selections[`${roller.id}_${rollerIndex}`].avoids), [0, 2, 7], fromVersion);
  assert.deepEqual(Array.from(selections[`${roller.id}_${otherIndex}`].avoids), [2, 8], fromVersion);
  context.migrateScenarioSelections(remapSnapshot, [roller], migration);
  assert.deepEqual(Array.from(selections[`${roller.id}_${rollerIndex}`].avoids), [0, 2, 7], `${fromVersion} idempotent`);
}
// 20261104b：舊作業名稱、群組內刪除措施的編號前移、改寫措施的勾選鍵複製。
const derrick = library['人字臂起重桿組裝與拆卸作業'];
const derrickFall = derrick.hazardGroups.findIndex(g => g.groupName === '墜落、滾落');
const derrickDrop = derrick.hazardGroups.findIndex(g => g.groupName === '物體飛落');
const rope = library['高處繩索接近作業'];
const ropeDrop = rope.hazardGroups.findIndex(g => g.groupName === '物體飛落');
const oldKey = '組拆前確認人字臂起重機檢查合格證仍在有效期限內，並由持有效操作證的人員操作。';
const newKey = context.controlBodyKey(derrick.hazardGroups[derrickDrop].AvoidItems[9]);
for (const fromVersion of ['20261104a', '20261027a', '20261021a', '20261020a', '20261005h']) {
  const snap = {
    dataVersion: fromVersion,
    myProjectTasks: ['人字臂起重機組裝與拆卸作業', '高處繩索接近作業'],
    userSelections: {
      [`人字臂起重機組裝與拆卸作業_${derrickFall}`]: {scenarios: [0, 2], avoids: [0, 8, 1]},
      [`人字臂起重機組裝與拆卸作業_${derrickDrop}`]: {scenarios: [4], avoids: [9]},
      [`高處繩索接近作業_${ropeDrop}`]: {scenarios: [], avoids: [5, 6, 7, 8, 11]}
    },
    taskControlChecks: {'人字臂起重機組裝與拆卸作業': {[oldKey]: true}}
  };
  context.migrateScenarioSelections(snap, [derrick, rope, roller], migration);
  assert.equal(snap.dataVersion, DATA_VER);
  assert.deepEqual(Array.from(snap.myProjectTasks), ['人字臂起重桿組裝與拆卸作業', '高處繩索接近作業']);
  assert(!Object.keys(snap.userSelections).some(k => k.startsWith('人字臂起重機')));
  assert.deepEqual(Array.from(snap.userSelections[`人字臂起重桿組裝與拆卸作業_${derrickFall}`].avoids), [0, 1], fromVersion);
  assert.deepEqual(Array.from(snap.userSelections[`人字臂起重桿組裝與拆卸作業_${derrickFall}`].scenarios), [0, 2]);
  assert.deepEqual(Array.from(snap.userSelections[`人字臂起重桿組裝與拆卸作業_${derrickDrop}`].avoids), [9]);
  assert.deepEqual(Array.from(snap.userSelections[`高處繩索接近作業_${ropeDrop}`].avoids), [5, 6, 9], fromVersion);
  assert.equal(snap.taskControlChecks['人字臂起重桿組裝與拆卸作業'][newKey], true);
  const once = JSON.stringify(snap);
  context.migrateScenarioSelections(snap, [derrick, rope, roller], migration);
  assert.equal(JSON.stringify(snap), once, `${fromVersion} idempotent`);
}
// 必要設施補強：新增情境可載入，且未勾任何措施時為 P5。
for (const [task, group, text] of [['人字臂起重桿組裝與拆卸作業', '物體飛落', '過捲預防裝置未設置'],
  ['使用升降機上下料件作業', '被夾、被捲', '終點極限開關、緊急停止裝置或制動器失效']]) {
  const g = library[task].hazardGroups.find(x => x.groupName === group);
  const s = g.scenarios.find(x => x.text.includes(text));
  assert(s && s.controls.some(c => c.core && c.scoreLane === 'E'), `${task} mandatory device scenario`);
}
for (const legacy of Object.keys(fixLog.taskRenames)) assert(!(legacy in library), legacy);
// 20261104a 已改寫內容的「吊籠作業」及中間名稱只換名稱：舊存檔的情境勾選、手動評估與措施勾選原樣帶到新名稱。
const basketTask = '移動式起重機搭乘設備載人高處作業';
for (const legacy of ['吊籠作業', '起重機吊掛搭乘設備載人作業']) {
  const basketState = {scenarios: [0, 3], avoids: [], scenarioManual: {3: {isManual: true, manualS: 'S5', manualP: 'P3'}}};
  const basketSnap = {dataVersion: '20261104a', myProjectTasks: [legacy], userSelections: {[`${legacy}_0`]: basketState},
    taskControlChecks: {[legacy]: {someKey: true}}};
  context.migrateScenarioSelections(basketSnap, [library[basketTask], roller], migration);
  assert.deepEqual(Array.from(basketSnap.myProjectTasks), [basketTask], legacy);
  assert.equal(basketSnap.userSelections[`${basketTask}_0`], basketState);
  assert.equal(basketSnap.taskControlChecks[basketTask].someKey, true);
}
// 20261104b 測試期間的存檔：只換名稱並複製改句後的勾選鍵，已勾措施編號不前移。
const tower = library['塔式起重機升高及拆卸作業'];
const towerDrop = tower.hazardGroups.findIndex(g => g.groupName === '物體飛落');
const towerOld = '塔吊升高或拆卸前確認檢查合格證仍在有效期內。';
const towerNew = context.controlBodyKey(tower.hazardGroups[towerDrop].AvoidItems[9]);
assert.notEqual(towerOld, towerNew);
const ropeIdx = [5, 6, 9];
const bSnap = {dataVersion: '20261104b', myProjectTasks: ['起重機吊掛搭乘設備載人作業', '高處繩索接近作業'],
  userSelections: {'起重機吊掛搭乘設備載人作業_0': {scenarios: [1], avoids: []}, [`高處繩索接近作業_${ropeDrop}`]: {scenarios: [], avoids: ropeIdx.slice()}},
  taskControlChecks: {'塔式起重機升高及拆卸作業': {[towerOld]: true}}};
context.migrateScenarioSelections(bSnap, [library[basketTask], rope, tower, roller], migration);
assert.equal(bSnap.dataVersion, DATA_VER);
assert.deepEqual(Array.from(bSnap.myProjectTasks), [basketTask, '高處繩索接近作業']);
assert.deepEqual(Array.from(bSnap.userSelections[`${basketTask}_0`].scenarios), [1]);
assert.deepEqual(Array.from(bSnap.userSelections[`高處繩索接近作業_${ropeDrop}`].avoids), ropeIdx);
assert.equal(bSnap.taskControlChecks['塔式起重機升高及拆卸作業'][towerNew], true);
// 20261104c 存檔走同一條路；20261104d 新增的作業可載入情境，未勾措施時為 P5。
for (const ver of ['20261104c', '20261104d', '20261104e']) {
  const cSnap = {dataVersion: ver, myProjectTasks: ['起重機吊掛搭乘設備載人作業'], userSelections: {}, taskControlChecks: {}};
  context.migrateScenarioSelections(cSnap, [library[basketTask], roller], migration);
  assert.equal(cSnap.dataVersion, DATA_VER, ver);
  assert.deepEqual(Array.from(cSnap.myProjectTasks), [basketTask], ver);
}
for (const name of ['剪叉式升降台作業', '建築物外牆吊籠清洗及維護作業']) {
  const task = library[name];
  assert(task && task.hazardGroups.every(g => g.scenarios && g.scenarios.length), name);
  assert(task.hazardGroups.every(g => g.scenarios.every(s => context.probabilityFromLinkedControls(s.controls, {}) === 'P5')), name);
}
const dosimeter = library['游離輻射作業'].hazardGroups.find(g => g.groupName === '職業病').scenarios
  .flatMap(s => s.controls).find(c => c.text.includes('個人劑量計'));
assert.equal(dosimeter.scoreLane, 'M');
console.log(JSON.stringify({dataVersion: DATA_VER, groups, hazards, controls, exactTextJoin: true, legacySplitMigration: true,
  legacyExactIndexMigration: true, migrationIdempotent: true, corruptMapRejected: true, avoidIndexRemap20261021a: true,
  taskRenames20261104b: true, avoidIndexRemap20261104b: true, controlKeyCopy20261104b: true}, null, 2));
