"""Simulierter Ultraschall-Abstandssensor HC-SR04 (constrained node).

Raum und ID konfigurierbar ueber AREA / DEVICE_ID. Misst die Distanz in cm;
daraus leitet die Regel-Engine Anwesenheit ab. Bezug zur Vorlesung:
HC-SR04 / Ultraschall-Abstandsmessung am Mikrocontroller.
"""
import os

from common.contract import Device
from common import profiles


def main() -> None:
    area = os.environ.get("AREA", "living_room")
    did = os.environ.get("DEVICE_ID", f"ultra-{area}-01")
    dev = Device(
        device_id=did,
        device_type="ultrasonic",
        area=area,
        device_class="constrained",
        capabilities=["distance", "presence"],
    )

    def work() -> None:
        dev.publish_telemetry("distance", profiles.ultrasonic_distance(), "centimeter")

    dev.run_forever(interval=3, work=work)


if __name__ == "__main__":
    main()
