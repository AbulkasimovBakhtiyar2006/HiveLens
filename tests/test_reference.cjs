const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
function ui() {
  const context = vm.createContext({view:'overview', Date, num: v=>String(v), esc:v=>String(v)});
  vm.runInContext(fs.readFileSync(path.join(__dirname,'../hivelens/static/reference.js'),'utf8'),context);
  return code=>vm.runInContext(code,context);
}
test('weight plot breaks at missing days instead of inventing an observation',()=>{
  const run=ui();
  const html=run(`fieldChart([{date:'2019-01-01',value:10,n:2},{date:'2019-01-02',value:12,n:2},{date:'2019-01-05',value:15,n:1}], ['2019-01-01','2019-01-05'],'Weight')`);
  const d=html.match(/class="series" d="([^"]+)"/)[1];
  assert.equal((d.match(/M/g)||[]).length,2);
  assert.equal((d.match(/L/g)||[]).length,1);
  assert.match(html,/2019-01-05 · 15 kg · 1 readings/);
});
test('non-detected wash sample stays separate from numeric zero',()=>{
  const run=ui();
  const html=run(`fieldChart([{date:'2019-01-01',value:0,source_id:'numeric'},{date:'2019-01-02',value:null,source_id:'lod'}],['2019-01-01','2019-01-02'],'Wash',true)`);
  const zero=html.match(/class="sample-dot"[^>]+cy="([^"]+)"/)[1];
  const lod=html.match(/class="lod-dot"[^>]+cy="([^"]+)"/)[1];
  assert.notEqual(zero,lod);
  assert.match(html,/Below detection limit; not zero/);
  assert.doesNotMatch(html,/class="series"/);
});
test('workspace URL and browser draft keys remain isolated',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../hivelens/static/app.js'),'utf8').split('const $ =')[0];
  const c=vm.createContext({location:{search:'?mode=production'}, URLSearchParams});
  vm.runInContext(source,c);
  assert.equal(vm.runInContext(`apiUrl('/api/state')`,c),'/api/workspaces/production/state');
  assert.equal(vm.runInContext(`workspaceStorageKey('draft')`,c),'hivelens:production:draft');
  assert.equal(vm.runInContext(`workspaceStorageKey('palette')`,c),'hivelens:palette');
});
