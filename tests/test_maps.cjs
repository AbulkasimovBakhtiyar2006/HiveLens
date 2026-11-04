// Provider contracts: offline, no accounts and no paid requests.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const file = fs.readFileSync('hivelens/static/farm.js', 'utf8');
const source = file.slice(file.indexOf('let locationPick'));
function ui(maps = {}) {
  const scripts = [];
  const window = { matchMedia: () => ({ matches: true }) };
  const context = vm.createContext({
    state: { maps }, view: 'welcome', window, URLSearchParams, setTimeout, clearTimeout,
    IntersectionObserver: class { observe() {} unobserve() {} disconnect() {} },
    document: {
      addEventListener() {}, querySelectorAll: () => [],
      createElement: () => ({}), head: { appendChild: s => scripts.push(s) },
    },
  });
  return { run: code => vm.runInContext(code, context), scripts, window, context };
}
test('coordinates require both finite numeric values and reject out-of-range locations', () => {
  // Definitions do not execute any network calls.
  const values = ['{lat:0,lon:0}', '{lat:43.3,lon:77.2}', '{lat:null,lon:10}', '{lat:10}', '{lat:NaN,lon:1}', '{lat:91,lon:0}', '{lat:0,lon:181}'];
  const env = ui(); vm.runInContext(source, env.context);
  assert.deepEqual(values.map(v => env.run(`Boolean(hasLocation(${v}))`)), [true,true,false,false,false,false,false]);
});
test('no Google key means no SDK request', async () => {
  const env = ui(); vm.runInContext(source, env.context);
  assert.equal(await env.run('loadGoogleMaps()'), null);
  assert.equal(env.scripts.length, 0);
});
test('failed Google SDK falls back once without repeated script loads', async () => {
  const env = ui({browser_key:'public-test-key'}); vm.runInContext(source, env.context);
  const pending = env.run('loadGoogleMaps()');
  assert.equal(env.scripts.length, 1);
  assert.equal(new URL(env.scripts[0].src).hostname, 'maps.googleapis.com');
  env.scripts[0].onerror();
  assert.equal(await pending, null);
  assert.equal(await env.run('loadGoogleMaps()'), null);
  assert.equal(env.scripts.length, 1);
});
test('Google adapter uses coordinates, supports satellite and removes old markers', () => {
  const env = ui(); vm.runInContext(source, env.context);
  const calls = []; const pins = [];
  env.context.g = {
    Map: class { setCenter(v) { calls.push(['center', v]); } setZoom(v) { calls.push(['zoom', v]); } setMapTypeId(v) { calls.push(['type', v]); } },
    marker: { AdvancedMarkerElement: class { constructor(opts) { Object.assign(this, opts); pins.push(this); } addListener() {} } },
    event: { trigger() {}, clearInstanceListeners() {} },
  };
  env.run('const adapter = createGoogleMap({}, false, g); adapter.update([{id:"farm",name:"Farm",lat:43,lon:77}]); adapter.fit(); adapter.setType(true)');
  assert.equal(pins[0].position.lat, 43); assert.equal(pins[0].position.lng, 77);
  assert.equal(calls.find(([k]) => k === 'zoom')[1], 12);
  assert.deepEqual(calls.find(([k]) => k === 'type'), ['type','hybrid']);
  env.run('adapter.update([])'); assert.equal(pins[0].map, null);
});
test('late Google authentication failure disposes existing maps before fallback', async () => {
  const env = ui({browser_key:'public-test-key'}); vm.runInContext(source, env.context);
  const pending = env.run('loadGoogleMaps()');
  env.context.google = { maps: { importLibrary: async () => {} } };
  await env.window.hiveLensMapsReady(); await pending;
  env.run('let disposed = false; farmMaps.world = { provider:"google", dispose(){ disposed = true; }, el:{remove(){}}, observer:{disconnect(){}} };');
  env.window.gm_authFailure();
  assert.equal(env.run('disposed'), true);
  assert.equal(env.run('farmMaps.world'), undefined);
  assert.equal(await env.run('loadGoogleMaps()'), null);
});
