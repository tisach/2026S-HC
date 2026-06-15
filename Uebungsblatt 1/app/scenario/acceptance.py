"""Anwendungsfall / Akzeptanztest

Dieser Client hängt sich als externer Teilnehmer an den laufenden Bus und prüft
jede geforderte Eigenschaft aktiv

  Verteilung      Mehrere unabhängige Komponenten publizieren bereits auf dem Bus.
  Heterogenitaet  Sie melden verschiedene device_class- und device_type-Werte.
  Erweiterbarkeit Ein komplett neuer Raum "office" wird nur über den Bus
                  eingeschleust und von Registry/Regel-Engine ohne Codeänderung
                  übernommen (Discovery).
  Lose Kopplung   Die Regel-Engine steuert dieses neue Gerät, das sie nie zuvor
                  gesehen hat über Topics, ohne direkten Aufruf.
  Robustheit      Fehlerhafte Nachrichten (Nicht-JSON, schema-ungueltig) bringen
                  das System nicht aus dem Tritt (die Regelschleife läuft weiter)
  Fehlertoleranz  Ein "ausgefallener" Aktor blockiert die Engine nicht; Kommandos
                  werden weiter emittiert (Fehler bleibt isoliert).
  Skalierbarkeit  Viele zusaetzliche Geräte werden registriert; das System
                  arbeitet unverändert weiter.

Start (während `docker compose up` läuft):
    docker compose run --rm scenario
"""
import json
import time

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

from common.contract import (announce_topic, availability_topic, command_topic,
                             connect_with_retry, now_iso, state_topic,
                             telemetry_topic)
import logging

logging.getLogger().setLevel(logging.WARNING)  # nur unsere Ausgabe, kein Rauschen

OFFICE = "office"
SENSOR_ID = "ultra-office-vt"
LIGHT_ID = "light-office-vt"


class Scenario:
    def __init__(self) -> None:
        self.client = mqtt.Client(client_id="scenario-runner",
                                  callback_api_version=CallbackAPIVersion.VERSION2)
        self.client.on_connect = lambda c, u, f, rc, p=None: c.subscribe("home/#", qos=1)
        self.client.on_message = self._on_message
        self.inventory: dict[str, dict] = {}
        self.commands: dict[str, dict | None] = {}
        self.light_alive = True
        self.results: list[tuple[str, bool, str]] = []

    # --- Bus-Callbacks ------------------------------------------------------
    def _on_message(self, client, userdata, msg):
        try:
            parts = msg.topic.split("/")
            if msg.topic.startswith("home/_registry/announce/"):
                reg = json.loads(msg.payload.decode())
                self.inventory[reg["device_id"]] = reg
            elif parts[-1] == "command" and len(parts) == 5:
                did = parts[3]
                params = json.loads(msg.payload.decode()).get("params", {})
                self.commands[did] = params
                # die virtuelle Lampe quittiert wie ein echtes Geraet
                if did == LIGHT_ID and self.light_alive:
                    self._state(OFFICE, "light", LIGHT_ID,
                                {"power": bool(params.get("on")), "brightness": 80 if params.get("on") else 0})
        except Exception:
            pass

    # --- Publish-Helfer (wir spielen Geraete des neuen Raums) ---------------
    def _announce(self, did, dtype, area, cls, caps):
        payload = {"device_id": did, "device_type": dtype, "area": area,
                   "device_class": cls, "capabilities": caps,
                   "schema_version": 1, "ts": now_iso()}
        self.client.publish(announce_topic(did), json.dumps(payload), qos=1, retain=True)

    def _telemetry(self, area, dtype, did, metric, value, unit):
        payload = {"device_id": did, "device_type": dtype, "metric": metric,
                   "value": value, "unit": unit, "ts": now_iso()}
        self.client.publish(telemetry_topic(area, dtype, did), json.dumps(payload), qos=1)

    def _state(self, area, dtype, did, state):
        payload = {"device_id": did, "device_type": dtype, "state": state, "ts": now_iso()}
        self.client.publish(state_topic(area, dtype, did), json.dumps(payload), qos=1, retain=True)

    def _availability(self, area, dtype, did, value):
        self.client.publish(availability_topic(area, dtype, did), value, qos=1, retain=True)

    def _raw(self, topic, payload):
        self.client.publish(topic, payload, qos=1)

    # --- Hilfsfunktionen ----------------------------------------------------
    @staticmethod
    def _wait(pred, timeout=8.0, interval=0.1) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if pred():
                return True
            time.sleep(interval)
        return False

    def _clear(self, did):
        self.commands[did] = None

    def _make_present(self) -> bool:
        """Erzwingt deterministisch ein 'set_power on:true' fuer die Office-Lampe."""
        self._telemetry(OFFICE, "ultrasonic", SENSOR_ID, "distance", 300.0, "centimeter")
        time.sleep(0.4)
        self._clear(LIGHT_ID)
        self._telemetry(OFFICE, "ultrasonic", SENSOR_ID, "distance", 40.0, "centimeter")
        return self._wait(lambda: (self.commands.get(LIGHT_ID) or {}).get("on") is True)

    def _make_absent(self) -> bool:
        self._telemetry(OFFICE, "ultrasonic", SENSOR_ID, "distance", 40.0, "centimeter")
        time.sleep(0.4)
        self._clear(LIGHT_ID)
        self._telemetry(OFFICE, "ultrasonic", SENSOR_ID, "distance", 300.0, "centimeter")
        return self._wait(lambda: (self.commands.get(LIGHT_ID) or {}).get("on") is False)

    def _check(self, name, passed, detail=""):
        self.results.append((name, passed, detail))
        print(f"  [{'PASS' if passed else 'FAIL'}]  {name}")
        if detail:
            print(f"         {detail}")

    # --- Ablauf -------------------------------------------------------------
    def run(self) -> int:
        connect_with_retry(self.client, logging.getLogger("scenario"))
        self.client.loop_start()

        print("\n=== Anwendungsfall: 'Ein Abend zieht ins Haus ein' ===\n")

        # Phase 0 -- warten, bis die bestehende (verteilte) Basis online ist
        ready = self._wait(lambda: len([d for d in self.inventory if not d.endswith("-vt")]) >= 6,
                           timeout=25)
        base = {d: r for d, r in self.inventory.items() if not d.endswith("-vt")}
        if not ready:
            print("  ! Hinweis: weniger als 6 Basisgeraete sichtbar -- laeuft `docker compose up`?\n")

        # 1) Verteilung
        areas = sorted({r["area"] for r in base.values()})
        self._check("Verteilung: mehrere unabhaengige Komponenten am Bus",
                    len(base) >= 6 and len(areas) >= 2,
                    f"{len(base)} Geraete in Raeumen {areas}")

        # 2) Heterogenitaet
        classes = sorted({r["device_class"] for r in base.values()})
        types = sorted({r["device_type"] for r in base.values()})
        self._check("Heterogenitaet: verschiedene Geraeteklassen und -typen",
                    len(classes) >= 2 and len(types) >= 2,
                    f"klassen={classes}, typen={types}")

        # 3) Erweiterbarkeit + lose Kopplung: neuen Raum 'office' einschleusen
        self._announce(LIGHT_ID, "light", OFFICE, "edge", ["on_off", "brightness"])
        self._announce(SENSOR_ID, "ultrasonic", OFFICE, "constrained", ["distance", "presence"])
        self._availability(OFFICE, "light", LIGHT_ID, "online")
        time.sleep(2.0)  # der Regel-Engine Zeit zum Lernen geben
        on_ok = self._make_present()
        off_ok = self._make_absent()
        self._check("Erweiterbarkeit + Discovery: neuer Raum ohne Codeaenderung",
                    on_ok,
                    "die unveraenderte Regel-Engine hat die neue Lampe entdeckt und geschaltet")
        self._check("Lose Kopplung: Engine steuert ein nie zuvor gesehenes Geraet",
                    on_ok and off_ok,
                    "set_power on/off nur ueber Topics, ohne direkten Aufruf")

        # 4) Robustheit: fehlerhafte Nachrichten einspeisen, dann erneut schalten
        self._raw(telemetry_topic(OFFICE, "ultrasonic", SENSOR_ID), "{kaputt: nicht-json")
        self._raw(telemetry_topic(OFFICE, "temperature", "temp-office-vt"),
                  json.dumps({"device_id": "x", "device_type": "temperature",
                              "metric": "temperature", "value": "warm",  # ungueltig: kein number
                              "unit": "celsius", "ts": now_iso()}))
        time.sleep(0.5)
        still_alive = self._make_present()
        self._check("Robustheit: System verarbeitet Fehlnachrichten ohne Ausfall",
                    still_alive,
                    "nach Nicht-JSON und schema-ungueltiger Telemetrie laeuft die Regelschleife weiter")

        # 5) Fehlertoleranz: Aktor 'faellt aus' -- Engine darf nicht blockieren
        self.light_alive = False
        self._availability(OFFICE, "light", LIGHT_ID, "offline")
        isolated = self._make_present()  # Kommando muss trotzdem emittiert werden
        self._check("Fehlertoleranz: Ausfall eines Aktors bleibt isoliert",
                    isolated,
                    "Engine emittiert Kommandos weiter, obwohl die Lampe offline ist")
        self.light_alive = True
        self._availability(OFFICE, "light", LIGHT_ID, "online")

        # 6) Skalierbarkeit: viele Geraete registrieren, System bleibt funktionsfaehig
        before = len(self.inventory)
        for i in range(15):
            did = f"scale-{i:02d}-vt"
            self._announce(did, "ultrasonic", f"room{i % 5}", "constrained", ["distance"])
            self._telemetry(f"room{i % 5}", "ultrasonic", did, "distance", 250.0, "centimeter")
        grew = self._wait(lambda: len(self.inventory) >= before + 15, timeout=10)
        sane = self._make_absent() and self._make_present()
        self._check("Skalierbarkeit: +15 Geraete, System weiter funktionsfaehig",
                    grew and sane,
                    f"Inventar {before} -> {len(self.inventory)}; Regelschleife weiterhin gruen")

        # Zusammenfassung
        passed = sum(1 for _, ok, _ in self.results if ok)
        total = len(self.results)
        print(f"\n=== Ergebnis: {passed}/{total} Anforderungen erfuellt ===")
        print("    Hinweis: Echte Prozess-/Container-Fehlertoleranz zusaetzlich live zeigen via")
        print("    `docker compose stop bedroom-light` (Kachel wird offline) und wieder `start`.\n")

        self.client.loop_stop()
        self.client.disconnect()
        return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(Scenario().run())
