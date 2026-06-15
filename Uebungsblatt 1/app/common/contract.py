import json
import logging
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion
from jsonschema import validate, ValidationError

# MQTT-Client-Logging (z. B. Verbindungsfehler) sichtbar machen.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-16s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)

MQTT_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", "1883"))

# Wurzel-Namespace aller Topics.
PREFIX = "home"

# Control-Topics: Szenario-Auswahl und Uhrzeit (simulierte Zeit, z. B. für Tageslicht).
CONTROL_TOPIC = f"{PREFIX}/_control/scenario"
CLOCK_TOPIC = f"{PREFIX}/_control/clock"

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"
_SCHEMA_CACHE: dict[str, dict] = {}

# Hilfsfunktion: JSON-Schema nur einmal laden und dann im Cache behalten (schneller, weniger IO).
def load_schema(name: str) -> dict:
    if name not in _SCHEMA_CACHE:
        with open(_SCHEMA_DIR / f"{name}.schema.json", encoding="utf-8") as fh:
            _SCHEMA_CACHE[name] = json.load(fh)
    return _SCHEMA_CACHE[name]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Topic-Schema 
# home/{area}/{device_type}/{device_id}/{channel}
def telemetry_topic(area: str, dtype: str, did: str) -> str:
    return f"{PREFIX}/{area}/{dtype}/{did}/telemetry"


def state_topic(area: str, dtype: str, did: str) -> str:
    return f"{PREFIX}/{area}/{dtype}/{did}/state"


def command_topic(area: str, dtype: str, did: str) -> str:
    return f"{PREFIX}/{area}/{dtype}/{did}/command"


def availability_topic(area: str, dtype: str, did: str) -> str:
    return f"{PREFIX}/{area}/{dtype}/{did}/availability"


def announce_topic(did: str) -> str:
    return f"{PREFIX}/_registry/announce/{did}"


def connect_with_retry(client: mqtt.Client, log: logging.Logger,
                       host: str = MQTT_HOST, port: int = MQTT_PORT) -> None:
    """Blockiert, bis der Broker erreichbar ist (Robustheit beim Hochfahren)."""
    while True:
        try:
            client.connect(host, port, keepalive=30)
            return
        except (socket.gaierror, ConnectionRefusedError, OSError) as exc:
            log.warning("Broker %s:%s nicht erreichbar (%s) -- neuer Versuch in 2s",
                        host, port, exc)
            time.sleep(2)

# Basisklasse für Sensoren und Aktoren.
class Device:
    """Basisklasse fuer simulierte Sensoren und Aktoren.

    Sensoren rufen run_forever(interval, work) mit einer Mess-Funktion auf.
    Aktoren setzen is_actuator=True und ueberschreiben on_command().
    """

    def __init__(self, device_id: str, device_type: str, area: str,
                 device_class: str = "edge", capabilities: list[str] | None = None,
                 is_actuator: bool = False):
        self.device_id = device_id
        self.device_type = device_type
        self.area = area
        self.device_class = device_class  # constrained | edge | cloud (Heterogenitaet)
        self.capabilities = capabilities or []
        self.is_actuator = is_actuator
        self.log = logging.getLogger(device_id)
        # topic -> callable(payload_str). Sensoren registrieren hier z. B.
        # CONTROL_TOPIC -> sensing.set_scenario und CLOCK_TOPIC -> simclock.set_clock,
        # um per Bus umschaltbar zu sein (retained -> sofort beim Verbinden aktiv).
        self.control_hooks = {}

        self.client = mqtt.Client(client_id=device_id,
                                  callback_api_version=CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        # Last Will: faellt das Geraet aus, markiert der Broker es als offline.
        self.client.will_set(self._avail(), payload="offline", qos=1, retain=True)

    # interne Topic-Helfer
    def _avail(self) -> str:
        return availability_topic(self.area, self.device_type, self.device_id)

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        self.log.info("verbunden mit Broker %s:%s", MQTT_HOST, MQTT_PORT)
        client.publish(self._avail(), "online", qos=1, retain=True)
        self._announce()
        if self.is_actuator:
            client.subscribe(command_topic(self.area, self.device_type, self.device_id), qos=1)
        for topic in self.control_hooks:
            client.subscribe(topic, qos=1)  # retained -> aktueller Wert sofort
        self.on_ready()

    def _announce(self) -> None:
        payload = {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "area": self.area,
            "device_class": self.device_class,
            "capabilities": self.capabilities,
            "schema_version": 1,
            "ts": now_iso(),
        }
        if self._valid(payload, "registration"):
            # retained: neue Dienste lernen den Geraetebestand sofort kennen.
            self.client.publish(announce_topic(self.device_id),
                                json.dumps(payload), qos=1, retain=True)

    def _valid(self, payload: dict, schema: str) -> bool:
        try:
            validate(payload, load_schema(schema))
            return True
        except ValidationError as exc:
            self.log.error("ungueltige %s-Nachricht: %s", schema, exc.message)
            return False

    def publish_telemetry(self, metric: str, value: float, unit: str) -> None:
        payload = {
            "device_id": self.device_id, "device_type": self.device_type,
            "metric": metric, "value": value, "unit": unit, "ts": now_iso(),
        }
        if self._valid(payload, "telemetry"):
            self.client.publish(
                telemetry_topic(self.area, self.device_type, self.device_id),
                json.dumps(payload), qos=1)

    def publish_state(self, state: dict) -> None:
        payload = {
            "device_id": self.device_id, "device_type": self.device_type,
            "state": state, "ts": now_iso(),
        }
        if self._valid(payload, "state"):
            self.client.publish(
                state_topic(self.area, self.device_type, self.device_id),
                json.dumps(payload), qos=1, retain=True)

    def _on_message(self, client, userdata, msg):
        # Control-Topics (Szenario, Uhr): Nutzlast ist einfacher Text.
        hook = self.control_hooks.get(msg.topic)
        if hook is not None:
            value = msg.payload.decode(errors="ignore").strip()
            hook(value)
            self.log.info("Control %s -> '%s'", msg.topic.split("/")[-1], value or "(default)")
            return
        try:
            data = json.loads(msg.payload.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.log.warning("verwerfe Nicht-JSON-Nachricht auf %s", msg.topic)
            return
        self.on_command(msg.topic, data)

    # Ueberschreibbare Hooks
    def on_ready(self) -> None:
        """Wird nach erfolgreichem Verbinden aufgerufen."""

    def on_command(self, topic: str, data: dict) -> None:
        """Aktoren reagieren hier auf Kommandos."""

    def run_forever(self, interval: float | None = None, work=None) -> None:
        connect_with_retry(self.client, self.log)
        self.client.loop_start()
        try:
            while True:
                if work is not None:
                    work()
                time.sleep(interval if interval is not None else 3600)
        except KeyboardInterrupt:
            pass
        finally:
            self.client.publish(self._avail(), "offline", qos=1, retain=True)
            self.client.loop_stop()
            self.client.disconnect()
