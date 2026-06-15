
import os

from common.contract import Device
from common import sensing
from common import simclock
from common.contract import CONTROL_TOPIC, CLOCK_TOPIC

# Simulierter Sensor: Ultraschallsensor (Abstandsmessung, Anwesenheitserkennung)
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

    dev.control_hooks[CONTROL_TOPIC] = sensing.set_scenario  # Szenario per Bus
    dev.control_hooks[CLOCK_TOPIC] = simclock.set_clock       # Uhr per Bus

    def work() -> None:
        dev.publish_telemetry("distance", sensing.distance(area), "centimeter")

    dev.run_forever(interval=3, work=work)


if __name__ == "__main__":
    main()
