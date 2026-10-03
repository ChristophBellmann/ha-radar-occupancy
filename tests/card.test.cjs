// Node test without Home Assistant: run with `node tests/card.test.cjs`.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../custom_components/radar_occupancy/frontend/radar-occupancy-card.js'), 'utf8');
const registry = new Map();
let definitions = 0;
const context = vm.createContext({
  setTimeout, clearTimeout, window: {},
  HTMLElement: class { attachShadow() { this.shadowRoot = {}; } },
  customElements: {
    get: name => registry.get(name),
    define: (name, type) => {
      assert.equal(registry.has(name), false);
      registry.set(name, type);
      definitions++;
    },
  },
});
vm.runInContext(`(function(){${source}})()`, context);
vm.runInContext(`(function(){${source}})()`, context);
assert.equal(definitions, 1, 'Mehrfaches Laden darf keine doppelte Registrierung erzeugen.');
const Card = registry.get('radar-occupancy-card');
assert.equal(context.window.customCards.length, 1);
const card = new Card();
card._hass = { language: 'de', states: { 'camera.test': { attributes: { entity_picture: '/api/camera_proxy/camera.test' } } } };
card.images.oben={url:'/api/camera_proxy/camera.test'};
card.images.unten={url:'/api/camera_proxy/camera.test'};
const data = {
  floors: { oben: { camera: 'camera.test', name: 'Oben', flip: true, width: 1000, height: 1000, calibration_points: [
    { vacuum: { x: 0, y: 0 }, map: { x: 100, y: 900 } },
    { vacuum: { x: 1000, y: 0 }, map: { x: 200, y: 900 } },
    { vacuum: { x: 0, y: 1000 }, map: { x: 100, y: 800 } },
  ] } },
  sensors: [], targets: [{ floor: 'oben', map: [500, 500], room: 'Bad', target: 1 }],
};
const markup = card.floor('oben', data);
assert.ok(markup.includes('href="/api/camera_proxy/camera.test"'), 'Bilder müssen ohne hassUrl-Hilfsfunktion funktionieren.');
assert.ok(markup.includes('cx="150" cy="850"'), 'Radarziel muss mit Kartenkalibrierung projiziert werden.');
assert.ok(markup.includes('Bad 1'));
assert.ok(markup.includes('data-map-space transform="rotate(180 500 500)"'));
// Der Bildpunkt (150,850) erscheint gedreht bei (850,150). Ein Tipp dort
// muss wieder als derselbe bekannte Standort (500,500) aufgenommen werden.
(async () => {
  let recorded;
  const measuringCard = new Card();
  measuringCard.mode = 'sample';
  measuringCard.render = () => {};
  measuringCard.service = async (name, sample) => { recorded = { name, ...sample }; return true; };
  const svg = {
    dataset: { floor: 'oben' },
    createSVGPoint: () => ({ matrixTransform(matrix) { return matrix.apply(this.x, this.y); } }),
    querySelector: () => ({ getScreenCTM: () => ({ inverse: () => ({ apply: (x,y) => ({ x:1000-x, y:1000-y }) }) }) }),
  };
  await measuringCard.mapClick({ clientX:850, clientY:150 }, svg, { floor:'oben' }, data);
  assert.equal(recorded,undefined,'Antippen darf noch keinen Dienst aufrufen.');
  assert.equal(measuringCard.pendingSample[0],500);
  await measuringCard.saveSample();
  assert.equal(recorded.name,'sample');
  assert.equal(recorded.x,500);
  assert.equal(recorded.y,500);
  assert.equal(measuringCard.mode,'view');
  assert.equal(measuringCard.pendingSample,null);
  console.log('Radar-Karte: Drehung und Antippen im ursprünglichen Koordinatensystem geprüft.');
})().catch(error => { console.error(error); process.exitCode = 1; });
console.log('Radar-Karte: doppelte Registrierung, Kamera-URL und Zielprojektion geprüft.');

let renders = 0;
card.render = () => { renders++; };
const startup = { states: { 'sensor.flat_overview': { entity_id:'sensor.flat_overview', state:'1', attributes:{floors:{'camera.roboter_map_1':{}},sensors:[],map_mode:true} } } };
card.hass = startup;
card.hass = startup;
assert.equal(renders,1);
card.hass = { states: { ...startup.states, 'camera.roboter_map_1': { attributes: { entity_picture:'/api/camera_proxy/camera.test' } } } };
card._hass.language = 'de';
assert.equal(renders,2,'Eine später geladene Kamera muss die Anzeige aktualisieren.');

const zoomCard = new Card();
zoomCard.shadowRoot.querySelector = () => null;
let zoomTransform = '';
const zoomSvg = {
  dataset: { floor:'oben' }, viewBox: { baseVal: { width:1000, height:1000 } },
  querySelector: () => ({ setAttribute: (name,value) => { zoomTransform=value; } }),
};
zoomCard.zoomAt(zoomSvg,2,{x:500,y:500});
assert.equal(zoomCard.viewports.oben.scale,2);
assert.equal(zoomCard.viewports.oben.x,-500);
assert.ok(zoomTransform.includes('scale(2)'));
zoomCard.zoomAt(zoomSvg,10,{x:500,y:500});
assert.equal(zoomCard.viewports.oben.scale,6);
zoomCard.zoomAt(zoomSvg,1,{x:500,y:500});
assert.equal(zoomCard.viewports.oben.x,0);
assert.equal(zoomCard.viewports.oben.y,0);
zoomSvg.createSVGPoint = () => ({ matrixTransform: function(matrix) { return matrix.apply(this.x,this.y); } });
zoomSvg.getScreenCTM = () => ({ inverse: () => ({ apply: (x,y) => ({x,y}) }) });
zoomSvg.setPointerCapture = () => {};
zoomSvg.addEventListener = () => {};
zoomCard.scrollContainer = () => ({ scrollTop:0 });
let taps = 0;
zoomCard.mapClick = () => { taps++; };
zoomCard.bindMap(zoomSvg,{floor:'oben'},data);
zoomSvg.onpointerdown({pointerType:'touch',pointerId:1,clientX:250,clientY:250});
zoomSvg.onpointerdown({pointerType:'touch',pointerId:2,clientX:750,clientY:750});
zoomSvg.onpointermove({pointerType:'touch',pointerId:2,clientX:1000,clientY:1000});
assert.ok(Math.abs(zoomCard.viewports.oben.scale-1.5)<1e-9);
zoomSvg.onpointerup({pointerId:2,type:'pointerup'});
zoomSvg.onpointerup({pointerId:1,type:'pointerup'});
assert.equal(taps,0,'Eine Zoomgeste darf keinen Messpunkt speichern.');
zoomSvg.onpointerdown({pointerType:'touch',pointerId:3,clientX:250,clientY:250});
zoomSvg.onpointerup({pointerId:3,type:'pointerup',clientX:250,clientY:250});
assert.equal(taps,1);
console.log('Zoomgrenzen, Zwei-Finger-Geste und Unterdrückung versehentlicher Messpunkte geprüft.');

const baseline = { id:'sat1', room:'Bad', floor:'oben', samples:2, sample_points:[
  {radar:[238,728],map:[500,500]}, {radar:[191,749],map:[600,500]},
], targets:[{radar:[1238,728]}] };
assert.ok(card.calibrationHint(baseline).includes('nur 5 cm'));
assert.ok(card.calibrationHint(baseline).includes('100 cm'));
card.selected='sat1';
const anchorMarkup=card.floor('oben',{...data,sensors:[baseline]});
assert.ok(anchorMarkup.includes('data-sample-marker="1" transform="translate(850 150)"'));
assert.ok(anchorMarkup.includes('data-sample-marker="2"'));
console.log('Warnung bei nahen Radarpositionen und aufrechte gespeicherte Messpunkte geprüft.');

// Raumlabel-Tipps wählen den Sensor auch unter Pointer-Capture und messen nie.
zoomCard.render=()=>{};
zoomCard._hass={states:{'sensor.flat_overview':{entity_id:'sensor.flat_overview',attributes:{floors:{},map_mode:true,sensors:[{id:'sat1',room:'Bad'}]}}}};
zoomCard.mode='sample';zoomCard.pendingSample=[1,2];
zoomSvg.onpointerdown({pointerType:'touch',pointerId:4,clientX:250,clientY:250,target:{closest:()=>({dataset:{roomSensor:'sat1'}})}});
zoomSvg.onpointerup({pointerId:4,type:'pointerup',clientX:250,clientY:250});
assert.equal(taps,1,'Ein Tipp auf einen Raumnamen darf keinen Karten-Messpunkt auslösen.');
assert.equal(zoomCard.selected,'sat1');
assert.equal(zoomCard.mode,'view');
assert.equal(zoomCard.pendingSample,null);
const labelData={...data,floors:{oben:{...data.floors.oben,rooms:[{name:'Bathroom',x:500,y:500}]}},sensors:[{...baseline,map_room:'Bathroom'}]};
const labelMarkup=card.floor('oben',labelData);
assert.ok(labelMarkup.includes('data-room-sensor="sat1" role="button"'));
card.mode='sample';card.pendingSample=[500,500];
const pendingMarkup=card.floor('oben',labelData);
assert.ok(pendingMarkup.includes('data-pending-sample'));
assert.ok(pendingMarkup.includes('data-save-sample'));
assert.ok(pendingMarkup.includes('data-undo-sample'));
console.log('Raumauswahl ohne Messung, Standortvorschau und explizite Aufnahme geprüft.');

const ready={id:'sat1',room:'Bad',calibrated:true,samples:4,error_mm:87,zone:'inside',boundary_source:'map',polygon:[[0,0],[1000,0],[0,1000]],approach_polygons:[]};
const completedMarkup=card.setupSummary(ready);
assert.ok(completedMarkup.includes('Bad: Einmessen abgeschlossen'));
assert.ok(completedMarkup.includes('4 Messpunkte gespeichert'));
assert.ok(completedMarkup.includes('8,7 cm'));
assert.ok(completedMarkup.includes('automatisch aus der Karte'));
assert.ok(completedMarkup.includes('Türvorbereich'));
assert.ok(card.setupSummary({...ready,polygon:[]}).includes('noch nicht verfügbar'));
assert.ok(!card.setupSummary({...ready,calibrated:false}).includes('Einmessen abgeschlossen'));
console.log('Abgeschlossene Kalibrierung, automatische Raumgrenze und fehlender Türvorbereich geprüft.');

(async()=>{
  const selectCard=new Card();let updates=0;
  const select={id:'sensor',value:'sat2',blur(){selectCard.shadowRoot.activeElement=null;this.onblur();}};
  selectCard.render=()=>{updates++;selectCard.deferred=false;};
  selectCard.bindSensorSelect(select);
  selectCard.shadowRoot.activeElement=select;
  for(let i=0;i<20;i++)selectCard.hass={states:{'sensor.flat_overview':{entity_id:'sensor.flat_overview',state:'1',attributes:{floors:{},sensors:[],map_mode:true,revision:i}}}};
  assert.equal(updates,0,'Radar-Updates dürfen die fokussierte Auswahl nicht ersetzen.');
  assert.equal(selectCard.deferred,true);
  let chosen;
  selectCard.selectSensor=value=>{chosen=value;selectCard.refreshView();};
  select.onchange({target:select});
  await Promise.resolve();
  assert.equal(chosen,'sat2');
  assert.equal(updates,1,'Nach der Wahl einmal mit dem aktuellen Zustand aktualisieren.');
  assert.equal(selectCard.deferred,false);
  selectCard.shadowRoot.activeElement=select;
  selectCard.refreshView();
  select.blur();await Promise.resolve();
  assert.equal(updates,2,'Auch beim Abbruch per Fokuswechsel wieder aktualisieren.');
  // Direkte Render-Aufrufe (z.B. nach einem Dienst) müssen ebenfalls warten.
  const directCard=new Card();directCard.shadowRoot.activeElement={id:'sensor'};
  directCard.render();assert.equal(directCard.deferred,true);
  assert.equal(directCard.shadowRoot.innerHTML,undefined);
  console.log('Offene Raumauswahl bleibt bei Radar-Updates bestehen; Auswahl und Abbruch geben Updates wieder frei.');
})().catch(error=>{console.error(error);process.exitCode=1;});

(async()=>{
  const holdCard=new Card(),calls=[];
  const sensor={id:'sat1',hold_enabled:true,entities:{hold:'switch.bad_hold_occupancy'}};
  holdCard._hass={states:{'sensor.flat_overview':{entity_id:'sensor.flat_overview',attributes:{floors:{},map_mode:true,sensors:[sensor]}}},callService:async(...args)=>calls.push(args)};
  await holdCard.toggleHold('sat1');
  assert.equal(calls[0][0],'switch');
  assert.equal(calls[0][1],'turn_off');
  assert.equal(calls[0][2].entity_id,'switch.bad_hold_occupancy');
  sensor.hold_enabled=false;
  await holdCard.toggleHold('sat1');
  assert.equal(calls[1][1],'turn_on');
  holdCard.selected='sat1';holdCard.mode='sensor';holdCard.pendingSample=[1000,2000];holdCard.render=()=>{};
  let stored;
  holdCard.service=async(name,data)=>{stored={name,...data};return true;};
  await holdCard.saveSensorLocation();
  assert.equal(stored.name,'set_location');
  assert.equal(stored.room,'sat1');
  assert.equal(stored.x,1000);
  assert.equal(stored.y,2000);
  assert.equal(holdCard.mode,'orient','Nach dem Platzieren folgt das Ausrichten.');
  console.log('Halten ein/aus und unabhängige Sensorplatzierung geprüft.');
})().catch(error=>{console.error(error);process.exitCode=1;});

(async()=>{
  const modeCard=new Card(),calls=[];
  const overview={entity_id:'sensor.flat_overview',attributes:{floors:{},sensors:[],map_mode:true,entities:{map_mode:'switch.flat_map_mode'}}};
  modeCard._hass={states:{'sensor.flat_overview':overview},callService:async(...args)=>calls.push(args)};
  await modeCard.toggleControlMode();
  overview.attributes.map_mode=false;
  await modeCard.toggleControlMode();
  assert.equal(calls[0][1],'turn_off');assert.equal(calls[1][1],'turn_on');
  assert.equal(calls[0][2].entity_id,'switch.flat_map_mode');
  console.log('Umschalter zwischen Karte und Entfernungsregel geprüft.');
})();

(async()=>{
  const c=new Card();let releases=0,selections=0;
  c.releaseHold=async()=>releases++;c.selectSensor=()=>selections++;
  c.render=()=>{};
  const b={dataset:{selectSensor:'sat1'}};
  c.bindRoomButton(b);
  const down={button:0,clientX:0,clientY:0,pointerId:1};
  b.onpointerdown(down);b.onpointerup();b.onclick({preventDefault(){}});
  assert.equal(selections,1);assert.equal(releases,0);
  b.onpointerdown(down);c.deferred=true;c.refreshView();
  await new Promise(resolve=>setTimeout(resolve,700));
  b.onpointerup();b.onclick({preventDefault(){}});
  assert.equal(releases,1);assert.equal(selections,1);
  b.onpointerdown(down);b.onpointermove({clientX:50,clientY:0});
  await new Promise(resolve=>setTimeout(resolve,700));b.onpointerup();b.onclick({preventDefault(){}});
  assert.equal(releases,1);assert.equal(selections,1);
  console.log('Langdruck löst einmalig; kurzer Tipp und Scrollen lösen keine Belegung.');
})();

(async()=>{
  const c=new Card();let releases=0,toggles=0;
  c.releaseHold=async()=>releases++;c.render=()=>{};
  const b={dataset:{toggleHold:'sat1'}};
  c.bindRoomButton(b,()=>toggles++);
  const down={button:0,clientX:0,clientY:0,pointerId:1};
  b.onpointerdown(down);b.onpointerup();b.onclick({preventDefault(){}});
  assert.equal(toggles,1);assert.equal(releases,0);
  b.onpointerdown(down);
  await new Promise(resolve=>setTimeout(resolve,700));
  assert.equal(c.interaction,true,'Langdruck muss die Kachel bis zum Loslassen stabil halten.');
  b.onpointerup();b.onclick({preventDefault(){}});
  assert.equal(releases,1);assert.equal(toggles,1);
  console.log('Halten-Knopf: Tipp schaltet Halten um, Langdruck löst Belegung ohne Umschalten.');
})();

const staleRegistry=new Map([['radar-position-card',class OldCard {}]]);
const staleContext=vm.createContext({HTMLElement:class {attachShadow(){this.shadowRoot={};}},customElements:{get:n=>staleRegistry.get(n),define:(n,c)=>staleRegistry.set(n,c)},setTimeout,clearTimeout});
vm.runInContext(`(function(){${source}})()`,staleContext);
assert.equal(typeof staleRegistry.get('radar-occupancy-card').prototype.releaseHold,'function');
console.log('Karte registriert sich neben einer alten Positionskarte.');

// Blickfeld: Fächer bei Wandmontage, Ellipse bei Deckenmontage, Drehung speichert verzögert.
{
  const c=new Card();
  c._hass={language:'de',states:{}};
  c.images.oben={url:'/x.png'};c.selected='s';
  const base={floors:{oben:data.floors.oben},targets:[]};
  const wall={id:'s',room:'Bad',floor:'oben',sensor_location:[0,0],heading:90,mirrored:false,mount:'wall',transform_source:'orientation'};
  let markup=c.floor('oben',{...base,sensors:[wall]});
  assert.ok(markup.includes('data-fov'),'Platzierter Sensor zeigt sein Sichtfeld.');
  assert.ok(!markup.includes('data-ceiling'));
  assert.ok(markup.includes('6 m'));
  // Heading 90° zeigt im Vakuumsystem nach +Y; Kartenpunkt für (0,6000) ist (100,300).
  assert.ok(markup.includes('x2="100" y2="300"'),'Mittelachse folgt der Blickrichtung.');
  c.mode='orient';
  markup=c.floor('oben',{...base,sensors:[wall]});
  assert.ok(markup.includes('data-rotate="15"')&&markup.includes('data-rotate="-1"')&&markup.includes('data-mirror'));
  const ceiling={...wall,id:'s',mount:'ceiling',mount_height:2500,heading:0};
  markup=c.floor('oben',{...base,sensors:[ceiling]});
  assert.ok(markup.includes('data-ceiling'),'Deckensensor zeigt Erfassungsfläche statt Fächer.');
  assert.ok(markup.includes('2,5 m hoch'));
  (async()=>{
    const r=new Card();r.selected='s';r.render=()=>{};
    const calls=[];
    r._hass={states:{'sensor.flat_overview':{entity_id:'sensor.flat_overview',attributes:{floors:base.floors,map_mode:true,sensors:[wall]}}},callService:async(d,a,payload)=>calls.push(payload)};
    r.rotateSensor(15);r.rotateSensor(-1);r.rotateSensor(0,true);
    assert.equal(r.orient.heading,104);assert.equal(r.orient.mirrored,true);
    assert.equal(calls.length,0,'Schnelles Tippen sammelt erst.');
    await new Promise(res=>setTimeout(res,650));
    assert.equal(JSON.stringify(calls),JSON.stringify([{room:'s',heading:104,mirrored:true}]));
    const unplaced=new Card();
    assert.equal(unplaced.orientation({id:'x'},{}),null,'Ohne Standort kein Sichtfeld.');
    console.log('Blickfeld: Fächer, Deckenellipse und Drehen geprüft.');
  })();
}

// Personenzahl, „manuell aus“ und Türen.
{
  const c=new Card();
  c._hass={language:'de',states:{}};
  assert.equal(c.roomStatus({available:true,calibrated:true,map_ready:true,people:2,zone:'lost'}),'2 Personen');
  assert.equal(c.roomStatus({available:true,calibrated:true,map_ready:true,people:0,zone:'lost'}),'Frei');
  assert.equal(c.roomStatus({available:true,calibrated:true,map_ready:true,people:1,zone:'inside',light_mode:'manual_off'}),'1 Person · Licht manuell aus');
  c.images.oben={url:'/x.png'};
  const markup=c.floor('oben',{floors:{oben:data.floors.oben},targets:[],sensors:[],doors:[{a:'Bad',b:'Gang',floor:'oben',point:[0,0],covered:{Bad:true,Gang:false}}]});
  assert.ok(markup.includes('data-door="Bad-Gang"'));
  console.log('Personenzahl, manuell aus und Türen in der Ansicht geprüft.');
}

// Ausgang markieren speichert sofort; umgedrehte Stockwerke zeigen den Drehknopf.
(async()=>{
  const c=new Card();let stored;
  c.mode='exit';c.selected='s';c.render=()=>{};
  c.service=async(name,payload)=>{stored={name,...payload};return true;};
  const svg={dataset:{floor:'oben'},createSVGPoint:()=>({matrixTransform(m){return m.apply(this.x,this.y);}}),
    querySelector:()=>({getScreenCTM:()=>({inverse:()=>({apply:(x,y)=>({x:1000-x,y:1000-y})})})})};
  await c.mapClick({clientX:850,clientY:150},svg,{floor:'oben'},data);
  assert.equal(stored.name,'set_exit');assert.equal(stored.room,'s');assert.equal(stored.x,500);
  c.images.oben={url:'/x.png'};
  assert.ok(c.floor('oben',{...data,sensors:[]}).includes('data-flip-floor="oben" data-flipped="true"'));
  console.log('Ausgang markieren und Drehknopf geprüft.');
})().catch(error=>{console.error(error);process.exitCode=1;});

// English for every other language; reasons as codes with rooms.
{
  const c=new Card();
  c._hass={language:'fr',states:{}};
  assert.equal(c.roomStatus({available:true,calibrated:true,map_ready:true,people:2,zone:'lost'}),'2 people');
  assert.equal(c.reasonText('moved',['Bedroom','Hall']),'Bedroom → Hall');
  assert.equal(c.reasonText('came_in',['outside','Hall']),'came in from outside');
  c._hass={language:'de',states:{}};
  assert.equal(c.reasonText('appeared_at_door',['outside','Gang']),'an der Tür zu draußen aufgetaucht');
  const summary=c.setupSummary({id:'a',room:'Bad',calibrated:true,samples:3,polygon:[[0,0],[1,0],[0,1]],boundary_source:'manual',approach_polygons:[],doors:[{to:'b',point:[0,0]}],map_ready:true,occupied:true,occupancy_reason:'moved',occupancy_reason_rooms:['Gang','Bad']});
  assert.ok(summary.includes('Eine Tür markiert.'));
  assert.ok(summary.includes('Gang → Bad'));
  console.log('Sprachen und Begründungen geprüft.');
}

// Tür markieren: Raum dahinter wählen, Tippen speichert sofort.
(async()=>{
  const c=new Card();let stored;
  c._hass={language:'en',states:{}};
  c.mode='door';c.selected='s';c.render=()=>{};
  c.service=async(name,payload)=>{stored={name,...payload};return true;};
  c.images.oben={url:'/x.png'};
  const sensors=[{id:'s',room:'Bed',floor:'oben'},{id:'h',room:'Hall',floor:'oben'}];
  const markup=c.floor('oben',{...data,sensors});
  assert.ok(markup.includes('data-door-to'));
  assert.ok(markup.includes('<option value="h" selected>Hall</option>'));
  assert.ok(markup.includes('<option value="outside" >outside</option>'));
  const svg={dataset:{floor:'oben'},createSVGPoint:()=>({matrixTransform(m){return m.apply(this.x,this.y);}}),
    querySelector:()=>({getScreenCTM:()=>({inverse:()=>({apply:(x,y)=>({x:1000-x,y:1000-y})})})})};
  await c.mapClick({clientX:850,clientY:150},svg,{floor:'oben'},data);
  assert.deepEqual({...stored},{name:'set_door',room:'s',to:'h',x:500,y:500});
  console.log('Tür markieren geprüft.');
})().catch(error=>{console.error(error);process.exitCode=1;});
