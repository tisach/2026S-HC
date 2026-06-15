"""Kleines Kommando ("Button"), um das aktive Szenario zur Laufzeit zu wechseln.

Veroeffentlicht den Szenario-Namen retained auf home/_control/scenario. Alle
Sensoren sind darauf abonniert und spielen ab sofort das gewaehlte Profil ab.

Beispiele (im laufenden Stack):
    docker compose exec rule-engine python -m control.set_scenario urlaub
    docker compose exec rule-engine python -m control.set_scenario besuch
    docker compose exec rule-engine python -m control.set_scenario day_profile
    docker compose exec rule-engine python -m control.set_scenario ""   # zurueck zur Formel
"""
import sys
import time

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

from common.contract import CONTROL_TOPIC, MQTT_HOST, MQTT_PORT
from common import sensing


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(f"Verwendung: python -m control.set_scenario <name|''>")
        print(f"Verfuegbare Profile: {', '.join(sensing.available())}")
        return 2
    name = argv[0]
    if name and name not in sensing.available():
        print(f"Warnung: '{name}' ist kein bekanntes Profil "
              f"({', '.join(sensing.available())}) -- Sensoren fallen ggf. auf die Formel zurueck.")
    client = mqtt.Client(client_id="scenario-setter",
                         callback_api_version=CallbackAPIVersion.VERSION2)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=10)
    client.loop_start()
    client.publish(CONTROL_TOPIC, name, qos=1, retain=True)
    time.sleep(0.5)  # Zustellung abwarten
    client.loop_stop()
    client.disconnect()
    print(f"Szenario gesetzt: '{name or '(Formel)'}' (retained auf {CONTROL_TOPIC})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
