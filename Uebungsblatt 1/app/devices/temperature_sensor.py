import os

from common.contract import Device
from common import sensing
from common import simclock
from common.contract import CONTROL_TOPIC, CLOCK_TOPIC

# Simulierter Sensor: Temperatur
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

    dev.control_hooks[CONTROL_TOPIC] = sensing.set_scenario  # Szenario per Bus
    dev.control_hooks[CLOCK_TOPIC] = simclock.set_clock       # Uhr per Bus

    def work() -> None:
        dev.publish_telemetry("temperature", sensing.temperature(area), "celsius")

    dev.run_forever(interval=5, work=work)


if __name__ == "__main__":
    main()
