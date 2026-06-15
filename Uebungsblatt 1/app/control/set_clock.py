"""Kleines Kommando ("Button"), um die simulierte Uhr zur Laufzeit zu setzen.

Veroeffentlicht den Uhr-Befehl retained auf home/_control/clock. Alle Sensoren
sind darauf abonniert und verwenden ab sofort die simulierte Zeit.

Beispiele (im laufenden Stack):
    docker compose exec rule-engine python -m control.set_clock 18:30   # einfrieren
    docker compose exec rule-engine python -m control.set_clock x600     # Zeitraffer
    docker compose exec rule-engine python -m control.set_clock real     # Echtzeit
"""
import sys
import time

import paho.mqtt.client as mqtt
from paho.mqtt.client import CallbackAPIVersion

from common.contract import CLOCK_TOPIC, MQTT_HOST, MQTT_PORT


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("Verwendung: python -m control.set_clock <real | HH:MM | x<faktor>>")
        return 2
    spec = argv[0]
    client = mqtt.Client(client_id="clock-setter",
                         callback_api_version=CallbackAPIVersion.VERSION2)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=10)
    client.loop_start()
    client.publish(CLOCK_TOPIC, spec, qos=1, retain=True)
    time.sleep(0.5)
    client.loop_stop()
    client.disconnect()
    print(f"Uhr gesetzt: '{spec}' (retained auf {CLOCK_TOPIC})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
