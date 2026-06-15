"""Device-Registry (Discovery & Inventar).

Hoert auf retained Announcements und Availability-Nachrichten und fuehrt ein
Live-Inventar aller Geraete. Demonstriert Discovery, Heterogenitaet
(device_class) und Fehlertoleranz (online/offline ueber Last-Will).
"""
import json
import logging
import threading
import time

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

from common.contract import PREFIX, connect_with_retry


class Registry:
    def __init__(self) -> None:
        self.log = logging.getLogger("registry")
        self.devices: dict[str, dict] = {}
        self.availability: dict[str, str] = {}
        self.client = mqtt.Client(client_id="registry",
                                  callback_api_version=CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.log.info("verbunden")
        client.subscribe(f"{PREFIX}/_registry/announce/#", qos=1)
        client.subscribe(f"{PREFIX}/+/+/+/availability", qos=1)

    def _on_message(self, client, userdata, msg):
        try:
            parts = msg.topic.split("/")
            payload = msg.payload.decode()

            if msg.topic.startswith(f"{PREFIX}/_registry/announce/"):
                reg = json.loads(payload)
                # nur vollstaendige Registrierungen aufnehmen (Robustheit)
                if not all(k in reg for k in
                           ("device_id", "device_type", "device_class", "capabilities")):
                    self.log.warning("verwerfe unvollstaendige Registrierung auf %s", msg.topic)
                    return
                self.devices[reg["device_id"]] = reg
                self.log.info("registriert: %s (typ=%s, klasse=%s, faehigkeiten=%s)",
                              reg["device_id"], reg["device_type"],
                              reg["device_class"], reg["capabilities"])
            elif parts[-1] == "availability" and len(parts) == 5:
                self.availability[parts[3]] = payload
                self.log.info("Verfuegbarkeit %s -> %s", parts[3], payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.log.warning("verwerfe Nicht-JSON-Nachricht auf %s", msg.topic)
        except Exception as exc:
            self.log.warning("uebergehe fehlerhafte Nachricht auf %s (%s)", msg.topic, exc)

    def _inventory_loop(self) -> None:
        while True:
            time.sleep(15)
            self.log.info("---- Inventar (%d Geraete) ----", len(self.devices))
            for did, reg in sorted(self.devices.items()):
                self.log.info("  %-16s typ=%-12s klasse=%-11s status=%s",
                              did, reg["device_type"], reg["device_class"],
                              self.availability.get(did, "unbekannt"))

    def run(self) -> None:
        connect_with_retry(self.client, self.log)
        threading.Thread(target=self._inventory_loop, daemon=True).start()
        self.client.loop_forever()


if __name__ == "__main__":
    Registry().run()
