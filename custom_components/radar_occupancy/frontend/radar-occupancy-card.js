/* Radar Occupancy: floor maps, anonymous radar targets, people per room and guided calibration.
   Served by the integration and loaded into every dashboard (type: custom:radar-occupancy-card).
   Texts in English and German, chosen by the user's Home Assistant language. */
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const I18N={"en":{"zone_inside":"Inside","zone_approach":"In front of the room","zone_outside":"Outside","zone_lost":"Target lost","zone_unreliable":"Check calibration","zone_uncalibrated":"Not calibrated yet","zone_unavailable":"Sensor offline","image_failed":"Map image could not be loaded: ","target_present":"{room}: a live radar target is present.","released_msg":"{room}: held occupancy released.","placed":"Sensor placed. Now turn the field of view until it matches the mounting.","heading_saved":"{room}: heading {heading}° saved{mirrored}.","mirrored_suffix":" (mirrored)","heading_follow":" Positions now follow location and heading.","svc_sample":"Calibration point saved. Progress is shown above.","svc_undo_sample":"Last calibration point removed. For the next point, go about 1 m away from the remaining location.","svc_set_exit":"Exit saved. Whoever vanishes there has left the home.","svc_set_door":"Door saved. People are counted through it.","svc_set_boundary":"Outline saved. For early pre-lighting also draw the door approach area.","svc_default":"Saved.","loading":"Loading the overview. If this message stays: add the \"Home\" entry of Radar Occupancy.","title":"Position in the home","light_automation":"Light automation","light_automation_aria":"Radar light automation","active":"Active","inactive":"Inactive","light_control":"Light control","mode_distance":"Distance rule","mode_map":"Map · people","select_room":"Select room","detected":"Detected","no_target":"No live target","hold_aria":"{room}: hold occupancy","hold_on":"Hold: on","hold_off":"Hold: off","no_map":"No room has a map yet (configure a room → map).","legend_target":"Radar target","legend_approach":"Door approach area","legend_door":"Door or exit (dashed: no radar behind it)","legend_fov":"Field of view of the selected sensor","calibration":"Calibration & areas","ready":"ready","place_sensor":"Place sensor","orient_active":"Orienting","orient_sensor":"Orient sensor","sample_active":"Choosing location","add_sample":"Add calibration point","fix_boundary":"Correct room outline","draw_boundary":"Draw room outline","fix_approach":"Correct door approach area","exit_tap":"Tap the exit","mark_exit":"Mark exit","door_tap":"Tap the door","mark_door":"Mark door","end_edit":"Stop editing","more_actions":"More actions","undo_sample":"Remove last calibration point","clear_orientation":"Remove orientation","clear_exits":"Remove exits ({n})","clear_doors":"Remove doors ({n})","reset_sensor":"Recalibrate sensor","refresh_maps":"Reload maps","transitions":"Light transitions","fade_summary":"{in} s on · {out} s off","fade_in":"Fade in","fade_out":"Fade out","seconds_aria":"{label} in seconds","fade_note":"In front of the door a part of the target brightness (configure the home), in the room the room's target brightness. 0 s: switch at once.","help":"Help","help1":"Zoom with two fingers, move a zoomed map with one. \"↻ 180°\" turns a map. Tap a room name or tile to select its sensor.","help2":"Calibrate: place the sensor and turn its field of view until your dot appears where you stand. Ceiling sensors: stand alone at three spread-out locations instead, each time \"Add calibration point\", mark your location and take the point. A fourth point checks the result.","help3":"On a robot map, room outlines and door approach areas come from the map; correct them under \"Calibration & areas\". On a floor plan, draw the outline of every room and mark its doors.","help4":"Mark exit: stairs or the front door, where people leave the home. Whoever vanishes there has left. Map rooms without a radar count as outside.","help5":"Map · people: people are counted through the doors. A room is free when everybody has walked out; people sitting still stay counted. A light switched off by hand in an occupied room stays off, also after leaving briefly. Switching it on by hand or 30 min without anyone hand it back to the automation.","help6":"Press a room tile or its hold button for about a second to release a held occupancy once (count to 0). The next live target detects the room again. \"Hold: off\" ends the occupancy as soon as no live target is left; \"Hold: on\" keeps it through radar dropouts.","help7":"The mode buttons switch between counting people on the map and the distance rule per room (door range as distance from the sensor). Rooms without a reliable calibration always use the distance rule. Light automation off pauses both; the position view stays active. Radar targets carry no identity; with several people all targets are shown.","msg_place":"Mark the sensor's mounting position on the map.","msg_sample":"Mark your location on the map, then press \"Take calibration point here\".","msg_boundary":"Room outline: tap the corners on the map.","msg_approach":"Door approach area: tap the corners in front of the door.","msg_exit":"Exit: tap where people leave the home (stairs, front door).","msg_door":"Door: choose the room behind it below the map, then tap the door.","confirm_exits":"Remove all exits of this room?","confirm_doors":"Remove all doors marked for this room?","msg_orient":"Turn the field of view with the buttons below the map.","confirm_orientation":"Remove the orientation? The calibration points apply again.","confirm_reset":"Delete all calibration points and the outline of this sensor?","status_offline":"Offline","status_calibrate":"Calibrate","free":"Free","one_person":"1 person","people":"{n} people","manual_off":"light off by hand","held":"Occupancy held","status_ready":"Ready","setup_running":"{room}: calibration in progress","setup_samples":"{n} calibration points · at least 3 locations needed.","warn_distorted":"The calibration is strongly distorted. Positions of this room are unreliable, so its occupancy uses the distance rule. Remedy: \"Place sensor\" and \"Orient sensor\".","source_orientation":"Transform from location and heading ({heading}°{mirrored}){error}.","mirrored_comma":", mirrored","orientation_error":" · {cm} cm from the calibration points","setup_done":"{room}: calibration complete","samples_saved":"{n} calibration points saved","deviation":" · {cm} cm deviation","outline_map":"Room outline taken from the map.","outline_manual":"Room outline drawn by hand.","outline_missing":"Room outline not available yet.","approach_set":"Door approach area set.","approach_missing":"Door approach area missing.","exits_one":"One exit marked.","exits_n":"{n} exits marked.","doors_n":"{n} doors marked.","sub_area_ref":"Sub-area reference stored separately.","occupancy_line":"Occupancy: {state}{reason}. The room only becomes free when everybody evidently walked out through a door.","occupied":"occupied","free_lower":"free","outside":"outside","reason_moved":"{from} → {to}","reason_came_in":"came in from outside","reason_went_out":"went outside","reason_seen_in_room":"seen in the room","reason_appeared_at_door":"appeared at the door to {from}","reason_released":"released","reason_hold_off":"no target (hold off)","reason_present":"present","reason_held":"held","reason_in_area":"in sub-area","reason_left_through_door":"left through the door","reason_handed_over":"handed over","reason_safety_timeout":"safety timeout","reason_live":"live presence only","reason_unavailable":"sensor offline","reason_empty":"empty","baseline_warn":"The first two radar calibration points are only {cm} cm apart. Remove the last point and go about 1 m further for the second location.","nearest":"Current radar distance to the nearest stored point: {cm} cm. Tap your actual location once you stand there.","need_one_target":"Exactly one live radar target is needed to measure. Move slightly.","map_unavailable":"Map not available.","map_loading":"Loading the map.","refresh_hint":" If it does not appear, use \"Reload maps\".","select_aria":"Select {name}","sensor_title":"{room} · sensor","door_title":"Door {a} – {b}","orient_title":"{room} · field of view","mounting":"Mounting","wall":"Wall","ceiling":"Ceiling","height_down":"Lower the mounting height","height_up":"Raise the mounting height","height":"{h} m high","ceiling_help":"Ceiling mounting: the ellipse shows the coverage on the floor (±{fov}° along +X, ±{pitch}° across), the dashed one at chest height. Turn until +X matches the mounting. The sensor cannot tell front from back across +X, so positions keep coming from the calibration points.","wall_help":"The fan shows what the sensor sees (±{fov}°, {range} m). Turn it until it matches the mounting. Check: standing in the room, your dot must appear where you stand. If it is mirrored, use \"Swap left/right\".","rotate_ccw":"{d} degrees counter-clockwise","rotate_cw":"{d} degrees clockwise","mirror":"Swap left/right","use_direction":"Use this direction","done":"Done","saved_ceiling":"Saved. The ellipse is for checking; positions keep coming from the calibration points.","saved_wall":"Saved. Positions follow location and heading.","saving":"Saving …","estimate":"Suggestion from the calibration points, not saved yet.","suggestion":"Suggestion: towards the room centre, not saved yet.","sample_title":"{room} · calibration point","sample_help":"Mark your location and stay there until the point is taken.","take_sample":"Take calibration point here","cancel":"Cancel","reset_this":"Recalibrate this sensor","marked":"Location marked.","tap_location":"Tap your location on the map.","place_title":"{room} · place sensor","place_help":"Tap the mounting position. The calibration points are kept.","place_here":"Place sensor here","approach_name":"Door approach area","outline_name":"Room outline","corners":"{n} corners","save":"Save","undo_corner":"Remove last corner","exit_title":"{room} · mark exit","exit_help":"Tap where people leave the home. Saved immediately.","door_edit_title":"{room} · mark door","door_help":"Choose the room behind the door, then tap the door on the map. Saved immediately.","door_to":"Room behind the door","flip_aria":"Turn map by 180°","zoom_out":"Zoom out","zoom_in":"Zoom in","overview":"Whole map","all":"All","no_coords":"Map coordinates missing; reload maps.","use_selected_map":"Please use the map of the selected sensor.","coords_missing":"Map coordinates missing. Please reload maps.","sensor_marked":"Sensor position marked – now save.","location_marked":"Location marked – now take the point.","card_description":"Floor maps, people per room and radar sensor calibration."},"de":{"zone_inside":"Im Raum","zone_approach":"Vor dem Raum","zone_outside":"Außerhalb","zone_lost":"Ziel verloren","zone_unreliable":"Umrechnung prüfen","zone_uncalibrated":"Noch nicht eingemessen","zone_unavailable":"Sensor offline","image_failed":"Kartenbild konnte nicht geladen werden: ","target_present":"{room}: Frisches Radarziel vorhanden.","released_msg":"{room}: Gehaltene Belegung gelöst.","placed":"Sensor platziert. Jetzt den Blickfächer drehen, bis er zur Montage passt.","heading_saved":"{room}: Blickrichtung {heading}° gespeichert{mirrored}.","mirrored_suffix":" (gespiegelt)","heading_follow":" Die Positionen folgen jetzt Standort und Winkel.","svc_sample":"Messpunkt gespeichert. Der Einmessfortschritt wird oben angezeigt.","svc_undo_sample":"Letzter Messpunkt entfernt. Gehe für den neuen Punkt möglichst 1 m vom verbleibenden Standort weg.","svc_set_exit":"Ausgang gespeichert. Wer dort verschwindet, hat die Wohnung verlassen.","svc_set_door":"Tür gespeichert. Personen werden durch sie gezählt.","svc_set_boundary":"Grenze gespeichert. Für frühes Einblenden auch den Türvorbereich einzeichnen.","svc_default":"Gespeichert.","loading":"Lagebild wird geladen. Falls diese Meldung bleibt: Radar Occupancy mit „Wohnung“ einrichten.","title":"Position im Haus","light_automation":"Lichtautomatik","light_automation_aria":"Radar-Lichtautomatik","active":"Aktiv","inactive":"Inaktiv","light_control":"Lichtsteuerung","mode_distance":"Entfernungsregel","mode_map":"Karte · Personen","select_room":"Raum auswählen","detected":"Erkannt","no_target":"Kein frisches Ziel","hold_aria":"{room}: Belegung halten","hold_on":"Halten: an","hold_off":"Halten: aus","no_map":"Noch keinem Raum ist eine Karte zugeordnet (Raum konfigurieren → Karte).","legend_target":"Radarziel","legend_approach":"Türvorbereich","legend_door":"Tür oder Ausgang (gestrichelt: dahinter misst kein Radar)","legend_fov":"Sichtfeld des gewählten Sensors","calibration":"Einmessen & Bereiche","ready":"bereit","place_sensor":"Sensor platzieren","orient_active":"Ausrichten aktiv","orient_sensor":"Sensor ausrichten","sample_active":"Standortwahl aktiv","add_sample":"Messpunkt hinzufügen","fix_boundary":"Raumgrenze korrigieren","draw_boundary":"Raumgrenze zeichnen","fix_approach":"Türvorbereich korrigieren","exit_tap":"Ausgang antippen","mark_exit":"Ausgang markieren","door_tap":"Tür antippen","mark_door":"Tür markieren","end_edit":"Bearbeitung beenden","more_actions":"Weitere Aktionen","undo_sample":"Letzten Messpunkt entfernen","clear_orientation":"Ausrichtung entfernen","clear_exits":"Ausgänge entfernen ({n})","clear_doors":"Türen entfernen ({n})","reset_sensor":"Sensor neu einmessen","refresh_maps":"Karten neu laden","transitions":"Lichtübergänge","fade_summary":"{in} s ein · {out} s aus","fade_in":"Einblenden","fade_out":"Ausblenden","seconds_aria":"{label} in Sekunden","fade_note":"Vor der Tür ein Teil der Zielhelligkeit (Wohnung konfigurieren), im Raum die Zielhelligkeit des Raums. 0 s: sofort schalten.","help":"Bedienhilfe","help1":"Mit zwei Fingern zoomen, vergrößerte Karten mit einem verschieben. „↻ 180°“ dreht eine Karte. Raumname oder Raumkachel antippen, um einen Sensor auszuwählen.","help2":"Einmessen: Sensor platzieren und den Blickfächer drehen, bis dein Punkt dort erscheint, wo du stehst. Deckensensoren stattdessen: allein an drei verteilten Standorten stehen, jeweils „Messpunkt hinzufügen“, Position markieren und aufnehmen. Ein vierter Punkt prüft das Ergebnis.","help3":"Auf einer Roboterkarte kommen Raumgrenzen und Türvorbereiche aus der Karte; unter „Einmessen & Bereiche“ lassen sie sich korrigieren. Auf einem Grundriss für jeden Raum die Grenze zeichnen und seine Türen markieren.","help4":"Ausgang markieren: Treppe oder Wohnungstür, wo man die Wohnung verlässt. Wer dort verschwindet, ist gegangen. Kartenräume ohne Radar gelten als draußen.","help5":"Karte · Personen: Personen werden über die Türen gezählt. Ein Raum ist frei, wenn alle hinausgegangen sind; still Sitzende bleiben gezählt. Licht, das im belegten Raum von Hand ausgeschaltet wurde, bleibt aus, auch nach kurzem Verlassen. Von Hand einschalten oder 30 min ohne Person geben es an die Automatik zurück.","help6":"Raumkachel oder Halten-Knopf etwa eine Sekunde gedrückt halten, um eine gehaltene Belegung einmalig zu lösen (Zähler auf 0). Beim nächsten frischen Radarziel wird der Raum wieder erkannt. „Halten: aus“ beendet die Belegung, sobald kein frisches Radarziel mehr da ist; „Halten: an“ behält sie bei Aussetzern bei.","help7":"Die Modusknöpfe wechseln zwischen Personenzählung auf der Karte und der Entfernungsregel je Raum (Türbereich als Entfernung zum Sensor). Räume ohne verlässliche Einmessung nutzen immer die Entfernungsregel. Lichtautomatik aus pausiert beide; die Positionsanzeige bleibt aktiv. Radarziele haben keine Personenidentität; bei mehreren Personen werden alle Ziele angezeigt.","msg_place":"Montageposition des Sensors auf der Karte markieren.","msg_sample":"Standort auf der Karte markieren, dann „Messpunkt hier aufnehmen“ drücken.","msg_boundary":"Raumgrenze: Ecken auf der Karte antippen.","msg_approach":"Türvorbereich: Ecken vor der Tür antippen.","msg_exit":"Ausgang: die Stelle antippen, an der man die Wohnung verlässt (Treppe, Wohnungstür).","msg_door":"Tür: unter der Karte den Raum dahinter wählen, dann die Tür antippen.","confirm_exits":"Alle Ausgänge dieses Raums entfernen?","confirm_doors":"Alle für diesen Raum markierten Türen entfernen?","msg_orient":"Blickfächer mit den Drehknöpfen unter der Karte ausrichten.","confirm_orientation":"Ausrichtung entfernen? Danach gilt wieder die Umrechnung aus den Messpunkten.","confirm_reset":"Alle Messpunkte und die Raumgrenze dieses Sensors löschen?","status_offline":"Offline","status_calibrate":"Einmessen","free":"Frei","one_person":"1 Person","people":"{n} Personen","manual_off":"Licht manuell aus","held":"Belegung gehalten","status_ready":"Bereit","setup_running":"{room}: Einmessen läuft","setup_samples":"{n} Messpunkte · mindestens 3 Standorte nötig.","warn_distorted":"Die Umrechnung ist stark verzerrt. Positionen dieses Raums sind unzuverlässig; die Belegung nutzt deshalb die Entfernungsregel. Abhilfe: „Sensor platzieren“ und „Sensor ausrichten“.","source_orientation":"Umrechnung aus Standort und Blickrichtung ({heading}°{mirrored}){error}.","mirrored_comma":", gespiegelt","orientation_error":" · {cm} cm Abstand zu den Messpunkten","setup_done":"{room}: Einmessen abgeschlossen","samples_saved":"{n} Messpunkte gespeichert","deviation":" · {cm} cm Abweichung","outline_map":"Raumgrenze automatisch aus der Karte.","outline_manual":"Raumgrenze manuell gespeichert.","outline_missing":"Raumgrenze noch nicht verfügbar.","approach_set":"Türvorbereich eingerichtet.","approach_missing":"Türvorbereich fehlt.","exits_one":"Ein Ausgang markiert.","exits_n":"{n} Ausgänge markiert.","doors_n":"{n} Türen markiert.","sub_area_ref":"Teilbereich-Referenz separat gespeichert.","occupancy_line":"Belegung: {state}{reason}. Frei wird der Raum nur, wenn alle nachweislich durch eine Tür hinausgegangen sind.","occupied":"belegt","free_lower":"frei","outside":"draußen","reason_moved":"{from} → {to}","reason_came_in":"von draußen gekommen","reason_went_out":"nach draußen gegangen","reason_seen_in_room":"im Raum gesehen","reason_appeared_at_door":"an der Tür zu {from} aufgetaucht","reason_released":"freigegeben","reason_hold_off":"kein Ziel (Halten aus)","reason_present":"anwesend","reason_held":"gehalten","reason_in_area":"im Teilbereich","reason_left_through_door":"durch die Tür gegangen","reason_handed_over":"übergeben","reason_safety_timeout":"Sicherheitsabschaltung","reason_live":"nur Live-Anwesenheit","reason_unavailable":"Sensor offline","reason_empty":"leer","baseline_warn":"Die ersten beiden Radar-Messpunkte liegen nur {cm} cm auseinander. Entferne den letzten Messpunkt und gehe für den zweiten Standort möglichst 1 m weit.","nearest":"Aktueller Radar-Abstand zum nächsten gespeicherten Punkt: {cm} cm. Tippe deinen tatsächlichen Standort an, sobald du dort stehst.","need_one_target":"Zum Messen muss genau ein frisches Radarziel sichtbar sein. Bewege dich leicht.","map_unavailable":"Karte nicht verfügbar.","map_loading":"Karte wird geladen.","refresh_hint":" Falls sie nicht erscheint, „Karten neu laden“ verwenden.","select_aria":"{name} auswählen","sensor_title":"{room} · Sensor","door_title":"Tür {a} – {b}","orient_title":"{room} · Blickfeld ausrichten","mounting":"Montageart","wall":"Wand","ceiling":"Decke","height_down":"Montagehöhe verringern","height_up":"Montagehöhe erhöhen","height":"{h} m hoch","ceiling_help":"Deckenmontage: Die Ellipse zeigt die Erfassung am Boden (±{fov}° entlang +X, ±{pitch}° quer), die gestrichelte auf Oberkörperhöhe. Drehen, bis +X zur Einbaulage passt. Vorne und hinten quer zu +X kann der Sensor nicht unterscheiden; Positionen kommen deshalb weiter aus den Messpunkten.","wall_help":"Der Fächer zeigt, was der Sensor sieht (±{fov}°, {range} m). Drehen, bis er zur Montage passt. Prüfen: Stehst du im Raum, muss dein Punkt an deinem Standort erscheinen. Liegt er seitenverkehrt, „Links/Rechts tauschen“.","rotate_ccw":"{d} Grad gegen den Uhrzeigersinn","rotate_cw":"{d} Grad im Uhrzeigersinn","mirror":"Links/Rechts tauschen","use_direction":"Diese Richtung übernehmen","done":"Fertig","saved_ceiling":"Gespeichert. Die Ellipse dient der Kontrolle; Positionen kommen weiter aus den Messpunkten.","saved_wall":"Gespeichert. Positionen folgen Standort und Blickrichtung.","saving":"Wird gespeichert …","estimate":"Vorschlag aus den Messpunkten, noch nicht gespeichert.","suggestion":"Vorschlag: Richtung Raummitte, noch nicht gespeichert.","sample_title":"{room} · Messpunkt","sample_help":"Deinen Standort markieren und bis zur Aufnahme dort stehen bleiben.","take_sample":"Messpunkt hier aufnehmen","cancel":"Abbrechen","reset_this":"Diesen Sensor neu einmessen","marked":"Standort markiert.","tap_location":"Standort auf der Karte antippen.","place_title":"{room} · Sensor platzieren","place_help":"Montageposition antippen. Die Messpunkte bleiben erhalten.","place_here":"Sensor hier platzieren","approach_name":"Türvorbereich","outline_name":"Raumgrenze","corners":"{n} Ecken","save":"Speichern","undo_corner":"Letzte Ecke entfernen","exit_title":"{room} · Ausgang markieren","exit_help":"Die Stelle antippen, an der man die Wohnung verlässt. Wird sofort gespeichert.","door_edit_title":"{room} · Tür markieren","door_help":"Den Raum hinter der Tür wählen, dann die Tür auf der Karte antippen. Wird sofort gespeichert.","door_to":"Raum hinter der Tür","flip_aria":"Karte um 180° drehen","zoom_out":"Karte verkleinern","zoom_in":"Karte vergrößern","overview":"Gesamtansicht","all":"Gesamt","no_coords":"Kartenkoordinaten fehlen; Karten neu laden.","use_selected_map":"Bitte die Karte des ausgewählten Sensors verwenden.","coords_missing":"Kartenkoordinaten fehlen. Bitte Karten neu laden.","sensor_marked":"Sensorposition markiert – jetzt speichern.","location_marked":"Standort markiert – jetzt aufnehmen.","card_description":"Karten je Stockwerk, Personen je Raum und Einmessen der Radarsensoren."}};
function tr(lang,key,vars={}) {
  const text=I18N[lang]?.[key]??I18N.en[key]??key;
  return text.replace(/\{(\w+)\}/g,(match,name)=>vars[name]??'');
}
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
// Radar Y is the viewing direction; unmirrored, radar X points right (like geometry.rigid).
function rigid(location,heading,mirrored) {
  const r=heading*Math.PI/180,m=mirrored?-1:1;
  return [[1000*m*Math.sin(r),1000*Math.cos(r),location[0]],[-1000*m*Math.cos(r),1000*Math.sin(r),location[1]]];
}
const projectRadar=(t,x,y)=>[t[0][0]*x/1000+t[0][1]*y/1000+t[0][2],t[1][0]*x/1000+t[1][1]*y/1000+t[1][2]];
const FOV_DEG=60,FOV_RANGE=6000,FOV_PITCH=35;
class RadarOccupancyCard extends HTMLElement {
  constructor() { super(); this.attachShadow({mode:'open'}); this.selected=null;this.entityId=null; this.mode='view';this.pendingSample=null;this.draft=[];this.message='';this.busy=false; this.viewports={};this.images={};this.panels={calibration:false,transitions:false,help:false,maintenance:false};this.interaction=false;this.deferred=false;this.orient=null;this.orientTimer=null; }
  setConfig(config) { this.config=config||{}; }
  lang() { const l=String(this._hass?.locale?.language||this._hass?.language||'en').toLowerCase();return l.startsWith('de')?'de':'en'; }
  t(key,vars) { return tr(this.lang(),key,vars); }
  num(value) { return Number(value).toLocaleString(this._hass?.locale?.language||this._hass?.language||'en'); }
  roomName(name) { return name==='outside'?this.t('outside'):name; }
  reasonText(code,rooms) {
    if(!code)return '';
    const [from,to]=rooms||[];
    return this.t('reason_'+code,{from:this.roomName(from??''),to:this.roomName(to??'')});
  }
  static getStubConfig() { return {}; }
  getCardSize() { return 12; }
  // Overview sensor of the integration: from the card configuration or found automatically.
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
        this.message=this.t('image_failed')+(error.message||String(error));
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
    if(sensor.targets?.length){this.message=this.t('target_present',{room:sensor.room});this.render();return;}
    if(await this.service('release',{room:sensorId})){this.message=this.t('released_msg',{room:sensor.room});this.render();}
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
      this.pendingSample=null;this.mode='orient';this.orient=null;this.message=this.t('placed');this.render();
    }
  }
  orientation(sensor,info) {
    // The orientation being edited, else the suggestion from the samples, else towards the room centre.
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
      this.message=this.t('heading_saved',{room:sensor.room,heading:this.num(current.heading),mirrored:current.mirrored?this.t('mirrored_suffix'):''})+(sensor.mount==='ceiling'?'':this.t('heading_follow'));
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
    try { await this._hass.callService('radar_occupancy',name,data);this.message=['sample','undo_sample','set_exit','set_door','set_boundary'].includes(name)&&!data.clear?this.t('svc_'+name):this.t('svc_default');return true; }
    catch(error) { this.message=error.message || String(error);return false; }
    finally { this.busy=false;this.render(); }
  }
  render() {
    if(this.interaction||this.sensorSelectFocused()){this.deferred=true;return;}
    this.deferred=false;
    this.shadowRoot.querySelectorAll?.('details[data-panel]').forEach(panel=>{this.panels[panel.dataset.panel]=panel.open;});
    const state=this.stateObj();
    if (!state) { this.shadowRoot.innerHTML=`<ha-card><p style="padding:24px">${escapeHtml(this.t('loading'))}</p></ha-card>`;return; }
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
    <ha-card class="overview"><div class="heading"><h1>${escapeHtml(this.t('title'))}</h1><button class="tracking" id="tracking" role="switch" aria-label="${escapeHtml(this.t('light_automation_aria'))}" aria-checked="${tracking}" ${this.busy?'disabled':''}><span class="switch-track" aria-hidden="true"></span><span class="tracking-label">${escapeHtml(this.t('light_automation'))}</span><span>${escapeHtml(this.t(tracking?'active':'inactive'))}</span></button></div>
      <div class="control-modes" role="group" aria-label="${escapeHtml(this.t('light_control'))}"><button data-control-mode="sensor" aria-pressed="${sensorMode}">${escapeHtml(this.t('mode_distance'))}</button><button data-control-mode="map" aria-pressed="${!sensorMode}">${escapeHtml(this.t('mode_map'))}</button></div>
      <div class="selector-row"><select id="sensor" aria-label="${escapeHtml(this.t('select_room'))}">${sensors.map(s=>`<option value="${escapeHtml(s.id)}" ${s.id===this.selected?'selected':''}>${escapeHtml(s.room)}</option>`).join('')}</select><div class="live-status">${detected.length?`${escapeHtml(this.t('detected'))}: <strong>${escapeHtml(detected.join(', '))}</strong>`:`<span class="muted">${escapeHtml(this.t('no_target'))}</span>`}</div></div>
      <div class="status">${sensors.map(s=>`<div class="room-tile ${s.id===this.selected?'selected':''}"><button class="room-button ${escapeHtml(s.zone)}" data-select-sensor="${escapeHtml(s.id)}" aria-pressed="${s.id===this.selected}"><strong>${escapeHtml(s.room)}</strong><span>${escapeHtml(this.roomStatus(s))}</span></button><button class="hold-button" data-toggle-hold="${escapeHtml(s.id)}" role="switch" aria-label="${escapeHtml(this.t('hold_aria',{room:s.room}))}" aria-checked="${s.hold_enabled!==false}">${escapeHtml(this.t(s.hold_enabled!==false?'hold_on':'hold_off'))}</button></div>`).join('')}</div>
      ${this.message?`<div class="notice" role="status">${escapeHtml(this.message)}</div>`:''}
    </ha-card>
    <div class="floors">${Object.keys(data.floors||{}).map(floor=>this.floor(floor,data)).join('')||`<ha-card><p>${escapeHtml(this.t('no_map'))}</p></ha-card>`}</div>
    <div class="legend muted"><span><i class="dot"></i>${escapeHtml(this.t('legend_target'))}</span><span><i class="door-key"></i>${escapeHtml(this.t('legend_approach'))}</span><span><i class="dot" style="background:white;border:2px solid #b76c13"></i>${escapeHtml(this.t('legend_door'))}</span><span><i class="door-key" style="border-color:#7a3fc4;background:#7a3fc420"></i>${escapeHtml(this.t('legend_fov'))}</span></div>
    <ha-card><details data-panel="calibration" ${open('calibration')}><summary>${escapeHtml(this.t('calibration'))}<span class="summary-note">${escapeHtml(current?.room||'')}${current?.calibrated?' · '+escapeHtml(this.t('ready')):''}</span></summary><div class="section-body">
      ${this.setupSummary(current)}
      <div class="toolbar"><button id="place-sensor" ${this.busy?'disabled':''}>${escapeHtml(this.t('place_sensor'))}</button><button id="orient-sensor" ${!current?.sensor_location||this.busy?'disabled':''}>${escapeHtml(this.t(this.mode==='orient'?'orient_active':'orient_sensor'))}</button><button id="sample" ${this.busy?'disabled':''}>${escapeHtml(this.t(this.mode==='sample'?'sample_active':'add_sample'))}</button><button id="boundary" ${!current?.calibrated||this.busy?'disabled':''}>${escapeHtml(this.t(current?.polygon?.length?'fix_boundary':'draw_boundary'))}</button><button id="approach" ${!current?.calibrated||this.busy?'disabled':''}>${escapeHtml(this.t('fix_approach'))}</button><button id="door" ${!current?.calibrated||this.busy?'disabled':''}>${escapeHtml(this.t(this.mode==='door'?'door_tap':'mark_door'))}</button><button id="exit" ${!current?.calibrated||this.busy?'disabled':''}>${escapeHtml(this.t(this.mode==='exit'?'exit_tap':'mark_exit'))}</button><button id="view">${escapeHtml(this.t('end_edit'))}</button></div>
      ${this.mode==='sample'?this.calibrationHint(current):''}
      <details class="maintenance" data-panel="maintenance" ${open('maintenance')}><summary>${escapeHtml(this.t('more_actions'))}</summary><div class="toolbar"><button id="undo-sample" ${!current?.samples||this.busy?'disabled':''}>${escapeHtml(this.t('undo_sample'))}</button>${current?.heading!=null?`<button id="clear-orientation" ${this.busy?'disabled':''}>${escapeHtml(this.t('clear_orientation'))}</button>`:''}${current?.exits?.length?`<button id="clear-exits" ${this.busy?'disabled':''}>${escapeHtml(this.t('clear_exits',{n:current.exits.length}))}</button>`:''}${current?.doors?.length?`<button id="clear-doors" ${this.busy?'disabled':''}>${escapeHtml(this.t('clear_doors',{n:current.doors.length}))}</button>`:''}<button id="reset" class="danger" ${this.busy?'disabled':''}>${escapeHtml(this.t('reset_sensor'))}</button><button id="refresh" ${this.busy?'disabled':''}>${escapeHtml(this.t('refresh_maps'))}</button></div></details>
    </div></details></ha-card>
    <ha-card><details data-panel="transitions" ${open('transitions')}><summary>${escapeHtml(this.t('transitions'))}<span class="summary-note">${escapeHtml(this.t('fade_summary',{in:data.fade_in,out:data.fade_out}))}</span></summary><div class="section-body"><div class="controls">${['fade_in','fade_out'].map((key,i)=>`<label>${escapeHtml(this.t(key))} · ${escapeHtml(data[key])} s<input aria-label="${escapeHtml(this.t('seconds_aria',{label:this.t(key)}))}" type="range" min="0" max="10" step="0.5" value="${escapeHtml(data[key]??0)}" data-setting="${escapeHtml(data.entities?.[key]||'')}"></label>`).join('')}</div><p class="muted">${escapeHtml(this.t('fade_note'))}</p></div></details></ha-card>
    <ha-card><details class="help" data-panel="help" ${open('help')}><summary>${escapeHtml(this.t('help'))}</summary><div class="section-body">${[1,2,3,4,5,6,7].map(i=>`<p>${escapeHtml(this.t('help'+i))}</p>`).join('')}</div></details></ha-card>`;
    const root=this.shadowRoot;
    root.getElementById('tracking').onclick=()=>this.switchEntity(data.entities?.light_automation,!tracking);
    root.querySelectorAll('[data-control-mode]').forEach(button=>button.onclick=()=>this.setControlMode(button.dataset.controlMode==='sensor'));
    this.bindSensorSelect(root.getElementById('sensor'));
    root.querySelectorAll('[data-toggle-hold]').forEach(button=>this.bindRoomButton(button,()=>this.toggleHold(button.dataset.toggleHold)));
    root.getElementById('place-sensor').onclick=()=>{this.mode='sensor';this.pendingSample=null;this.draft=[];this.message=this.t('msg_place');this.render();};
    root.querySelectorAll('[data-save-location]').forEach(button=>button.onclick=()=>this.saveSensorLocation());
    root.querySelectorAll('[data-select-sensor]').forEach(button=>this.bindRoomButton(button));
    root.querySelectorAll('details[data-panel]').forEach(panel=>panel.ontoggle=()=>{if(panel.isConnected)this.panels[panel.dataset.panel]=panel.open;});
    root.getElementById('sample').onclick=()=>{this.mode='sample';this.draft=[];this.pendingSample=null;this.message=this.t('msg_sample');this.render();};
    root.getElementById('boundary').onclick=()=>{this.mode='boundary';this.draft=[];this.message=this.t('msg_boundary');this.render();};
    root.getElementById('approach').onclick=()=>{this.mode='approach';this.draft=[];this.message=this.t('msg_approach');this.render();};
    root.getElementById('exit').onclick=()=>{this.mode='exit';this.draft=[];this.pendingSample=null;this.message=this.t('msg_exit');this.render();};
    root.getElementById('door').onclick=()=>{this.mode='door';this.draft=[];this.pendingSample=null;this.message=this.t('msg_door');this.render();};
    root.querySelectorAll('[data-door-to]').forEach(select=>select.onchange=event=>{this.doorTo=event.target.value;});
    if(root.getElementById('clear-exits'))root.getElementById('clear-exits').onclick=async()=>{if(confirm(this.t('confirm_exits')))await this.service('set_exit',{room:this.selected,clear:true});};
    if(root.getElementById('clear-doors'))root.getElementById('clear-doors').onclick=async()=>{if(confirm(this.t('confirm_doors')))await this.service('set_door',{room:this.selected,clear:true});};
    root.querySelectorAll('[data-flip-floor]').forEach(button=>button.onclick=()=>this.service('set_floor',{camera:button.dataset.flipFloor,flip:button.dataset.flipped!=='true'}));
    root.getElementById('view').onclick=()=>{this.mode='view';this.draft=[];this.orient=null;this.render();};
    root.getElementById('orient-sensor').onclick=()=>{this.mode='orient';this.pendingSample=null;this.draft=[];this.message=this.t('msg_orient');this.render();};
    if(root.getElementById('clear-orientation'))root.getElementById('clear-orientation').onclick=async()=>{if(confirm(this.t('confirm_orientation'))&&await this.service('set_orientation',{room:this.selected,clear:true})){this.orient=null;this.render();}};
    root.querySelectorAll('[data-rotate]').forEach(button=>button.onclick=()=>this.rotateSensor(Number(button.dataset.rotate)));
    root.querySelectorAll('[data-mirror]').forEach(button=>button.onclick=()=>this.rotateSensor(0,true));
    root.querySelectorAll('[data-mount]').forEach(button=>button.onclick=()=>this.service('set_orientation',{room:this.selected,mount:button.dataset.mount}));
    root.querySelectorAll('[data-height]').forEach(button=>button.onclick=()=>{const s=this.data()?.sensors?.find(x=>x.id===this.selected);this.service('set_orientation',{room:this.selected,height:Math.max(1500,Math.min(5000,(s?.mount_height||2500)+Number(button.dataset.height)))});});
    root.querySelectorAll('[data-orient-save]').forEach(button=>button.onclick=()=>this.saveOrientation());
    root.getElementById('undo-sample').onclick=()=>this.service('undo_sample',{room:this.selected});
    root.getElementById('refresh').onclick=()=>this.service('refresh_maps');
    const resetSensor=async()=>{if (confirm(this.t('confirm_reset'))) {if(await this.service('reset_calibration',{room:this.selected})){this.mode='view';this.draft=[];this.pendingSample=null;this.render();}}};
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
    if(!sensor.available)return this.t('status_offline');
    if(!sensor.calibrated)return this.t('status_calibrate');
    if(sensor.map_ready&&sensor.people!=null) {
      const people=sensor.people===0?this.t('free'):sensor.people===1?this.t('one_person'):this.t('people',{n:sensor.people});
      return sensor.light_mode==='manual_off'?`${people} · ${this.t('manual_off')}`:people;
    }
    if(sensor.zone==='lost')return this.t(sensor.occupied?'held':'free');
    return I18N.en['zone_'+sensor.zone]?this.t('zone_'+sensor.zone):this.t('status_ready');
  }
  setupSummary(current) {
    if(!current)return '';
    if(!current.calibrated)return `<div class="setup"><strong>${escapeHtml(this.t('setup_running',{room:current.room}))}</strong><span>${escapeHtml(this.t('setup_samples',{n:current.samples||0}))}</span></div>`;
    const boundary=current.polygon?.length;
    const warning=current.plausible===false?`<span class="danger">${escapeHtml(this.t('warn_distorted'))}</span>`:'';
    const source=current.transform_source==='orientation'?`<span>${escapeHtml(this.t('source_orientation',{heading:this.num(current.heading),mirrored:current.mirrored?this.t('mirrored_comma'):'',error:current.orientation_error_mm!=null?this.t('orientation_error',{cm:this.num(current.orientation_error_mm/10)}):''}))}</span>`:'';
    const outline=boundary?this.t(current.boundary_source==='map'?'outline_map':'outline_manual'):this.t('outline_missing');
    const marks=[this.t(current.approach_polygons?.length?'approach_set':'approach_missing')];
    if(current.exits?.length)marks.push(current.exits.length===1?this.t('exits_one'):this.t('exits_n',{n:current.exits.length}));
    if(current.doors?.length)marks.push(this.t('doors_n',{n:current.doors.length}));
    const reason=current.occupancy_reason?` – ${this.reasonText(current.occupancy_reason,current.occupancy_reason_rooms)}`:'';
    const occupancy=current.map_ready?`<span>${escapeHtml(this.t('occupancy_line',{state:this.t(current.occupied?'occupied':'free_lower'),reason}))}</span>`:'';
    return `<div class="setup" data-setup-complete><strong>${escapeHtml(this.t('setup_done',{room:current.room}))}</strong><span>${escapeHtml(this.t('samples_saved',{n:current.samples})+(current.error_mm!=null?this.t('deviation',{cm:this.num(current.error_mm/10)}):''))}</span><span>${escapeHtml([outline,...marks].join(' '))}</span>${(current.sample_points||[]).some(s=>s.area&&s.area!=='room')?`<span>${escapeHtml(this.t('sub_area_ref'))}</span>`:''}${source}${warning}${occupancy}</div>`;
  }
  calibrationHint(current) {
    if(current?.calibrated&&this.mode!=='sample')return '';
    const points=current?.sample_points||[];
    if(!points.length)return '';
    const distances=points.slice(1).map((point,i)=>Math.hypot(...point.radar.map((v,j)=>v-points[i].radar[j])));
    const badBaseline=points.length===2&&distances[0]<300;
    const target=current.targets?.length===1?current.targets[0]:null;
    const nearest=target?Math.min(...points.map(p=>Math.hypot(...p.radar.map((v,j)=>v-target.radar[j])))):null;
    return `${badBaseline?`<div class="notice">${escapeHtml(this.t('baseline_warn',{cm:Math.round(distances[0]/10)}))}</div>`:''}${nearest!==null?`<p class="muted">${escapeHtml(this.t('nearest',{cm:Math.round(nearest/10)}))}</p>`:`<p class="muted">${escapeHtml(this.t('need_one_target'))}</p>`}`;
  }
  floor(floor,data) {
    const info=data.floors?.[floor],url=this.images[floor]?.url;
    const convert=affine(info?.calibration_points,'vacuum','map');
    const title=escapeHtml(info?.name||this._hass?.states?.[info?.camera||floor]?.attributes?.friendly_name||floor);
    if (!info?.width||!url) return `<ha-card class="floor"><h2>${title}</h2><p>${escapeHtml(this.t(info?.error&&info.error!=='loading'?'map_unavailable':'map_loading')+this.t('refresh_hint'))}</p></ha-card>`;
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
      const selectable=sensor?` data-room-sensor="${escapeHtml(sensor.id)}" role="button" tabindex="0" aria-label="${escapeHtml(this.t('select_aria',{name}))}" style="cursor:pointer"`:'';
      return `<g${selectable} transform="translate(${p[0]} ${p[1]})"><rect x="${-width/2}" y="${-height/2}" width="${width}" height="${height}" rx="${height/2}" fill="#fff" fill-opacity=".93" stroke="#718399"/><text text-anchor="middle" dominant-baseline="central" fill="#17334f" font-size="${font}">${escapeHtml(name)}</text></g>`;
    }).join('');
    const sensorMarkers=(data.sensors||[]).filter(s=>s.floor===floor&&s.sensor_location).map(s=>{
      const p=convert&&displayPoint(convert(...s.sensor_location));if(!p)return '';
      const r=info.width/70;
      return `<g data-sensor-location="${escapeHtml(s.id)}" transform="translate(${p[0]} ${p[1]})" pointer-events="none"><title>${escapeHtml(this.t('sensor_title',{room:s.room}))}</title><rect x="${-r}" y="${-r}" width="${r*2}" height="${r*2}" rx="${r/3}" fill="#29394b" stroke="white" stroke-width="2" vector-effect="non-scaling-stroke"/><circle r="${r/3}" fill="white"/></g>`;
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
        // Looking down: coverage on the floor (outer) and at chest height (inner).
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
      return `<circle data-door="${escapeHtml(d.a)}-${escapeHtml(d.b)}" cx="${p[0]}" cy="${p[1]}" r="${r}" fill="white" stroke="#b76c13" stroke-width="2" ${seen?'':'stroke-dasharray="3 2"'} vector-effect="non-scaling-stroke"><title>${escapeHtml(this.t('door_title',{a:this.roomName(d.a),b:this.roomName(d.b)}))}</title></circle>`;
    }).join('');
    const orienting=this.mode==='orient'&&selected?.floor===floor&&pose;
    const orientControls=orienting?`<div class="edit-controls" data-orient-controls><strong>${escapeHtml(this.t('orient_title',{room:selected.room}))}</strong><div class="toolbar" role="group" aria-label="${escapeHtml(this.t('mounting'))}"><button data-mount="wall" aria-pressed="${selected.mount!=='ceiling'}">${escapeHtml(this.t('wall'))}</button><button data-mount="ceiling" aria-pressed="${selected.mount==='ceiling'}">${escapeHtml(this.t('ceiling'))}</button>${selected.mount==='ceiling'?`<button data-height="-100" aria-label="${escapeHtml(this.t('height_down'))}">− 10 cm</button><span class="heading-value">${escapeHtml(this.t('height',{h:this.num((selected.mount_height||2500)/1000)}))}</span><button data-height="100" aria-label="${escapeHtml(this.t('height_up'))}">+ 10 cm</button>`:''}</div><p class="muted">${escapeHtml(selected.mount==='ceiling'?this.t('ceiling_help',{fov:FOV_DEG,pitch:FOV_PITCH}):this.t('wall_help',{fov:FOV_DEG,range:FOV_RANGE/1000}))}</p><div class="toolbar rotate">${[15,5,1].map(d=>`<button data-rotate="${d}" aria-label="${escapeHtml(this.t('rotate_ccw',{d}))}">⟲ ${d}°</button>`).join('')}<span class="heading-value">${this.num(pose.heading)}°</span>${[1,5,15].map(d=>`<button data-rotate="-${d}" aria-label="${escapeHtml(this.t('rotate_cw',{d}))}">⟳ ${d}°</button>`).join('')}</div><div class="toolbar"><button data-mirror aria-pressed="${Boolean(pose.mirrored)}">${escapeHtml(this.t('mirror'))}</button>${pose.source==='estimate'||pose.source==='room'?`<button data-orient-save>${escapeHtml(this.t('use_direction'))}</button>`:''}<button data-cancel-sample>${escapeHtml(this.t('done'))}</button></div><p class="muted">${escapeHtml(pose.source==='saved'?this.t(selected.mount==='ceiling'?'saved_ceiling':'saved_wall'):pose.source==='draft'?this.t('saving'):pose.source==='estimate'?this.t('estimate'):this.t('suggestion'))}</p></div>`:'';
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
    const measurementControls=measuring?`<div class="notice"><strong>${escapeHtml(this.t('sample_title',{room:selected.room}))}</strong><p>${escapeHtml(this.t('sample_help'))}</p>${this.calibrationHint(selected)}<div class="toolbar"><button data-save-sample ${!pending||this.busy||selected.targets?.length!==1?'disabled':''}>${escapeHtml(this.t('take_sample'))}</button><button data-cancel-sample>${escapeHtml(this.t('cancel'))}</button>${selected.samples?`<button data-undo-sample ${this.busy?'disabled':''}>${escapeHtml(this.t('undo_sample'))}</button><button data-reset-sensor ${this.busy?'disabled':''}>${escapeHtml(this.t('reset_this'))}</button>`:''}</div><p class="muted">${escapeHtml(this.t(pending?'marked':'tap_location'))}</p></div>`:'';
    const locationControls=placingSensor?`<div class="edit-controls"><strong>${escapeHtml(this.t('place_title',{room:selected.room}))}</strong><p class="muted">${escapeHtml(this.t('place_help'))}</p><div class="toolbar"><button data-save-location ${!pending||this.busy?'disabled':''}>${escapeHtml(this.t('place_here'))}</button><button data-cancel-sample>${escapeHtml(this.t('cancel'))}</button></div></div>`:'';
    const boundaryControls=['boundary','approach'].includes(this.mode)&&selected?.floor===floor?`<div class="edit-controls"><strong>${escapeHtml(selected.room)} · ${escapeHtml(this.t(this.mode==='approach'?'approach_name':'outline_name'))}</strong><div class="toolbar"><span>${escapeHtml(this.t('corners',{n:this.draft.length}))}</span><button id="save" ${this.draft.length<3||this.busy?'disabled':''}>${escapeHtml(this.t('save'))}</button><button id="undo">${escapeHtml(this.t('undo_corner'))}</button><button data-cancel-sample>${escapeHtml(this.t('cancel'))}</button></div></div>`:'';
    const view=this.view(floor);
    const rotation=info.flip?`rotate(180 ${info.width/2} ${info.height/2})`:'';
    const exitHint=this.mode==='exit'&&selected?.floor===floor?`<div class="edit-controls"><strong>${escapeHtml(this.t('exit_title',{room:selected.room}))}</strong><p class="muted">${escapeHtml(this.t('exit_help'))}</p><div class="toolbar"><button data-cancel-sample>${escapeHtml(this.t('done'))}</button></div></div>`:'';
    const doorChoices=(data.sensors||[]).filter(s=>s.floor===floor&&s.id!==selected?.id).map(s=>[s.id,s.room]).concat([['outside',this.t('outside')]]);
    if(this.mode==='door'&&!doorChoices.some(([id])=>id===this.doorTo))this.doorTo=doorChoices[0]?.[0];
    const doorHint=this.mode==='door'&&selected?.floor===floor?`<div class="edit-controls"><strong>${escapeHtml(this.t('door_edit_title',{room:selected.room}))}</strong><p class="muted">${escapeHtml(this.t('door_help'))}</p><div class="toolbar"><label>${escapeHtml(this.t('door_to'))} <select data-door-to>${doorChoices.map(([id,name])=>`<option value="${escapeHtml(id)}" ${id===this.doorTo?'selected':''}>${escapeHtml(name)}</option>`).join('')}</select></label><button data-cancel-sample>${escapeHtml(this.t('done'))}</button></div></div>`:'';
    return `<ha-card class="floor"><div class="floor-head"><h2>${title}</h2><div class="zoom-tools"><button data-flip-floor="${escapeHtml(floor)}" data-flipped="${Boolean(info.flip)}" aria-label="${escapeHtml(this.t('flip_aria'))}">↻ 180°</button><button data-zoom-floor="${floor}" data-zoom-action="out" aria-label="${escapeHtml(this.t('zoom_out'))}">−</button><span data-zoom-label="${floor}">${Math.round(view.scale*100)} %</span><button data-zoom-floor="${floor}" data-zoom-action="in" aria-label="${escapeHtml(this.t('zoom_in'))}">+</button><button data-zoom-floor="${floor}" data-zoom-action="reset" aria-label="${escapeHtml(this.t('overview'))}">${escapeHtml(this.t('all'))}</button></div></div><div class="map"><svg data-floor="${floor}" viewBox="0 0 ${info.width} ${info.height}" xmlns="http://www.w3.org/2000/svg"><g data-zoom-space transform="translate(${view.x} ${view.y}) scale(${view.scale})"><g data-map-space transform="${rotation}"><image href="${escapeHtml(url)}" width="${info.width}" height="${info.height}"/>${polygons}${approach}${fov}${doors}${draft}${targets}</g>${roomLabels}${fovLabel}${targetLabels}${sampleMarkers}${sensorMarkers}${marker}</g></svg></div>${measurementControls}${locationControls}${orientControls}${boundaryControls}${exitHint}${doorHint}${!convert?`<p class="muted">${escapeHtml(this.t('no_coords'))}</p>`:''}</ha-card>`;
  }
  async mapClick(event,svg,current,data) {
    if(this.mode==='view'||this.busy)return;
    const floor=svg.dataset.floor;
    if(current?.floor!==floor){this.message=this.t('use_selected_map');this.render();return;}
    const convert=affine(data.floors[floor]?.calibration_points,'map','vacuum');
    if(!convert){this.message=this.t('coords_missing');this.render();return;}
    const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;
    const p=point.matrixTransform(svg.querySelector('[data-map-space]').getScreenCTM().inverse());const coords=convert(p.x,p.y);
    if(this.mode==='exit'){await this.service('set_exit',{room:this.selected,x:Math.round(coords[0]),y:Math.round(coords[1])});return;}
    if(this.mode==='door'){if(this.doorTo)await this.service('set_door',{room:this.selected,to:this.doorTo,x:Math.round(coords[0]),y:Math.round(coords[1])});return;}
    if(['sample','sensor'].includes(this.mode)){this.pendingSample=coords;this.message=this.t(this.mode==='sensor'?'sensor_marked':'location_marked');this.render();}
    else {this.draft.push(coords);this.render();}
  }
}
// Resources and extra_module_url can load the same module. An extension loaded
// later can replace window.customElements with a registry polyfill in which
// earlier cards are unknown ("configuration error"). So register every card
// again with its own subclass for as long as it is missing.
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
  if(!window.customCards.some(c=>c.type==='radar-occupancy-card'))window.customCards.push({type:'radar-occupancy-card',name:'Radar Occupancy',description:tr(String(globalThis.navigator?.language||'en').toLowerCase().startsWith('de')?'de':'en','card_description')});
}
if(typeof setInterval==='function') {
  let checks=0;
  const timer=setInterval(()=>{registerRadarCards();if(++checks>=120)clearInterval(timer);},250);
}
