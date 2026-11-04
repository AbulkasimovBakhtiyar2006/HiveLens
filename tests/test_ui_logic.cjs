// Run with: node --test tests/test_ui_logic.cjs. No browser, network or model calls.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../hivelens/static/app.js'), 'utf8').split('/* ── Events ')[0];
function ui() {
  const nodes = {};
  const storage = new Map();
  const node = id => nodes[id] ||= { value: '', checked: false, validity: { valid: true }, innerHTML: '', textContent: '', querySelector: () => ({ addEventListener() {} }) };
  const context = vm.createContext({ document: { getElementById: node, querySelectorAll: () => [] }, localStorage: { getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v) } });
  vm.runInContext(source, context);
  const run = code => vm.runInContext(code, context);
  run('state = {has_api_key: true, hives: [{id: "one", name: "One"}], apiary: {hives: [], drift_links: []}}; selectedHive = "one";');
  return { run, node };
}
test('stores drive the critical reason when varroa only warrants watch', () => {
  const {run} = ui();
  assert.equal(run('primaryReason({overall:"act", levels:{varroa:"watch",stores:"act",brood:"good"}, mites_per_day:6.67, stores_weeks:0, brood_total_pct:26.4})'), 'Stores: 0 weeks remaining');
  assert.equal(run('statusReasons({}, {})[0].level'), 'unknown');
});
test('inspection requires photos, valid fields, API key and no concurrent run', () => {
  const {run,node} = ui();
  assert.match(run('inspectionReadiness()'), /Add a board/);
  node('board-sample').value = 'sample.jpg';
  assert.equal(run('inspectionReadiness()'), '');
  for (const id of ['inspection-date','inspection-days','inspection-frames']) {
    node(id).validity.valid = false;
    assert.notEqual(run('inspectionReadiness()'), '');
    node(id).validity.valid = true;
  }
  run('state.has_api_key = false');
  assert.match(run('inspectionReadiness()'), /MODEL_API_KEY/);
  run('state.has_api_key = true; activeJob = {id:"running"}');
  assert.match(run('inspectionReadiness()'), /running/);
  run('activeJob = null; frameFiles = Array(9).fill({})');
  assert.match(run('inspectionReadiness()'), /8 frame/);
});
test('duration history matches options and stays unknown for different work', () => {
  const {run,node} = ui();
  assert.match(run('timingHint()'), /Duration unknown/);
  run('store.set("inspection-times", [{key:timingKey(),ms:90000}])');
  assert.match(run('timingHint()'), /about 2 min/);
  node('inspection-agent').checked = true;
  assert.match(run('timingHint()'), /Duration unknown/);
});
test('report puts actions before findings and keeps claims collapsed', () => {
  const {run,node} = ui();
  run(`renderRecord('one', {id:'r',date:'2026-11-04',synthetic:true,status:{overall:'act',levels:{stores:'act',varroa:'watch'},flags:['Mites watch','Stores low']},metrics:{stores_weeks:0,mites_per_day:6.67},report:{summary:'Summary text',actions:[{action:'Review stores',urgency:'now'}],findings:[{text:'Measured stores',claim_ids:['c1']}]},claims:[{id:'c1',verdict:'verified',statement:'No stores',metric:'stores_weeks',actual:0}]}, 'result')`);
  const html = node('result').innerHTML;
  assert.ok(html.indexOf('Summary text') < html.indexOf('What to do'));
  assert.ok(html.indexOf('What to do') < html.indexOf('<h4>Findings'));
  assert.ok(html.indexOf('<h4>Findings') < html.indexOf('class="metric-grid"'));
  assert.match(html, /<details class="claims-box">/);
  assert.match(html, /recommendations are simulated/);
  assert.match(html, /badge watch/);
});

test('first entry welcomes newcomers without hijacking direct report links', () => {
  const {run} = ui();
  assert.equal(run('entryView("", false)'), 'welcome');
  assert.equal(run('entryView("overview", false)'), 'welcome');
  assert.equal(run('entryView("history", false)'), 'history');
  assert.equal(run('entryView("benchmark", false)'), 'benchmark');
  assert.equal(run('entryView("", true)'), 'overview');
  assert.equal(run('entryView("overview", true)'), 'overview');
  assert.equal(run('entryView("welcome", true)'), 'welcome');
});
