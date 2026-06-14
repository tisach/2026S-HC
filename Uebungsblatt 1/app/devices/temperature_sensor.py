"""Simulierter Temperatursensor (constrained node, vgl. Cortex-M).

Raum und ID kommen aus Umgebungsvariablen (AREA, DEVICE_ID). Dieselbe Datei
erzeugt damit beliebig viele Instanzen in beliebig vielen Raeumen, ohne dass
sich der Code aendert -- das demonstriert Skalierbarkeit und Erweiterbarkeit.
"""
import os

from common.contract import Device
from common import profiles


def main() -> None:
    area = os.environ.get("AREA", "living_room")
    did = os.environ.get("DEVICE_ID", f"temp-{area}-01")
    dev = Device(
        device_id=did,
        device_type="temperature",
        area=area,
        device_class="constrained",
        capabilities=["temperature"],
    )

    def work() -> None:
        dev.publish_telemetry("temperature", profiles.temperature(), "celsius")

    dev.run_forever(interval=5, work=work)


if __name__ == "__main__":
    main()
