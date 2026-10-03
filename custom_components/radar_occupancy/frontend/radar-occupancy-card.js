/* Radar Occupancy: Roboterkarten je Stockwerk, anonyme Radarziele, Personen je Raum und geführtes Einmessen.
   Wird von der Integration ausgeliefert und in jedes Dashboard geladen (type: custom:radar-occupancy-card). */
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {inside:'Im Raum',approach:'Vor dem Raum',outside:'Außerhalb',lost:'Ziel verloren',unreliable:'Umrechnung prüfen',uncalibrated:'Noch nicht eingemessen',unavailable:'Sensor offline'};
function affine(points, from, to) {
  if (!points || points.length < 3) return null;
  const p = points.slice(0,3), a=p[0][from],b=p[1][from],c=p[2][from];
  const det=(b.x-a.x)*(c.y-a.y)-(c.x-a.x)*(b.y-a.y);
  if (Math.abs(det)<1e-8) return null;
  return (x,y) => {
    const u=((x-a.x)*(c.y-a.y)-(c.x-a.x)*(y-a.y))/det;
    const v=((b.x-a.x)*(y-a.y)-(x-a.x)*(b.y-a.y))/det;
    return [p[0][to].x+u*(p[1][to].x-p[0][to].x)+v*(p[2][to].x-p[0][to].x),p[0][to].y+u*(p[1][to].y-p[0][to].y)+v*(p[2][to].y-p[0][to].y)];
  };
}
// Radar-Y ist die Blickrichtung, Radar-X zeigt ungespiegelt nach rechts (wie geometry.rigid).
function rigid(location,heading,mirrored) {
  const r=heading*Math.PI/180,m=mirrored?-1:1;
  return [[1000*m*Math.sin(r),1000*Math.cos(r),location[0]],[-1000*m*Math.cos(r),1000*Math.sin(r),location[1]]];
}
const projectRadar=(t,x,y)=>[t[0][0]*x/1000+t[0][1]*y/1000+t[0][2],t[1][0]*x/1000+t[1][1]*y/1000+t[1][2]];
const FOV_DEG=60,FOV_RANGE=6000,FOV_PITCH=35;
class RadarOccupancyCard extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:'open'}); this.selected=null;this.entityId=null; this.mode='view';this.pendingSample=null;this.draft=[];this.message='';this.busy=false; this.viewports={};this.images={};this.panels={calibration:false,transitions:false,help:false,maintenance:false};this.interaction=false;this.deferred=false;this.orient=null;this.orientTimer=null; }
  setConfig(config) { this.config=config||{}; }
  static getStubConfig() { return {}; }
  getCardSize() { return 12; }
  // Lagebild-Sensor der Integration: aus der Kartenkonfiguration oder automatisch gefunden.
  stateObj() {
    const states=this._hass?.states||{};
    if(this.config?.entity)return states[this.config.entity];
    if(this.entityId&&states[this.entityId])return states[this.entityId];
    const found=Object.values(states).find(s=>s?.entity_id?.startsWith('sensor.')&&s.attributes?.floors&&s.attributes?.sensors&&'map_mode' in s.attributes);
    this.entityId=found?.entity_id||null;
    return found;
  }
  data() { return this.stateObj()?.attributes; }
  view(floor) { return this.viewports[floor]||(this.viewports[floor]={scale:1,x:0,y:0}); }
  set hass(hass) {
    this._hass=hass;
    const state=this.stateObj();
    this.prepareImages(state?.attributes);
    const cameras=Object.keys(state?.attributes?.floors||{});
    const signature=JSON.stringify([state?.state,state?.attributes,cameras.map(id=>hass.states[id]?.attributes.entity_picture)]);
    if (signature===this.signature) return;
    this.signature=signature;
    this.refreshView();
  }
  refreshView() {
    if(this.interaction||this.sensorSelectFocused()) this.deferred=true;
    else this.render();
  }
  sensorSelectFocused() {
    return this.shadowRoot.activeElement?.id==='sensor'||Boolean(this.shadowRoot.activeElement?.dataset?.setting);
  }
  bindSensorSelect(select) {
    select.onchange=event=>{
      const sensor=event.target.value;
      event.target.blur();
      this.selectSensor(sensor);
    };
    select.onblur=()=>Promise.resolve().then(()=>{
      if(this.deferred)this.refreshView();
    });
  }
  prepareImages(data) {
    for(const [floor,info] of Object.entries(data?.floors||{})) {
      if(!info.image_path || typeof this._hass.callWS!=='function') continue;
      const cached=this.images[floor];
      if(cached?.path===info.image_path && (cached.loading||cached.expires>Date.now())) continue;
      this.images[floor]={path:info.image_path,loading:true,url:cached?.path===info.image_path?cached.url:undefined};
      this._hass.callWS({type:'auth/sign_path',path:info.image_path,expires:3600}).then(result=>{
        if(this.images[floor]?.path!==info.image_path)return;
        this.images[floor]={path:info.image_path,url:result.path,expires:Date.now()+1800000};
        this.refreshView();
      }).catch(error=>{
        this.images[floor]={path:info.image_path,expires:Date.now()+15000};
        this.message='Kartenbild konnte nicht geladen werden: '+(error.message||String(error));
        this.refreshView();
      });
    }
  }
  canvasPoint(svg,x,y) {
    const point=svg.createSVGPoint();point.x=x;point.y=y;
    return point.matrixTransform(svg.getScreenCTM().inverse());
  }
  applyViewport(svg) {
    const floor=svg.dataset.floor,view=this.view(floor);
    const box=svg.viewBox.baseVal;
    view.x=Math.max(box.width*(1-view.scale),Math.min(0,view.x));
    view.y=Math.max(box.height*(1-view.scale),Math.min(0,view.y));
    svg.querySelector('[data-zoom-space]').setAttribute('transform',`translate(${view.x} ${view.y}) scale(${view.scale})`);
    const label=this.shadowRoot.querySelector(`[data-zoom-label="${floor}"]`);
    if(label)label.textContent=Math.round(view.scale*100)+' %';
  }
  zoomAt(svg,scale,point) {
    const view=this.view(svg.dataset.floor),next=Math.max(1,Math.min(6,scale));
    const world={x:(point.x-view.x)/view.scale,y:(point.y-view.y)/view.scale};
    view.x=point.x-world.x*next;view.y=point.y-world.y*next;view.scale=next;
    this.applyViewport(svg);
  }
  scrollContainer(svg) {
    let node=svg;
    while(node) {
      if(node.nodeType===1 && node.scrollHeight>node.clientHeight+1 && /auto|scroll/.test(getComputedStyle(node).overflowY))return node;
      node=node.parentElement||node.getRootNode?.().host;
    }
    return document.scrollingElement;
  }
  bindMap(svg,current,data) {
    const pointers=new Map(),floor=svg.dataset.floor;
    let gesture=null,moved=false,multi=false,scroll=null,roomSensor=null;
    const snapshot=()=>{
      const list=[...pointers.values()];
      const view={...this.view(floor)};
      if(list.length===2) {
        const a=this.canvasPoint(svg,list[0].x,list[0].y),b=this.canvasPoint(svg,list[1].x,list[1].y);
        gesture={view,mid:{x:(a.x+b.x)/2,y:(a.y+b.y)/2},distance:Math.hypot(a.x-b.x,a.y-b.y)};
      } else if(list.length===1) gesture={view,point:this.canvasPoint(svg,list[0].x,list[0].y),client:{...list[0]}};
    };
    svg.onpointerdown=event=>{
      if(event.pointerType==='mouse'&&event.button!==0)return;
      if(pointers.size===0){moved=false;multi=false;scroll=this.scrollContainer(svg);roomSensor=event.target?.closest?.('[data-room-sensor]')?.dataset.roomSensor||null;}
      this.interaction=true;
      pointers.set(event.pointerId,{x:event.clientX,y:event.clientY,lastY:event.clientY});
      if(pointers.size>1){multi=true;moved=true;}
      svg.setPointerCapture(event.pointerId);snapshot();
    };
    svg.onpointermove=event=>{
      const old=pointers.get(event.pointerId);if(!old)return;
      const lastY=old.y;
      pointers.set(event.pointerId,{x:event.clientX,y:event.clientY});
      const list=[...pointers.values()],view=this.view(floor);
      if(list.length===2 && gesture?.distance>0) {
        const a=this.canvasPoint(svg,list[0].x,list[0].y),b=this.canvasPoint(svg,list[1].x,list[1].y);
        const mid={x:(a.x+b.x)/2,y:(a.y+b.y)/2};
        view.scale=Math.max(1,Math.min(6,gesture.view.scale*Math.hypot(a.x-b.x,a.y-b.y)/gesture.distance));
        view.x=mid.x-(gesture.mid.x-gesture.view.x)/gesture.view.scale*view.scale;
        view.y=mid.y-(gesture.mid.y-gesture.view.y)/gesture.view.scale*view.scale;
        this.applyViewport(svg);
      } else if(list.length===1 && gesture?.point) {
        if(Math.hypot(event.clientX-gesture.client.x,event.clientY-gesture.client.y)>7)moved=true;
        if(moved && view.scale>1) {
          const point=this.canvasPoint(svg,event.clientX,event.clientY);
          view.x=gesture.view.x+point.x-gesture.point.x;
          view.y=gesture.view.y+point.y-gesture.point.y;
          this.applyViewport(svg);
        } else if(moved && !multi && event.pointerType!=='mouse' && scroll) scroll.scrollTop-=event.clientY-lastY;
      }
    };
    const finish=event=>{
      if(!pointers.has(event.pointerId))return;
      const tap=pointers.size===1&&!moved&&!multi&&event.type!=='pointercancel';
      pointers.delete(event.pointerId);
      if(pointers.size){snapshot();return;}
      this.interaction=false;
      if(tap){if(roomSensor)this.selectSensor(roomSensor);else this.mapClick(event,svg,current,data);}
      if(this.deferred){this.deferred=false;this.render();}
    };
    svg.onpointerup=finish;svg.onpointercancel=finish;
    svg.addEventListener('wheel',event=>{event.preventDefault();this.zoomAt(svg,this.view(floor).scale*Math.exp(-event.deltaY*.002),this.canvasPoint(svg,event.clientX,event.clientY));},{passive:false});
  }
  selectSensor(sensor) {
    if(this.busy)return;
    this.selected=sensor;this.mode='view';this.draft=[];this.pendingSample=null;this.orient=null;
    this.message='';
    this.render();
  }
  bindRoomButton(button, tap=null) {
    const sensorId=button.dataset.selectSensor||button.dataset.toggleHold;
    let timer=null,start=null,longPressed=false;
    const clear=()=>{if(timer!==null)clearTimeout(timer);timer=null;};
    const finish=()=>{clear();this.interaction=false;setTimeout(()=>{if(this.deferred){this.deferred=false;this.render();}},0);};
    button.onpointerdown=event=>{
      if(event.button!==0)return;
      clear();longPressed=false;start={x:event.clientX,y:event.clientY};this.interaction=true;
      button.setPointerCapture?.(event.pointerId);
      timer=setTimeout(()=>{timer=null;longPressed=true;this.releaseHold(sensorId);},650);
    };
    button.onpointermove=event=>{if(start&&Math.hypot(event.clientX-start.x,event.clientY-start.y)>12){longPressed=true;finish();}};
    button.onpointerup=finish;
    button.onpointercancel=()=>{longPressed=true;finish();};
    button.oncontextmenu=event=>{event.preventDefault();if(!longPressed){clear();longPressed=true;this.releaseHold(sensorId);}};
    button.onclick=event=>{if(longPressed){event.preventDefault();longPressed=false;return;}if(tap)tap();else this.selectSensor(sensorId);};
  }
  async releaseHold(sensorId) {
    const sensor=this.data()?.sensors?.find(s=>s.id===sensorId);
    if(!sensor)return;
    if(sensor.targets?.length){this.message=`${sensor.room}: Frisches Radarziel vorhanden.`;this.render();return;}
    if(await this.service('release',{room:sensorId})){this.message=`${sensor.room}: Gehaltene Belegung gelöst.`;this.render();}
  }
  async switchEntity(entityId,on) {
    if(!entityId)return;
    try { await this._hass.callService('switch',on?'turn_on':'turn_off',{entity_id:entityId}); }
    catch(error) {this.message=error.message||String(error);this.render();}
  }
  async setControlMode(sensorMode) {
    await this.switchEntity(this.data()?.entities?.map_mode,!sensorMode);
  }
  async toggleControlMode() {
    await this.setControlMode(this.data()?.map_mode!==false);
  }
  async toggleHold(sensorId) {
    const sensor=this.data()?.sensors?.find(s=>s.id===sensorId);
    if(!sensor)return;
    await this.switchEntity(sensor.entities?.hold,sensor.hold_enabled===false);
  }
  async saveSensorLocation() {
    if(this.busy||this.mode!=='sensor'||!this.pendingSample)return;
    if(await this.service('set_location',{room:this.selected,x:this.pendingSample[0],y:this.pendingSample[1]})) {
      this.pendingSample=null;this.mode='orient';this.orient=null;this.message='Sensor platziert. Jetzt den Blickfächer drehen, bis er zur Montage passt.';this.render();
    }
  }
  orientation(sensor,info) {
    // Aktive Ausrichtung, sonst Vorschlag aus den Messpunkten, sonst Richtung Raummitte.
    if(!sensor?.sensor_location)return null;
    if(this.orient?.sensor===sensor.id)return {...this.orient,source:'draft'};
    if(sensor.heading!=null)return {heading:sensor.heading,mirrored:Boolean(sensor.mirrored),source:'saved'};
    if(sensor.estimated_orientation)return {heading:sensor.estimated_orientation[0],mirrored:sensor.estimated_orientation[1],source:'estimate'};
    const room=(info?.rooms||[]).find(r=>r.name===sensor.map_room);
    const [x,y]=sensor.sensor_location;
    const heading=room?Math.round((Math.atan2(room.y-y,room.x-x)*180/Math.PI+360)%360):90;
    return {heading,mirrored:false,source:'room'};
  }
  rotateSensor(delta,mirror=false) {
    const data=this.data(),sensor=data?.sensors?.find(s=>s.id===this.selected);
    const current=this.orientation(sensor,data?.floors?.[sensor?.floor]);
    if(!current)return;
    this.orient={sensor:sensor.id,heading:Math.round(((current.heading+delta)%360+360)%360*10)/10,mirrored:mirror?!current.mirrored:current.mirrored};
    this.render();
    clearTimeout(this.orientTimer);
    this.orientTimer=setTimeout(()=>this.saveOrientation(),500);
  }
  async saveOrientation() {
    clearTimeout(this.orientTimer);
    const data=this.data(),sensor=data?.sensors?.find(s=>s.id===this.selected);
    const current=this.orientation(sensor,data?.floors?.[sensor?.floor]);
    if(!current)return;
    try {
      await this._hass.callService('radar_occupancy','set_orientation',{room:sensor.id,heading:current.heading,mirrored:current.mirrored});
      this.message=`${sensor.room}: Blickrichtung ${current.heading.toLocaleString('de-DE')}° gespeichert${current.mirrored?' (gespiegelt)':''}.${sensor.mount==='ceiling'?'':' Die Positionen folgen jetzt Standort und Winkel.'}`;
    } catch(error) {this.message=error.message||String(error);}
    this.render();
  }
  async saveSample() {
    if(this.busy||this.mode!=='sample'||!this.pendingSample)return;
    const point=[...this.pendingSample],sensor=this.selected;
    if(await this.service('sample',{room:sensor,x:point[0],y:point[1]})) {
      this.pendingSample=null;this.mode='view';this.render();
    }
  }
  async service(name,data={}) {
    this.busy=true;this.render();
    try { await this._hass.callService('radar_occupancy',name,data);this.message=name==='sample'?'Messpunkt gespeichert. Der Einmessfortschritt wird oben angezeigt.':name==='undo_sample'?'Letzter Messpunkt entfernt. Gehe für den neuen Punkt möglichst 1 m vom verbleibenden Standort weg.':name==='set_exit'?'Ausgang gespeichert. Wer dort verschwindet, hat die Wohnung verlassen.':name==='set_boundary'?'Grenze gespeichert. Für frühes Einblenden auch den Türvorbereich einzeichnen.':'Gespeichert.';return true; }
    catch(error) { this.message=error.message || String(error);return false; }
    finally { this.busy=false;this.render(); }
  }
  render() {
    if(this.interaction||this.sensorSelectFocused()){this.deferred=true;return;}
    this.deferred=false;
    this.shadowRoot.querySelectorAll?.('details[data-panel]').forEach(panel=>{this.panels[panel.dataset.panel]=panel.open;});
    const state=this.stateObj();
    if (!state) { this.shadowRoot.innerHTML='<ha-card><p style="padding:24px">Lagebild wird geladen. Falls diese Meldung bleibt: Integration Radar Occupancy mit „Wohnung“ einrichten.</p></ha-card>';return; }
    const data=state.attributes,sensors=data.sensors||[];
    if(!sensors.some(s=>s.id===this.selected))this.selected=sensors[0]?.id||null;
    const current=sensors.find(s=>s.id===this.selected);
    const tracking=data.light_automation!==false;
    const sensorMode=data.map_mode===false;
    const detected=[...new Set((data.targets||[]).filter(t=>t.inside).map(t=>t.room))];
    for(const t of sensors.flatMap(s=>s.targets||[]))if(t.area&&!detected.includes(t.room))detected.push(t.room);
    const open=name=>this.panels[name]?'open':'';
    this.shadowRoot.innerHTML=`<style>
      :host{display:block;box-sizing:border-box;color:var(--primary-text-color);max-width:940px;margin:auto;padding:12px}
      *{box-sizing:border-box}ha-card{display:block;padding:16px;margin-bottom:12px}h1{margin:0;font-size:22px;line-height:1.3}h2{margin:0;font-size:18px}p{line-height:1.45;margin:8px 0}button,select{font:inherit;color:var(--primary-text-color);background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:10px;padding:10px;cursor:pointer;min-height:44px}button:disabled{opacity:.5;cursor:default}button:focus-visible,summary:focus-visible,select:focus-visible{outline:2px solid var(--primary-color);outline-offset:3px}
      .heading,.floor-head,.selector-row,.summary-row{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.heading{margin-bottom:12px}.tracking{display:flex;align-items:center;gap:9px;font-size:13px;font-weight:600}.tracking[aria-checked="true"]{background:#16796b;color:white;border-color:#16796b}.switch-track{width:30px;height:18px;background:#66717d;border-radius:12px;position:relative}.switch-track:after{content:'';position:absolute;width:12px;height:12px;top:3px;left:3px;background:white;border-radius:50%}.tracking[aria-checked="true"] .switch-track{background:#ffffff40}.tracking[aria-checked="true"] .switch-track:after{left:15px}
      .control-modes{display:flex;gap:6px;margin-bottom:12px}.control-modes button{flex:1;font-size:13px}.control-modes button[aria-pressed="true"]{background:#16796b;color:white;border-color:#16796b}.room-button,.hold-button{touch-action:pan-y;user-select:none;-webkit-user-select:none;-webkit-touch-callout:none}
      .selector-row{margin-bottom:12px}.selector-row select{width:150px}.live-status{font-size:13px;flex:1;text-align:right}.muted{color:var(--secondary-text-color)}.status{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}.room-button{display:flex;flex-direction:column;align-items:flex-start;text-align:left;padding:9px 10px;gap:3px;min-width:0}.room-tile{border:1px solid var(--divider-color);border-radius:10px;overflow:hidden}.room-tile.selected{border-color:var(--primary-color)}.room-tile .room-button{width:100%;border:0;border-radius:0;min-height:58px;padding:7px 9px}.hold-button{width:100%;border:0;border-top:1px solid var(--divider-color);border-radius:0;min-height:32px;padding:5px;font-size:11px}.hold-button[aria-checked="true"]{background:var(--secondary-background-color)}.room-button strong{font-size:13px}.room-button span{font-size:11px;color:var(--secondary-text-color)}.room-button.selected{border-color:var(--primary-color)}.room-button.inside{background:#16796b;color:white}.room-button.inside span{color:#e5fffa}.room-button.approach{background:#b76c13;color:white}.room-button.approach span{color:#fff6e5}
      .floors{display:grid;grid-template-columns:minmax(0,1fr);gap:12px}.floor{margin:0;padding:12px}.floor-head{margin-bottom:10px}.map{width:100%;overflow:hidden;background:#e9edf2;border-radius:12px}.map svg{display:block;width:100%;height:auto;max-height:68vh;touch-action:none}.zoom-tools{display:flex;gap:5px;align-items:center;font-size:12px}.zoom-tools button{min-width:42px;padding:7px}.zoom-tools span{min-width:40px;text-align:center}.legend{display:flex;align-items:center;flex-wrap:wrap;gap:16px;font-size:12px;padding:10px 4px 14px}.legend span{display:flex;gap:6px;align-items:center}.dot{width:9px;height:9px;display:inline-block;border-radius:50%;background:#176ee0}.door-key{width:15px;height:9px;border:1px dashed #b76c13;background:#b76c1320}
      details>summary{cursor:pointer;min-height:44px;display:flex;align-items:center;gap:8px;font-size:15px;font-weight:600;list-style:none}details>summary:before{content:'›';font-size:22px;transition:transform .15s}details[open]>summary:before{transform:rotate(90deg)}summary::-webkit-details-marker{display:none}.summary-note{margin-left:auto;font-size:12px;font-weight:400;color:var(--secondary-text-color)}.section-body{padding-top:8px}.toolbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:12px 0}.toolbar button{font-size:13px}.notice{border-left:3px solid var(--primary-color);padding:8px 10px;margin:10px 0;font-size:13px}.setup{font-size:13px;margin:6px 0 12px}.setup strong,.setup span{display:block}.setup span{margin-top:5px}.controls{display:grid;grid-template-columns:1fr 1fr;gap:16px}input{width:100%;accent-color:var(--primary-color)}.help p{font-size:13px}.maintenance{border-top:1px solid var(--divider-color);padding-top:4px}.edit-controls{margin-top:10px}.rotate button{min-width:58px}.heading-value{min-width:56px;text-align:center;font-weight:600}[data-mirror][aria-pressed="true"],[data-mount][aria-pressed="true"]{background:#7a3fc4;color:white;border-color:#7a3fc4}.danger{color:var(--error-color)}
      @media(max-width:650px){:host{padding:8px}ha-card{padding:12px}.floor{padding:10px}h1{font-size:20px}.heading{gap:8px}.tracking{padding:8px;font-size:12px}.tracking-label{display:none}.controls{grid-template-columns:1fr}.map svg{max-height:52vh}.floor-head h2{font-size:16px}.live-status{font-size:12px}.room-button{padding:8px}.room-button strong{font-size:12px}.summary-note{font-size:11px}}
    </style>
    <ha-card class="overview"><div class="heading"><h1>Position im Haus</h1><button class="tracking" id="tracking" role="switch" aria-label="Radar-Lichtautomatik" aria-checked="${tracking}" ${this.busy?'disabled':''}><span class="switch-track" aria-hidden="true"></span><span class="tracking-label">Lichtautomatik</span><span>${tracking?'Aktiv':'Inaktiv'}</span></button></div>
      <div class="control-modes" role="group" aria-label="Lichtsteuerung"><button data-control-mode="sensor" aria-pressed="${sensorMode}">Entfernungsregel</button><button data-control-mode="map" aria-pressed="${!sensorMode}">Karte · Personen</button></div>
      <div class="selector-row"><select id="sensor" aria-label="Raum auswählen">${sensors.map(s=>`<option value="${escapeHtml(s.id)}" ${s.id===this.selected?'selected':''}>${escapeHtml(s.room)}</option>`).join('')}</select><div class="live-status">${detected.length?`Erkannt: <strong>${escapeHtml(detected.join(', '))}</strong>`:'<span class="muted">Kein frisches Ziel</span>'}</div></div>
      <div class="status">${sensors.map(s=>`<div class="room-tile ${s.id===this.selected?'selected':''}"><button class="room-button ${escapeHtml(s.zone)}" data-select-sensor="${escapeHtml(s.id)}" aria-pressed="${s.id===this.selected}"><strong>${escapeHtml(s.room)}</strong><span>${escapeHtml(this.roomStatus(s))}</span></button><button class="hold-button" data-toggle-hold="${escapeHtml(s.id)}" role="switch" aria-label="${escapeHtml(s.room)}: Belegung halten" aria-checked="${s.hold_enabled!==false}">Halten: ${s.hold_enabled!==false?'an':'aus'}</button></div>`).join('')}</div>
      ${this.message?`<div class="notice" role="status">${escapeHtml(this.message)}</div>`:''}
    </ha-card>
    <div class="floors">${Object.keys(data.floors||{}).map(floor=>this.floor(floor,data)).join('')||'<ha-card><p>Noch keinem Raum ist eine Roboterkarte zugeordnet (Raum konfigurieren → Roboterkarte).</p></ha-card>'}</div>
    <div class="legend muted"><span><i class="dot"></i>Radarziel</span><span><i class="door-key"></i>Türvorbereich</span><span><i class="dot" style="background:white;border:2px solid #b76c13"></i>Tür oder Ausgang (gestrichelt: dahinter misst kein Radar)</span><span><i class="door-key" style="border-color:#7a3fc4;background:#7a3fc420"></i>Sichtfeld des gewählten Sensors</span></div>
    <ha-card><details data-panel="calibration" ${open('calibration')}><summary>Einmessen &amp; Bereiche<span class="summary-note">${escapeHtml(current?.room||'')}${current?.calibrated?' · bereit':''}</span></summary><div class="section-body">
      ${this.setupSummary(current)}
      <div class="toolbar"><button id="place-sensor" ${this.busy?'disabled':''}>Sensor platzieren</button><button id="orient-sensor" ${!current?.sensor_location||this.busy?'disabled':''}>${this.mode==='orient'?'Ausrichten aktiv':'Sensor ausrichten'}</button><button id="sample" ${this.busy?'disabled':''}>${this.mode==='sample'?'Standortwahl aktiv':'Messpunkt hinzufügen'}</button><button id="boundary" ${!current?.calibrated||this.busy?'disabled':''}>Raumgrenze korrigieren</button><button id="approach" ${!current?.calibrated||this.busy?'disabled':''}>Türvorbereich korrigieren</button><button id="exit" ${!current?.calibrated||this.busy?'disabled':''}>${this.mode==='exit'?'Ausgang antippen':'Ausgang markieren'}</button><button id="view">Bearbeitung beenden</button></div>
      ${this.mode==='sample'?this.calibrationHint(current):''}
      <details class="maintenance" data-panel="maintenance" ${open('maintenance')}><summary>Weitere Aktionen</summary><div class="toolbar"><button id="undo-sample" ${!current?.samples||this.busy?'disabled':''}>Letzten Messpunkt entfernen</button>${current?.heading!=null?`<button id="clear-orientation" ${this.busy?'disabled':''}>Ausrichtung entfernen</button>`:''}${current?.exits?.length?`<button id="clear-exits" ${this.busy?'disabled':''}>Ausgänge entfernen (${current.exits.length})</button>`:''}<button id="reset" class="danger" ${this.busy?'disabled':''}>Sensor neu einmessen</button><button id="refresh" ${this.busy?'disabled':''}>Karten neu laden</button></div></details>
    </div></details></ha-card>
    <ha-card><details data-panel="transitions" ${open('transitions')}><summary>Lichtübergänge<span class="summary-note">${escapeHtml(data.fade_in)} s ein · ${escapeHtml(data.fade_out)} s aus</span></summary><div class="section-body"><div class="controls">${['fade_in','fade_out'].map((key,i)=>`<label>${i?'Ausblenden':'Einblenden'} · ${escapeHtml(data[key])} s<input aria-label="${i?'Ausblenden':'Einblenden'} in Sekunden" type="range" min="0" max="10" step="0.5" value="${escapeHtml(data[key]??0)}" data-setting="${escapeHtml(data.entities?.[key]||'')}"></label>`).join('')}</div><p class="muted">Vor der Tür ein Teil der Zielhelligkeit (Wohnung konfigurieren), im Raum die Zielhelligkeit des Raums. 0 s: sofort schalten.</p></div></details></ha-card>
    <ha-card><details class="help" data-panel="help" ${open('help')}><summary>Bedienhilfe</summary><div class="section-body"><p>Mit zwei Fingern zoomen, vergrößerte Karten verschieben. Oben ist um 180° gedreht. Raumname oder Raumkachel antippen, um einen Sensor auszuwählen.</p><p>Einmessen: allein an drei verteilten Standorten stehen, jeweils „Messpunkt hinzufügen“, Position markieren und aufnehmen. Ein vierter Punkt prüft die Umrechnung.</p><p>Raumgrenzen und Türvorbereiche kommen aus der Roboterkarte. Unter „Einmessen &amp; Bereiche“ kannst du sie korrigieren.</p><p>Ausgang markieren: Treppe oder Wohnungstür, die die Roboterkarte nicht als Durchgang zeigt. Wer dort verschwindet, hat die Wohnung verlassen. Kartenräume ohne Radar (z. B. ein Flur unten) gelten automatisch als draußen.</p><p>Karte · Personen: Personen werden über die Türen gezählt. Ein Raum ist frei, wenn alle hinausgegangen sind; still Sitzende bleiben gezählt. Licht von Hand im belegten Raum ausgeschaltet bleibt aus, auch nach kurzem Verlassen. Von Hand einschalten oder 30 min ohne Person geben es an die Automatik zurück.</p><p>Raumkachel oder Halten-Knopf etwa eine Sekunde gedrückt halten, um eine gehaltene Belegung einmalig zu lösen (Zähler auf 0). Beim nächsten frischen Radarziel wird der Raum wieder erkannt. „Halten: aus“ beendet die Belegung, sobald kein frisches Radarziel mehr vorhanden ist. „Halten: an“ behält sie bei Aussetzern bei. Sind Sensorstandort und Blickrichtung gesetzt, ersetzen sie die Umrechnung aus den Messpunkten (1 m Radar = 1 m Karte); die Messpunkte bleiben als Kontrolle erhalten.</p><p>Der Modusknopf wechselt zwischen Personenzählung auf der Karte und der Entfernungsregel je Raum (Türbereich als Entfernung zum Sensor). Räume ohne verlässliche Einmessung nutzen immer die Entfernungsregel. Lichtautomatik aus pausiert beide. Die Positionsanzeige bleibt aktiv. Radarziele haben keine Personenidentität; bei mehreren Personen werden alle Ziele angezeigt.</p></div></details></ha-card>`;
    const root=this.shadowRoot;
    root.getElementById('tracking').onclick=()=>this.switchEntity(data.entities?.light_automation,!tracking);
    root.querySelectorAll('[data-control-mode]').forEach(button=>button.onclick=()=>this.setControlMode(button.dataset.controlMode==='sensor'));
    this.bindSensorSelect(root.getElementById('sensor'));
    root.querySelectorAll('[data-toggle-hold]').forEach(button=>this.bindRoomButton(button,()=>this.toggleHold(button.dataset.toggleHold)));
    root.getElementById('place-sensor').onclick=()=>{this.mode='sensor';this.pendingSample=null;this.draft=[];this.message='Montageposition des Sensors auf der Karte markieren.';this.render();};
    root.querySelectorAll('[data-save-location]').forEach(button=>button.onclick=()=>this.saveSensorLocation());
    root.querySelectorAll('[data-select-sensor]').forEach(button=>this.bindRoomButton(button));
    root.querySelectorAll('details[data-panel]').forEach(panel=>panel.ontoggle=()=>{if(panel.isConnected)this.panels[panel.dataset.panel]=panel.open;});
    root.getElementById('sample').onclick=()=>{this.mode='sample';this.draft=[];this.pendingSample=null;this.message='Standort auf der Karte markieren, dann „Messpunkt hier aufnehmen“ drücken.';this.render();};
    root.getElementById('boundary').onclick=()=>{this.mode='boundary';this.draft=[];this.message='Raumgrenze: Ecken auf der Karte antippen.';this.render();};
    root.getElementById('approach').onclick=()=>{this.mode='approach';this.draft=[];this.message='Türvorbereich: Ecken vor der Tür antippen.';this.render();};
    root.getElementById('exit').onclick=()=>{this.mode='exit';this.draft=[];this.pendingSample=null;this.message='Ausgang: die Stelle antippen, an der man die Wohnung verlässt (Treppe, Wohnungstür).';this.render();};
    if(root.getElementById('clear-exits'))root.getElementById('clear-exits').onclick=async()=>{if(confirm('Alle Ausgänge dieses Raums entfernen?'))await this.service('set_exit',{room:this.selected,clear:true});};
    root.querySelectorAll('[data-flip-floor]').forEach(button=>button.onclick=()=>this.service('set_floor',{camera:button.dataset.flipFloor,flip:button.dataset.flipped!=='true'}));
    root.getElementById('view').onclick=()=>{this.mode='view';this.draft=[];this.orient=null;this.render();};
    root.getElementById('orient-sensor').onclick=()=>{this.mode='orient';this.pendingSample=null;this.draft=[];this.message='Blickfächer mit den Drehknöpfen unter der Karte ausrichten.';this.render();};
    if(root.getElementById('clear-orientation'))root.getElementById('clear-orientation').onclick=async()=>{if(confirm('Ausrichtung entfernen? Danach gilt wieder die Umrechnung aus den Messpunkten.')&&await this.service('set_orientation',{room:this.selected,clear:true})){this.orient=null;this.render();}};
    root.querySelectorAll('[data-rotate]').forEach(button=>button.onclick=()=>this.rotateSensor(Number(button.dataset.rotate)));
    root.querySelectorAll('[data-mirror]').forEach(button=>button.onclick=()=>this.rotateSensor(0,true));
    root.querySelectorAll('[data-mount]').forEach(button=>button.onclick=()=>this.service('set_orientation',{room:this.selected,mount:button.dataset.mount}));
    root.querySelectorAll('[data-height]').forEach(button=>button.onclick=()=>{const s=this.data()?.sensors?.find(x=>x.id===this.selected);this.service('set_orientation',{room:this.selected,height:Math.max(1500,Math.min(5000,(s?.mount_height||2500)+Number(button.dataset.height)))});});
    root.querySelectorAll('[data-orient-save]').forEach(button=>button.onclick=()=>this.saveOrientation());
    root.getElementById('undo-sample').onclick=()=>this.service('undo_sample',{room:this.selected});
    root.getElementById('refresh').onclick=()=>this.service('refresh_maps');
    const resetSensor=async()=>{if (confirm('Alle Messpunkte und die Raumgrenze dieses Sensors löschen?')) {if(await this.service('reset_calibration',{room:this.selected})){this.mode='view';this.draft=[];this.pendingSample=null;this.render();}}};
    root.getElementById('reset').onclick=resetSensor;
    root.querySelectorAll('[data-reset-sensor]').forEach(button=>button.onclick=resetSensor);
    root.querySelectorAll('[data-undo-sample]').forEach(button=>button.onclick=()=>this.service('undo_sample',{room:this.selected}));
    if(root.getElementById('save'))root.getElementById('save').onclick=async()=>{if(await this.service('set_boundary',{room:this.selected,points:this.draft,kind:this.mode==='approach'?'approach':'room'})){this.mode='view';this.draft=[];this.render();}};
    if(root.getElementById('undo'))root.getElementById('undo').onclick=()=>{this.draft.pop();this.render();};
    root.querySelectorAll('[data-save-sample]').forEach(button=>button.onclick=()=>this.saveSample());
    root.querySelectorAll('[data-cancel-sample]').forEach(button=>button.onclick=()=>{if(this.orientTimer)this.saveOrientation();this.mode='view';this.pendingSample=null;this.orient=null;this.render();});
    root.querySelectorAll('[data-room-sensor]').forEach(label=>label.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();this.selectSensor(label.dataset.roomSensor);}});
    root.querySelectorAll('svg[data-floor]').forEach(svg=>this.bindMap(svg,current,data));
    root.querySelectorAll('[data-zoom-action]').forEach(button=>button.onclick=()=>{
      const floor=button.dataset.zoomFloor,svg=root.querySelector(`svg[data-floor="${floor}"]`);
      const action=button.dataset.zoomAction,view=this.view(floor),box=svg.viewBox.baseVal;
      if(action==='reset'){view.scale=1;view.x=0;view.y=0;this.applyViewport(svg);}
      else this.zoomAt(svg,view.scale*(action==='in'?1.5:1/1.5),{x:box.width/2,y:box.height/2});
    });
    root.querySelectorAll('[data-setting]').forEach(input=>{input.onblur=()=>Promise.resolve().then(()=>{if(this.deferred)this.refreshView();});input.onchange=e=>this._hass.callService('number','set_value',{entity_id:input.dataset.setting,value:Number(e.target.value)}).catch(error=>{this.message=error.message;this.render();});});
  }
  roomStatus(sensor) {
    if(!sensor.available)return 'Offline';
    if(!sensor.calibrated)return 'Einmessen';
    if(sensor.map_ready&&sensor.people!=null) {
      const people=sensor.people===0?'Frei':sensor.people===1?'1 Person':`${sensor.people} Personen`;
      return sensor.light_mode==='manual_off'?`${people} · Licht manuell aus`:people;
    }
    if(sensor.zone==='lost')return sensor.occupied?'Belegung gehalten':'Frei';
    return labels[sensor.zone]||'Bereit';
  }
  setupSummary(current) {
    if(!current)return '';
    if(!current.calibrated)return `<div class="setup"><strong>${escapeHtml(current.room)}: Einmessen läuft</strong><span>${current.samples||0} Messpunkte · mindestens 3 Standorte nötig.</span></div>`;
    const boundary=current.polygon?.length;
    const warning=current.plausible===false?`<span class="danger">Die Umrechnung aus den Messpunkten ist stark verzerrt. Positionen dieses Raums sind unzuverlässig; die Belegung nutzt deshalb die Entfernungsregel. Abhilfe: „Sensor platzieren“ und „Sensor ausrichten“.</span>`:'';
    const source=current.transform_source==='orientation'?`<span>Umrechnung aus Standort und Blickrichtung (${Number(current.heading).toLocaleString('de-DE')}°${current.mirrored?', gespiegelt':''})${current.orientation_error_mm!=null?` · ${(current.orientation_error_mm/10).toLocaleString('de-DE')} cm Abstand zu den Messpunkten`:''}.</span>`:'';
    return `<div class="setup" data-setup-complete><strong>${escapeHtml(current.room)}: Einmessen abgeschlossen</strong><span>${current.samples} Messpunkte gespeichert${current.error_mm!=null?` · ${(current.error_mm/10).toLocaleString('de-DE')} cm Abweichung`:''}</span><span>${boundary?(current.boundary_source==='map'?'Raumgrenze automatisch aus der Roboterkarte.':'Raumgrenze manuell gespeichert.'):'Raumgrenze noch nicht verfügbar.'} ${current.approach_polygons?.length?'Türvorbereich eingerichtet.':'Türvorbereich fehlt.'}${current.exits?.length?` ${current.exits.length===1?'Ein Ausgang':current.exits.length+' Ausgänge'} markiert.`:''}</span>${(current.sample_points||[]).some(s=>s.area&&s.area!=='room')?'<span>Teilbereich-Referenz (z. B. Balkon) separat gespeichert.</span>':''}${source}${warning}${current.map_ready?`<span>Belegung: ${current.occupied?'belegt':'frei'}${current.occupancy_reason?` – ${escapeHtml(current.occupancy_reason)}`:''}. Frei wird der Raum nur, wenn alle nachweislich durch eine Tür hinausgegangen sind.</span>`:''}</div>`;
  }
  calibrationHint(current) {
    if(current?.calibrated&&this.mode!=='sample')return '';
    const points=current?.sample_points||[];
    if(!points.length)return '';
    const distances=points.slice(1).map((point,i)=>Math.hypot(...point.radar.map((v,j)=>v-points[i].radar[j])));
    const badBaseline=points.length===2&&distances[0]<300;
    const target=current.targets?.length===1?current.targets[0]:null;
    const nearest=target?Math.min(...points.map(p=>Math.hypot(...p.radar.map((v,j)=>v-target.radar[j])))):null;
    return `${badBaseline?`<div class="notice">Die ersten beiden Radar-Messpunkte liegen nur ${Math.round(distances[0]/10)} cm auseinander. Entferne den letzten Messpunkt und gehe für den zweiten Standort möglichst 1 m weit.</div>`:''}${nearest!==null?`<p class="muted">Aktueller Radar-Abstand zum nächsten gespeicherten Punkt: ${Math.round(nearest/10)} cm. Tippe deinen tatsächlichen Standort an, sobald du dort stehst.</p>`:'<p class="muted">Zum Messen muss genau ein frisches Radarziel sichtbar sein. Bewege dich leicht.</p>'}`;
  }
  floor(floor,data) {
    const info=data.floors?.[floor],url=this.images[floor]?.url;
    const convert=affine(info?.calibration_points,'vacuum','map');
    const title=escapeHtml(info?.name||this._hass?.states?.[info?.camera||floor]?.attributes?.friendly_name||floor);
    if (!info?.width||!url) return `<ha-card class="floor"><h2>${title}</h2><p>${info?.error&&info.error!=='loading'?'Karte nicht verfügbar. Ist die Roboterkarte gespeichert?':'Karte wird geladen.'} Falls sie nicht erscheint, „Karten neu laden“ verwenden.</p></ha-card>`;
    const polygons=(data.sensors||[]).filter(s=>s.floor===floor&&s.polygon?.length).map(s=>{const ps=convert&&s.polygon.map(p=>convert(...p));return ps?`<polygon points="${ps.map(p=>p.join(',')).join(' ')}" fill="#16796b" fill-opacity=".10" stroke="#16796b" stroke-width="2" vector-effect="non-scaling-stroke"/>`:'';}).join('');
    const approach=(data.sensors||[]).filter(s=>s.floor===floor).flatMap(s=>s.approach_polygons||[]).filter(p=>p.length).map(polygon=>{const ps=convert&&polygon.map(p=>convert(...p));return ps?`<polygon points="${ps.map(p=>p.join(',')).join(' ')}" fill="#b76c13" fill-opacity=".15" stroke="#b76c13" stroke-width="2" stroke-dasharray="6 4" vector-effect="non-scaling-stroke"/>`:'';}).join('');
    const displayPoint=p=>info.flip?[info.width-p[0],info.height-p[1]]:p;
    const targetList=(data.targets||[]).filter(t=>t.floor===floor);
    const targets=targetList.map(t=>{const p=convert&&convert(...t.map);return p?`<circle cx="${p[0]}" cy="${p[1]}" r="${info.width/90}" fill="#176ee0" stroke="white" stroke-width="2" vector-effect="non-scaling-stroke"/>`:'';}).join('');
    const targetLabels=targetList.map(t=>{const p=convert&&displayPoint(convert(...t.map));return p?`<text x="${p[0]+info.width/60}" y="${p[1]}" fill="#12395e" stroke="white" stroke-width="3" paint-order="stroke" font-size="${info.width/45}">${escapeHtml(t.room)} ${t.target}</text>`:'';}).join('');
    const selected=(data.sensors||[]).find(s=>s.id===this.selected);
    const roomLabels=(info.rooms||[]).map(room=>{
      const p=convert&&displayPoint(convert(room.x,room.y));if(!p)return '';
      const sensor=(data.sensors||[]).find(s=>s.floor===floor&&s.map_room===room.name);
      const name=sensor?.room||room.name;
      const font=info.width/42,width=Math.max(font*3,name.length*font*.62+font),height=font*1.7;
      const selectable=sensor?` data-room-sensor="${escapeHtml(sensor.id)}" role="button" tabindex="0" aria-label="${escapeHtml(name)} auswählen" style="cursor:pointer"`:'';
      return `<g${selectable} transform="translate(${p[0]} ${p[1]})"><rect x="${-width/2}" y="${-height/2}" width="${width}" height="${height}" rx="${height/2}" fill="#fff" fill-opacity=".93" stroke="#718399"/><text text-anchor="middle" dominant-baseline="central" fill="#17334f" font-size="${font}">${escapeHtml(name)}</text></g>`;
    }).join('');
    const sensorMarkers=(data.sensors||[]).filter(s=>s.floor===floor&&s.sensor_location).map(s=>{
      const p=convert&&displayPoint(convert(...s.sensor_location));if(!p)return '';
      const r=info.width/70;
      return `<g data-sensor-location="${escapeHtml(s.id)}" transform="translate(${p[0]} ${p[1]})" pointer-events="none"><title>${escapeHtml(s.room)} · Sensor</title><rect x="${-r}" y="${-r}" width="${r*2}" height="${r*2}" rx="${r/3}" fill="#29394b" stroke="white" stroke-width="2" vector-effect="non-scaling-stroke"/><circle r="${r/3}" fill="white"/></g>`;
    }).join('');
    const pose=selected?.floor===floor?this.orientation(selected,info):null;
    const fovTransform=pose?rigid(selected.sensor_location,pose.heading,pose.mirrored):selected?.floor===floor&&selected?.transform?selected.transform:null;
    const tentative=!pose||pose.source==='estimate'||pose.source==='room';
    let fov='',fovLabel='';
    if(fovTransform&&convert) {
      const at=(x,y)=>convert(...projectRadar(fovTransform,x,y)).map(v=>Math.round(v*10)/10);
      const ceiling=selected.mount==='ceiling'&&pose;
      const ring=(height,count=48)=>Array.from({length:count},(_,i)=>{const t=i/count*2*Math.PI;return at(height*Math.tan(FOV_DEG*Math.PI/180)*Math.cos(t),height*Math.tan(FOV_PITCH*Math.PI/180)*Math.sin(t));});
      const arc=r=>Array.from({length:25},(_,i)=>{const a=(-FOV_DEG+i*FOV_DEG/12)*Math.PI/180;return at(r*Math.sin(a),r*Math.cos(a));});
      const origin=at(0,0),edge=arc(FOV_RANGE);
      const stroke=tentative?'stroke-dasharray="7 5"':'';
      const height=selected.mount_height||2500,font=info.width/55;
      if(ceiling) {
        // Nach unten schauend: Erfassungsfläche am Boden (außen) und auf Oberkörperhöhe (innen).
        fov=`<g data-fov data-ceiling pointer-events="none"><polygon points="${ring(height).map(p=>p.join(',')).join(' ')}" fill="#7a3fc4" fill-opacity="${tentative?.06:.12}" stroke="#7a3fc4" stroke-width="2" ${stroke} vector-effect="non-scaling-stroke"/><polygon points="${ring(Math.max(300,height-1000)).map(p=>p.join(',')).join(' ')}" fill="none" stroke="#7a3fc4" stroke-opacity=".55" stroke-width="1" stroke-dasharray="3 4" vector-effect="non-scaling-stroke"/><line x1="${origin[0]}" y1="${origin[1]}" x2="${at(height*Math.tan(FOV_DEG*Math.PI/180),0)[0]}" y2="${at(height*Math.tan(FOV_DEG*Math.PI/180),0)[1]}" stroke="#7a3fc4" stroke-width="1" stroke-dasharray="3 4" vector-effect="non-scaling-stroke"/></g>`;
        const plus=displayPoint(at(height*Math.tan(FOV_DEG*Math.PI/180)*.75,0));
        fovLabel=`<text pointer-events="none" x="${plus[0]}" y="${plus[1]}" text-anchor="middle" fill="#5a2a99" stroke="white" stroke-width="3" paint-order="stroke" font-size="${font}">+X</text>`;
      } else {
      fov=`<g data-fov pointer-events="none"><polygon points="${[origin,...edge].map(p=>p.join(',')).join(' ')}" fill="#7a3fc4" fill-opacity="${tentative?.06:.12}" stroke="#7a3fc4" stroke-width="2" ${stroke} vector-effect="non-scaling-stroke"/>${[2000,4000].map(r=>`<polyline points="${arc(r).map(p=>p.join(',')).join(' ')}" fill="none" stroke="#7a3fc4" stroke-opacity=".45" stroke-width="1" vector-effect="non-scaling-stroke"/>`).join('')}<line x1="${origin[0]}" y1="${origin[1]}" x2="${at(0,FOV_RANGE)[0]}" y2="${at(0,FOV_RANGE)[1]}" stroke="#7a3fc4" stroke-width="1" stroke-dasharray="3 4" vector-effect="non-scaling-stroke"/></g>`;
      const plus=displayPoint(at(1400,1600));
      fovLabel=`<text pointer-events="none" x="${plus[0]}" y="${plus[1]}" text-anchor="middle" fill="#5a2a99" stroke="white" stroke-width="3" paint-order="stroke" font-size="${font}">+X</text>${[2,4,6].map(m=>{const p=displayPoint(at(0,m*1000));return `<text pointer-events="none" x="${p[0]}" y="${p[1]}" text-anchor="middle" fill="#5a2a99" stroke="white" stroke-width="3" paint-order="stroke" font-size="${font*.85}">${m} m</text>`;}).join('')}`;
      }
    }
    const doors=(data.doors||[]).filter(d=>d.floor===floor&&d.point&&convert).map(d=>{
      const p=convert(...d.point),r=info.width/110;
      const seen=Object.values(typeof d.covered==='object'?d.covered:{x:d.covered}).some(Boolean);
      return `<circle data-door="${escapeHtml(d.a)}-${escapeHtml(d.b)}" cx="${p[0]}" cy="${p[1]}" r="${r}" fill="white" stroke="#b76c13" stroke-width="2" ${seen?'':'stroke-dasharray="3 2"'} vector-effect="non-scaling-stroke"><title>Tür ${escapeHtml(d.a)} – ${escapeHtml(d.b)}</title></circle>`;
    }).join('');
    const orienting=this.mode==='orient'&&selected?.floor===floor&&pose;
    const orientControls=orienting?`<div class="edit-controls" data-orient-controls><strong>${escapeHtml(selected.room)} · Blickfeld ausrichten</strong><div class="toolbar" role="group" aria-label="Montageart"><button data-mount="wall" aria-pressed="${selected.mount!=='ceiling'}">Wand</button><button data-mount="ceiling" aria-pressed="${selected.mount==='ceiling'}">Decke</button>${selected.mount==='ceiling'?`<button data-height="-100" aria-label="Montagehöhe verringern">− 10 cm</button><span class="heading-value">${((selected.mount_height||2500)/1000).toLocaleString('de-DE')} m hoch</span><button data-height="100" aria-label="Montagehöhe erhöhen">+ 10 cm</button>`:''}</div><p class="muted">${selected.mount==='ceiling'?`Deckenmontage: Die Ellipse zeigt die Erfassung am Boden (±${FOV_DEG}° entlang +X, ±${FOV_PITCH}° quer), die gestrichelte auf Oberkörperhöhe. Drehen, bis +X zur Einbaulage passt. Vorne und hinten quer zu +X kann der Sensor nicht unterscheiden; Positionen kommen deshalb weiter aus den Messpunkten.`:`Der Fächer zeigt, was der Sensor sieht (±${FOV_DEG}°, ${FOV_RANGE/1000} m). Drehen, bis er zur Montage passt. Prüfen: Stehst du im Raum, muss dein Punkt an deinem Standort erscheinen. Liegt er seitenverkehrt, „Links/Rechts tauschen“.`}</p><div class="toolbar rotate">${[15,5,1].map(d=>`<button data-rotate="${d}" aria-label="${d} Grad gegen den Uhrzeigersinn">⟲ ${d}°</button>`).join('')}<span class="heading-value">${Number(pose.heading).toLocaleString('de-DE')}°</span>${[1,5,15].map(d=>`<button data-rotate="-${d}" aria-label="${d} Grad im Uhrzeigersinn">⟳ ${d}°</button>`).join('')}</div><div class="toolbar"><button data-mirror aria-pressed="${Boolean(pose.mirrored)}">Links/Rechts tauschen</button>${pose.source==='estimate'||pose.source==='room'?'<button data-orient-save>Diese Richtung übernehmen</button>':''}<button data-cancel-sample>Fertig</button></div><p class="muted">${pose.source==='saved'?(selected.mount==='ceiling'?'Gespeichert. Die Ellipse dient der Kontrolle; Positionen kommen weiter aus den Messpunkten.':'Gespeichert. Positionen folgen Standort und Blickrichtung.'):pose.source==='draft'?'Wird gespeichert …':pose.source==='estimate'?'Vorschlag aus den Messpunkten, noch nicht gespeichert.':'Vorschlag: Richtung Raummitte, noch nicht gespeichert.'}</p></div>`:'';
    const sampleMarkers=selected?.floor===floor&&convert?(selected.sample_points||[]).map((sample,i)=>{
      if(sample.area&&sample.area!=='room')return '';
      const p=displayPoint(convert(...sample.map)),radius=info.width/65;
      return `<g data-sample-marker="${i+1}" transform="translate(${p[0]} ${p[1]})"><circle r="${radius}" fill="#b85c00" stroke="white" stroke-width="2" vector-effect="non-scaling-stroke"/><text text-anchor="middle" dominant-baseline="central" fill="white" font-size="${radius*1.4}">${i+1}</text></g>`;
    }).join(''):'';
    const draft=['boundary','approach'].includes(this.mode)&&selected?.floor===floor&&convert?`<polyline points="${this.draft.map(p=>convert(...p).join(',')).join(' ')}" fill="none" stroke="#d87a00" stroke-width="3" vector-effect="non-scaling-stroke"/>`:'';
    const measuring=this.mode==='sample'&&selected?.floor===floor;
    const placingSensor=this.mode==='sensor'&&selected?.floor===floor;
    const pending=(measuring||placingSensor)&&this.pendingSample&&convert?displayPoint(convert(...this.pendingSample)):null;
    const marker=pending?`<g data-pending-sample transform="translate(${pending[0]} ${pending[1]})" pointer-events="none"><circle r="${info.width/45}" fill="none" stroke="#b85c00" stroke-width="3" vector-effect="non-scaling-stroke"/><path d="M -${info.width/30} 0 H ${info.width/30} M 0 -${info.width/30} V ${info.width/30}" stroke="#b85c00" stroke-width="2" vector-effect="non-scaling-stroke"/></g>`:'';
    const measurementControls=measuring?`<div class="notice"><strong>${escapeHtml(selected.room)} · Messpunkt</strong><p>Deinen Standort markieren und bis zur Aufnahme dort stehen bleiben.</p>${this.calibrationHint(selected)}<div class="toolbar"><button data-save-sample ${!pending||this.busy||selected.targets?.length!==1?'disabled':''}>Messpunkt hier aufnehmen</button><button data-cancel-sample>Abbrechen</button>${selected.samples?`<button data-undo-sample ${this.busy?'disabled':''}>Letzten Messpunkt entfernen</button><button data-reset-sensor ${this.busy?'disabled':''}>Diesen Sensor neu einmessen</button>`:''}</div><p class="muted">${pending?'Standort markiert.':'Standort auf der Karte antippen.'}</p></div>`:'';
    const locationControls=placingSensor?`<div class="edit-controls"><strong>${escapeHtml(selected.room)} · Sensor platzieren</strong><p class="muted">Montageposition antippen. Die Messpunkte bleiben erhalten.</p><div class="toolbar"><button data-save-location ${!pending||this.busy?'disabled':''}>Sensor hier platzieren</button><button data-cancel-sample>Abbrechen</button></div></div>`:'';
    const boundaryControls=['boundary','approach'].includes(this.mode)&&selected?.floor===floor?`<div class="edit-controls"><strong>${escapeHtml(selected.room)} · ${this.mode==='approach'?'Türvorbereich':'Raumgrenze'}</strong><div class="toolbar"><span>${this.draft.length} Ecken</span><button id="save" ${this.draft.length<3||this.busy?'disabled':''}>Speichern</button><button id="undo">Letzte Ecke entfernen</button><button data-cancel-sample>Abbrechen</button></div></div>`:'';
    const view=this.view(floor);
    const rotation=info.flip?`rotate(180 ${info.width/2} ${info.height/2})`:'';
    const exitHint=this.mode==='exit'&&selected?.floor===floor?`<div class="edit-controls"><strong>${escapeHtml(selected.room)} · Ausgang markieren</strong><p class="muted">Die Stelle antippen, an der man die Wohnung verlässt. Wird sofort gespeichert.</p><div class="toolbar"><button data-cancel-sample>Fertig</button></div></div>`:'';
    return `<ha-card class="floor"><div class="floor-head"><h2>${title}</h2><div class="zoom-tools"><button data-flip-floor="${escapeHtml(floor)}" data-flipped="${Boolean(info.flip)}" aria-label="Karte um 180° drehen">↻ 180°</button><button data-zoom-floor="${floor}" data-zoom-action="out" aria-label="Karte verkleinern">−</button><span data-zoom-label="${floor}">${Math.round(view.scale*100)} %</span><button data-zoom-floor="${floor}" data-zoom-action="in" aria-label="Karte vergrößern">+</button><button data-zoom-floor="${floor}" data-zoom-action="reset" aria-label="Gesamtansicht">Gesamt</button></div></div><div class="map"><svg data-floor="${floor}" viewBox="0 0 ${info.width} ${info.height}" xmlns="http://www.w3.org/2000/svg"><g data-zoom-space transform="translate(${view.x} ${view.y}) scale(${view.scale})"><g data-map-space transform="${rotation}"><image href="${escapeHtml(url)}" width="${info.width}" height="${info.height}"/>${polygons}${approach}${fov}${doors}${draft}${targets}</g>${roomLabels}${fovLabel}${targetLabels}${sampleMarkers}${sensorMarkers}${marker}</g></svg></div>${measurementControls}${locationControls}${orientControls}${boundaryControls}${exitHint}${!convert?'<p class="muted">Kartenkoordinaten fehlen; Karten neu laden.</p>':''}</ha-card>`;
  }
  async mapClick(event,svg,current,data) {
    if(this.mode==='view'||this.busy)return;
    const floor=svg.dataset.floor;
    if(current?.floor!==floor){this.message='Bitte die Karte des ausgewählten Sensors verwenden.';this.render();return;}
    const convert=affine(data.floors[floor]?.calibration_points,'map','vacuum');
    if(!convert){this.message='Kartenkoordinaten fehlen. Bitte Karten neu laden.';this.render();return;}
    const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;
    const p=point.matrixTransform(svg.querySelector('[data-map-space]').getScreenCTM().inverse());const coords=convert(p.x,p.y);
    if(this.mode==='exit'){await this.service('set_exit',{room:this.selected,x:Math.round(coords[0]),y:Math.round(coords[1])});return;}
    if(['sample','sensor'].includes(this.mode)){this.pendingSample=coords;this.message=this.mode==='sensor'?'Sensorposition markiert – jetzt speichern.':'Standort markiert – jetzt aufnehmen.';this.render();}
    else {this.draft.push(coords);this.render();}
  }
}
// Ressourcen und extra_module_url können dasselbe Modul laden. Eine später
// geladene Erweiterung kann window.customElements durch ein Registry-Polyfill
// ersetzen; früher registrierte Karten sind darin unbekannt („Konfigurationsfehler“).
// Deshalb jede Komponente mit eigener Unterklasse nachregistrieren, solange sie fehlt.
const RADAR_CARD_NAMES=['radar-occupancy-card'];
function registerRadarCards() {
  for(const name of RADAR_CARD_NAMES) {
    if(customElements.get(name))continue;
    try { customElements.define(name,class extends RadarOccupancyCard {}); } catch(error) {}
  }
}
registerRadarCards();
if(typeof window!=='undefined') {
  window.customCards=window.customCards||[];
  if(!window.customCards.some(c=>c.type==='radar-occupancy-card'))window.customCards.push({type:'radar-occupancy-card',name:'Radar Occupancy',description:'Roboterkarten, Personen je Raum und Einmessen der Radarsensoren.'});
}
if(typeof setInterval==='function') {
  let checks=0;
  const timer=setInterval(()=>{registerRadarCards();if(++checks>=120)clearInterval(timer);},250);
}
