# Deutsch

Raumbelegung aus mmWave-Radarsensoren (z. B. HLK-LD2450), die **das Licht
nicht ausschaltet, wenn jemand still sitzt**, und es so früh einschaltet, wie
die Sensoren es erlauben.

## Die Idee

Ein Raum wird durch Radar-Anwesenheit belegt und nur durch einen Nachweis
wieder frei: Das Ziel verschwand im **Türbereich**, ein anderer Raum hat die
Person **übernommen** (nur Einpersonenhaushalt), die **Sicherheitsabschaltung**
griff, oder jemand hat **freigegeben**. Verschwindet das Ziel woanders, etwa am
Schreibtisch, bleibt der Raum belegt. **Teilbereiche** (z. B. ein Balkon, den
der Raumsensor mit sieht) zählen nie als Verlassen und können ein eigenes
Licht schalten.

## Einrichten

1. Über HACS installieren: *Benutzerdefinierte Repositories* →
   `https://github.com/ChristophBellmann/ha-radar-occupancy`, Kategorie
   *Integration*; danach Home Assistant neu starten.
2. *Integration hinzufügen → Radar Occupancy → Raum*, das Radar-Gerät wählen;
   Anwesenheit, Entfernung und X/Y werden vorgeschlagen, der Name kommt aus
   dem Bereich des Geräts. Licht wählen.
3. **Türbereich einmessen:** normal durch die Tür hinausgehen, danach
   **Türbereich vom letzten Verlassen lernen** drücken. Der Bereich beginnt
   dann 50 cm vor der Stelle, an der das Radar dich verloren hat.
4. Bei Besuch den Schalter **Übergabe zwischen Räumen** der Wohnung
   ausschalten.

## Kartenmodus

Optional, mit dem Eintrag „Wohnung“: Radarziele auf einer Karte, Personen je
Raum über Türen gezählt, mehrpersonentauglich. Ein Raum wird erst frei, wenn
alle nachweislich durch eine Tür gegangen sind. Als Karte dient die
gespeicherte Karte eines Saugroboters (dreame_vacuum) oder ein **Grundriss**
als Bild (Eintrag „Grundriss“: PNG/JPEG im Ordner `www` plus die echte Breite
des Bildes in Metern). Eingemessen wird in der Positionskarte
`custom:radar-occupancy-card`: Sensor platzieren und ausrichten, auf
Grundrissen Raumgrenzen zeichnen und Türen und Ausgänge markieren.

## Licht

- Einschalten beim Betreten, Ausschalten nach der Nachlaufzeit, wenn alle
  gegangen sind; „Nur bei Dunkelheit“ und Zeitfenster.
- Weiches Ein- und Ausblenden in wahrnehmungsgleichen Schritten.
- **Vorlicht** beim Zugehen auf eine Tür (30 %); **volles Licht schon vor
  dem Betreten**, wenn das Radar des Zielraums die Person bereits durch die
  Tür kommen sieht (z. B. Bad mit Blick in den Flur), und hinter Türen, hinter
  die kein Sensor sieht.
- **Von Hand aus bleibt aus**, egal ob per Schalter, App, Sprachbefehl oder
  LLM: auch beim Umdrehen im Bett und nach kurzem Verlassen. Die Sperre endet
  mit „Licht an“, nach 30 min Leerstand, wenn jemand nachweislich gegangen
  ist, oder beim Heimkommen.

## Simulation

In der Positionskarte unter **Simulation** laufen bis zu acht simulierte
Personen über die Karte, auf Wunsch mit den echten Lampen (**Echte Lichter
steuern**; Stoppen stellt die vorherigen Zustände wieder her). Die simulierten
Radare melden wie echte nur im eigenen Sichtfeld und Raum und etwa einmal pro
Sekunde. `radar_occupancy.measure_simulation` misst, wie viele Sekunden nach
dem Betreten eines Raums das Licht beschlossen wird.

Einrichtung, Entitäten und Positionskarte sind auf Deutsch und Englisch. Die
ausführliche Dokumentation auf den übrigen Seiten ist englisch.
