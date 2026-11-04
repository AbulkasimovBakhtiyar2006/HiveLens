// Camera lifecycle and capture acceptance, without hardware or paid model calls.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const script = fs.readFileSync(path.join(__dirname, '../hivelens/static/camera.js'), 'utf8');

function setup(getUserMedia = async () => { throw Object.assign(new Error(), {name:'NotAllowedError'}); }) {
  const nodes = new Map(), accepted = [], revoked = [];
  const make = () => ({hidden:false, value:'board', disabled:false, textContent:'', handlers:{},
    classList:{toggle(){}}, addEventListener(k, fn) { (this.handlers[k] ||= []).push(fn); },
    async emit(k, event = {}) { for (const fn of this.handlers[k] || []) await fn(event); },
    setAttribute(k,v){this[k]=v;}, removeAttribute(k){delete this[k];}, replaceChildren(){}, focus(){},
    pause(){this.paused=true;}, play(){this.paused=false; return Promise.resolve();}, load(){},
    readyState:4, videoWidth:1920, videoHeight:1080, currentTime:3.5, seeking:false,
  });
  const node = id => { if (!nodes.has(id)) nodes.set(id,make()); return nodes.get(id); };
  const win = {...make(),isSecureContext:true}, doc = {...make(), getElementById:node,
    createElement:() => ({getContext:()=>({drawImage(){}}),toBlob:fn=>fn(new Blob(['jpeg'],{type:'image/jpeg'}))})};
  const captureSources = new WeakMap();
  let accept = true, url = 0;
  vm.runInNewContext(script, {
    document:doc, window:win, location:{hash:'#overview'}, navigator:{mediaDevices:{getUserMedia, enumerateDevices:async()=>[]}},
    URL:{createObjectURL:()=>`blob:${++url}`,revokeObjectURL:value=>revoked.push(value)},
    Blob, File, Date, Option:function(){}, captureSources,
    setFiles:(kind, files)=>{if (accept) accepted.push({kind,file:files[0]}); return accept;}, toast(){},
  });
  return {node,win,doc,accepted,captureSources,revoked,rejectFiles:()=>accept=false,
    click:id=>node(id).emit('click')};
}
function cameraStream() {
  const track = {stops:0,stop(){this.stops++;},label:'Test camera',addEventListener(){},getSettings:()=>({})};
  return {track,getTracks:()=>[track],getVideoTracks:()=>[track]};
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test('a permission response arriving after cancellation releases its camera', async () => {
  let resolve;
  const ui = setup(() => new Promise(r=>resolve=r));
  const permission = ui.click('camera-start');
  await ui.click('source-upload');
  const stream = cameraStream();
  resolve(stream);
  await permission;
  await flush();
  assert.equal(stream.track.stops,1);
  assert.equal(ui.node('camera-video').srcObject,null);
});

test('camera stops on route change and when the tab is hidden', async () => {
  for (const event of ['hashchange','visibilitychange']) {
    const stream = cameraStream(), ui = setup(async()=>stream);
    await ui.click('camera-start');
    await flush();
    assert.equal(ui.node('camera-video').srcObject,stream);
    ui.doc.hidden=true;
    await (event === 'hashchange' ? ui.win : ui.doc).emit(event);
    assert.equal(stream.track.stops,1);
    assert.equal(ui.node('camera-video').srcObject,null);
  }
});

test('hiding the tab also cancels an unresolved camera permission request', async () => {
  let resolve;
  const ui=setup(() => new Promise(r=>resolve=r));
  const permission=ui.click('camera-start');
  ui.doc.hidden=true;
  await ui.doc.emit('visibilitychange');
  const stream=cameraStream(); resolve(stream); await permission;
  assert.equal(stream.track.stops,1);
  assert.equal(ui.node('camera-video').srcObject,null);
});

test('permission denial gives a recovery action without creating a photo', async () => {
  const ui=setup();
  await ui.click('camera-start'); await flush();
  assert.match(ui.node('camera-status').textContent,/not granted.*Upload photos/);
  assert.equal(ui.node('camera-start').disabled,false);
  assert.equal(ui.accepted.length,0);
});

test('demo capture is only added after review, retaining its source and frame position', async () => {
  const ui=setup();
  await ui.click('camera-demo'); await ui.click('camera-capture');
  assert.equal(ui.accepted.length,0);
  assert.equal(ui.node('camera-review').hidden,false);
  await ui.click('camera-add');
  assert.equal(ui.accepted.length,1);
  const {kind,file}=ui.accepted[0], meta=ui.captureSources.get(file);
  assert.equal(kind,'frames'); assert.equal(file.type,'image/jpeg');
  assert.equal(meta.source,'demo'); assert.equal(meta.video_seconds,3.5);
  assert.equal(meta.width,1920); assert.equal(ui.node('camera-panel').hidden,true);
  assert.ok(ui.revoked.length);
});

test('a rejected upload keeps the captured photo available for review', async () => {
  const ui=setup();
  await ui.click('camera-demo'); await ui.click('camera-capture'); ui.rejectFiles();
  await ui.click('camera-add');
  assert.equal(ui.accepted.length,0);
  assert.equal(ui.node('camera-review').hidden,false);
  assert.equal(ui.revoked.length,0);
});

test('an undecoded or seeking video cannot be captured', async () => {
  const ui=setup(); await ui.click('camera-demo');
  for (const state of [{readyState:1,seeking:false},{readyState:4,seeking:true}]) {
    Object.assign(ui.node('camera-video'),state);
    await ui.click('camera-capture'); await ui.click('camera-add');
    assert.equal(ui.accepted.length,0);
  }
});
