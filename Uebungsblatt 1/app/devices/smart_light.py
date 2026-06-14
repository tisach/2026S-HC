"""Simulierter Aktor: schaltbare Lampe.

Raum und ID konfigurierbar ueber AREA / DEVICE_ID. Abonniert sein
Kommando-Topic und meldet seinen Zustand zurueck (retained). Reagiert nur auf
Nachrichten -- weiss nichts ueber die Regel-Engine.
"""
import os

from common.contract import Device


class SmartLight(Device):
    def __init__(self, device_id: str, area: str) -> None:
        super().__init__(
            device_id=device_id,
            device_type="light",
            area=area,
            device_class="edge",
            capabilities=["on_off", "brightness"],
            is_actuator=True,
        )
        self.power = False
        self.brightness = 0

    def on_ready(self) -> None:
        self.publish_state({"power": self.power, "brightness": self.brightness})

    def on_command(self, topic: str, data: dict) -> None:
        cmd = data.get("command")
        params = data.get("params", {})
        if cmd == "set_power":
            self.power = bool(params.get("on", False))
            self.brightness = 80 if self.power else 0
        elif cmd == "set_brightness":
            self.brightness = max(0, min(100, int(params.get("level", 0))))
            self.power = self.brightness > 0
        else:
            self.log.warning("unbekanntes Kommando: %s", cmd)
            return
        self.log.info("Kommando '%s' -> power=%s brightness=%s",
                      cmd, self.power, self.brightness)
        self.publish_state({"power": self.power, "brightness": self.brightness})


def main() -> None:
    area = os.environ.get("AREA", "living_room")
    did = os.environ.get("DEVICE_ID", f"light-{area}-01")
    SmartLight(did, area).run_forever()


if __name__ == "__main__":
    main()
