"""Ereignisbasierte Regel-Engine.

Abonniert Telemetrie, entdeckt Aktoren ueber die Registry-Announcements und
steuert sie ausschliesslich ueber Kommando-Topics. Sender und Empfaenger kennen
sich nicht direkt -- die Engine demonstriert lose Kopplung und Erweiterbarkeit:
ein neuer Sensor oder eine neue Lampe funktioniert ohne Codeaenderung.

Robustheit: jede eingehende Nachricht wird defensiv verarbeitet. Nicht-JSON,
schema-ungueltige oder unerwartete Nachrichten werden verworfen, ohne den Dienst
zu beeintraechtigen.
"""
import json
import logging

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from jsonschema import validate, ValidationError

from common.contract import (PREFIX, command_topic, connect_with_retry,
                             load_schema, now_iso)

PRESENCE_CM = 120.0   # naeher als 120 cm -> Anwesenheit
TEMP_WARN_C = 26.0


class RuleEngine:
    def __init__(self) -> None:
        self.log = logging.getLogger("rule-engine")
        self.lights_by_area: dict[str, list[tuple[str, str]]] = {}
        self.presence: dict[str, bool] = {}
        self.client = mqtt.Client(client_id="rule-engine",
                                  callback_api_version=CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.log.info("verbunden")
        client.subscribe(f"{PREFIX}/+/ultrasonic/+/telemetry", qos=1)
        client.subscribe(f"{PREFIX}/+/temperature/+/telemetry", qos=1)
        client.subscribe(f"{PREFIX}/_registry/announce/#", qos=1)

    def _on_message(self, client, userdata, msg):
        # 1) dekodieren -- Nicht-JSON wird verworfen, nicht weitergereicht
        try:
            data = json.loads(msg.payload.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.log.warning("verwerfe Nicht-JSON-Nachricht auf %s", msg.topic)
            return
        # 2) verarbeiten -- jeder Fehler bleibt lokal und legt den Dienst nicht lahm
        try:
            if msg.topic.startswith(f"{PREFIX}/_registry/announce/"):
                self._learn(data)
                return
            try:
                validate(data, load_schema("telemetry"))
            except ValidationError:
                self.log.warning("verwerfe ungueltige Telemetrie auf %s", msg.topic)
                return
            area = msg.topic.split("/")[1]
            metric, value = data.get("metric"), data.get("value")
            if metric == "distance":
                self._handle_presence(area, value)
            elif metric == "temperature" and value > TEMP_WARN_C:
                self.log.info("Temperatur hoch in %s: %.1f C", area, value)
        except Exception as exc:  # defensiv: unerwartete Nachrichtenform
            self.log.warning("uebergehe fehlerhafte Nachricht auf %s (%s)", msg.topic, exc)

    def _learn(self, reg: dict) -> None:
        if "on_off" in reg.get("capabilities", []):
            area = reg["area"]
            entry = (reg["device_type"], reg["device_id"])
            bucket = self.lights_by_area.setdefault(area, [])
            if entry not in bucket:
                bucket.append(entry)
                self.log.info("Aktor entdeckt: %s in %s", reg["device_id"], area)

    def _handle_presence(self, area: str, distance) -> None:
        present = distance is not None and distance < PRESENCE_CM
        if self.presence.get(area) == present:
            return  # nur bei Zustandswechsel handeln (Entprellung)
        self.presence[area] = present
        self.log.info("Anwesenheit in %s -> %s (%.0f cm)", area, present, distance)
        for dtype, did in self.lights_by_area.get(area, []):
            self._command(area, dtype, did, "set_power", {"on": present})

    def _command(self, area, dtype, did, command, params) -> None:
        payload = {"command": command, "params": params,
                   "source": "rule-engine", "ts": now_iso()}
        validate(payload, load_schema("command"))
        self.client.publish(command_topic(area, dtype, did),
                            json.dumps(payload), qos=1)

    def run(self) -> None:
        connect_with_retry(self.client, self.log)
        self.client.loop_forever()


if __name__ == "__main__":
    RuleEngine().run()
