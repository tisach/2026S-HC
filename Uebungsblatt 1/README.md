# Smart-Home-Demonstrator (Heterogeneous Computing, Übungsblatt 1b)

Prototypischer Demonstrator einer modernen Smart-Home-Infrastruktur. Mehrere
eigenständige Komponenten kommunizieren über einen MQTT-Broker. Physische
Sensoren und Aktoren werden als realistisch verhaltende Software-Mockups
simuliert; die fachliche Logik (Automatisierung, Discovery) läuft am Edge.

## Architektur

Leitbild: **Message-Bus als Nervensystem** — Geräte sind voneinander entkoppelt
und reden nur über den Broker. Details und Diagramm: [`docs/architecture.md`](docs/architecture.md).

## Schnellstart

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

## Schnittstellen-Vertrag

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

## Einsatz generativer KI

Die Sensoren nutzen Verhaltensprofile (Tag/Nacht-Temperatur, Anwesenheit) statt
reiner Zufallswerte — siehe [`app/common/profiles.py`](app/common/profiles.py).
Diese Profile sind der Andockpunkt für generative KI: Ein LLM kann komplette
Szenarien („Arbeitstag", „Urlaub") oder ganze Mockup-Geräte gegen den
definierten Schnittstellen-Vertrag erzeugen, ohne dass sich die Infrastruktur
ändert.

## Hinweis zur Abgabe

Dieses Repository enthält bewusst keine personenbezogenen Daten (kein Name,
keine Matrikelnummer), damit es im Sammel-Repository `2026S-HC` veröffentlicht
werden kann.
