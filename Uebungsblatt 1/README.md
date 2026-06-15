# Smart-Home-Demonstrator (Heterogeneous Computing, Übungsblatt 1b)

Prototypischer Demonstrator einer modernen Smart-Home-Infrastruktur. Mehrere
eigenständige Komponenten kommunizieren über einen MQTT-Broker. Physische
Sensoren und Aktoren werden als realistisch verhaltende Software-Mockups
simuliert; die fachliche Logik (Automatisierung, Discovery) läuft am Edge.


## Anleitung

Voraussetzung: Docker und Docker Compose.

```bash
docker compose up --build
```

Dann das **Live-Dashboard** öffnen: <http://localhost:8080>. Es zeigt jede
Gerätekachel mit aktuellem Messwert/Zustand, Online-Status und einem
Ereignis-Log. Im Container-Log sieht man parallel, wie die Sensoren Telemetrie
senden, die Registry den Gerätebestand aufbaut und die Regel-Engine bei
Anwesenheit das Licht schaltet. Stoppen mit `Ctrl+C`, aufräumen mit
`docker compose down`.

Das Dashboard ist eine statische Seite, die sich per MQTT-over-WebSockets
(Port 9001) direkt mit dem Broker verbindet — es ist damit nur ein weiterer
Subscriber am Bus, kein Sonderfall (lose Kopplung bleibt erhalten).

Einzelne Komponente lokal ausführen (Broker muss laufen):

```bash
pip install -r requirements.txt
AREA=kitchen MQTT_HOST=localhost python -m app.devices.temperature_sensor
```

Fehlertoleranz testen: einen Container stoppen
(`docker compose stop smart-light`) — die übrigen laufen weiter, die Registry
meldet das Gerät über das Last-Will als `offline`.

## Schnittstellen

Topic-Schema: `home/{area}/{device_type}/{device_id}/{channel}`

| Kanal          | Richtung            | Schema             | retained |
|----------------|---------------------|--------------------|----------|
| `telemetry`    | Sensor → Bus        | `telemetry`        | nein     |
| `command`      | Bus → Aktor         | `command`          | nein     |
| `state`        | Aktor → Bus         | `state`            | ja       |
| `availability` | Gerät → Bus (LWT)   | `online`/`offline` | ja       |
| `_registry/announce/{id}` | Gerät → Bus | `registration`  | ja       |

Die JSON-Schemas in [`app/schemas/`](app/schemas) sind der verbindliche
Vertrag; jede Nachricht wird vor dem Versand validiert.

## Anforderungen aktiv testen (Akzeptanztest)

Der Anwendungsfall „Ein Abend zieht ins Haus ein" prüft jede geforderte
Eigenschaft aktiv am laufenden System. Ein Szenario-Client schleust einen
komplett neuen Raum (`office`) nur über den Bus ein und beobachtet, ob das
**unveränderte** System korrekt reagiert. Bei laufendem Stack:

```bash
docker compose up -d
docker compose run --rm scenario
```

Geprüft werden Verteilung, Heterogenität, Erweiterbarkeit/Discovery, lose
Kopplung (die Regel-Engine steuert ein nie zuvor gesehenes Gerät), Robustheit
(fehlerhafte Nachrichten brechen nichts), Fehlertoleranz (ein „ausgefallener"
Aktor blockiert die Engine nicht) und Skalierbarkeit (+15 Geräte zur Laufzeit).
Der Test endet mit einer PASS/FAIL-Übersicht und Exit-Code 0, wenn alle
Anforderungen erfüllt sind.

Echte Prozess-Fehlertoleranz zusätzlich live zeigen: `docker compose stop
bedroom-light` — die Kachel wird offline, der Rest läuft weiter; `docker compose
start bedroom-light` holt sie zurück.

## Komponenten

| Komponente            | Rolle                  | device_class  |
|-----------------------|------------------------|---------------|
| `broker`              | MQTT-Message-Bus       | —             |
| `dashboard`           | Live-UI (WebSockets)   | edge          |
| `rule-engine`         | Automatisierung        | edge          |
| `registry`            | Discovery & Inventar   | edge          |
| `{room}-temperature`  | Sensor (Telemetrie)    | constrained   |
| `{room}-ultrasonic`   | HC-SR04 (Präsenz)      | constrained   |
| `{room}-light`        | Aktor (schaltbar)      | edge          |

Die Geräte laufen je Raum (`living_room`, `bedroom`) aus **identischem Code** —
nur die Umgebungsvariable `AREA` unterscheidet die Instanzen. Registry und
Regel-Engine arbeiten raumweise über Topic-Wildcards und bleiben dabei
unverändert: ein weiterer Raum ist ein Compose-Block, kein Code-Eingriff. Genau
das macht **Skalierbarkeit** und **Erweiterbarkeit** sichtbar; die Räume sind
voneinander isoliert (Anwesenheit im Schlafzimmer schaltet nur das
Schlafzimmerlicht).

Das Feld `device_class` (`constrained` / `edge` / `cloud`) macht die
**Heterogenität** explizit — angelehnt an die in der Vorlesung behandelten
ARM-Klassen (Cortex-M-Sensorknoten vs. leistungsfähigeres Edge-Gateway).

## Abbildung der Anforderungen

| Anforderung      | Umsetzung im Demonstrator                                              |
|------------------|-----------------------------------------------------------------------|
| Verteilung       | Jede Komponente ist ein eigener Prozess/Container                     |
| Skalierbarkeit   | Neue Geräte docken über Topics an, ohne Änderung am Kern             |
| Fehlertoleranz   | Last-Will markiert Ausfälle; Edge arbeitet ohne Cloud weiter         |
| Robustheit       | JSON-Schema-Validierung, Reconnect-Logik, Verwerfen ungültiger Daten |
| Lose Kopplung    | Pub/Sub über den Broker; Sender kennen Empfänger nicht               |
| Heterogenität    | `device_class` und unterschiedliche Fähigkeiten je Gerät             |
| Erweiterbarkeit  | Registry-Discovery; Regel-Engine lernt Aktoren zur Laufzeit          |

## Tagesprofile

Die Sensoren beziehen ihre Werte aus **vorab durch generative KI erzeugten
Tagesprofilen** ([`app/data/`](app/data)). Drei Profile liegen bei:

| Profil        | Verhalten                                                        |
|---------------|------------------------------------------------------------------|
| `day_profile` | normaler Werktag (morgens/abends zu Hause, tagsüber abwesend)    |
| `urlaub`      | niemand zu Hause, Heizung abgesenkt                              |
| `besuch`      | viele Personen, Wohnzimmer durchgehend belegt und warm          |


**Szenario zur Laufzeit umschalten.** Das aktive Profil wird über ein retained
Control-Topic (`home/_control/scenario`) gesteuert; alle Sensoren sind darauf
abonniert und wechseln sofort. Zwei Wege:

- **Dashboard-Buttons** (oben: Alltag / Urlaub / Besuch / Formel) — ein Klick
  veröffentlicht das Szenario auf den Bus.
- **CLI-Kommando** im laufenden Stack:
  ```bash
  docker compose exec rule-engine python -m control.set_scenario besuch
  ```

Das Startszenario kommt aus der Umgebungsvariable `SCENARIO` (im Compose auf
`day_profile` gesetzt). Eine leere Auswahl (`Formel`) schaltet auf die
deterministischen Formeln in [`app/common/profiles.py`](app/common/profiles.py)
zurück. Die Geräteschnittstelle bleibt in allen Fällen identisch — es wechselt
nur die Herkunft der Werte. Dass der Umschalter selbst nur eine Bus-Nachricht
ist, ist ein weiterer Beleg für die lose Kopplung.

**Simulierte Uhr (Tageszeit manipulieren).** Damit der Tagesverlauf im Vortrag
nicht in Echtzeit abläuft, lesen die Sensoren ihre Zeit aus einer simulierten Uhr
([`app/common/simclock.py`](app/common/simclock.py)), steuerbar über das retained
Topic `home/_control/clock`:

| Befehl   | Wirkung                                                        |
|----------|----------------------------------------------------------------|
| `real`   | echte Systemzeit (Standard)                                    |
| `HH:MM`  | Uhrzeit einfrieren, z. B. `18:30`                              |
| `x<f>`   | Zeitraffer: `f` simulierte Sekunden je echter Sekunde (`x600` = ein Tag in ~2,4 min) |

Bedienbar über die **Uhrzeit-Buttons** im Dashboard (Echtzeit / 07:00 / 12:00 /
18:00 / 23:00 / Zeitraffer) oder per CLI:
```bash
docker compose exec rule-engine python -m control.set_clock 18:00
docker compose exec rule-engine python -m control.set_clock x600
```
So springst du gezielt auf eine Tageszeit (z. B. 18:00 → Wohnzimmer belegt) oder
lässt im Zeitraffer einen kompletten Tag durchlaufen. Optional setzt die
Umgebungsvariable `CLOCK` einen Startwert.

