"""Simulierte Uhr für die Sensoren -- zur Laufzeit über den Bus steürbar.

Die Sensoren fragen nicht die echte Systemzeit ab, sondern simclock.now().
Damit laesst sich die Tageszeit für Demonstrationen manipulieren, ohne zu warten.

Steuerung über das retained Topic home/_control/clock (Nutzlast als Text):

  * "real"   -> echte Systemzeit (Standard)
  * "HH:MM"  -> Uhrzeit einfrieren (z. B. "18:30")
  * "x<f>"   -> Zeitraffer: f simulierte Sekunden pro echter Sekunde
               (z. B. "x600" -> ein ganzer Tag in ~2,4 Minuten)

Startwert optional aus der Umgebungsvariable CLOCK.
"""
import os
import time
from datetime import datetime, timedelta

_mode = "real"            # real | fixed | fast
_fixed = (0, 0)           # (Stunde, Minute) im fixed-Modus
_factor = 1.0             # Beschleunigung im fast-Modus
_t0_real = 0.0            # echte Startzeit (epoch) des fast-Modus
_sim0 = None              # simulierter Startzeitpunkt (Mitternacht)


def set_clock(spec: str | None) -> None:
    global _mode, _fixed, _factor, _t0_real, _sim0
    spec = (spec or "").strip().lower()
    if not spec or spec == "real":
        _mode = "real"
        return
    if spec.startswith("x"):
        try:
            factor = float(spec[1:])
        except ValueError:
            return
        _mode = "fast"
        _factor = max(1.0, factor)
        _t0_real = time.time()
        _sim0 = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        return
    if ":" in spec:
        try:
            h, m = (int(x) for x in spec.split(":"))
        except ValueError:
            return
        _mode = "fixed"
        _fixed = (h % 24, m % 60)


def now() -> datetime:
    if _mode == "fixed":
        return datetime.now().replace(hour=_fixed[0], minute=_fixed[1], second=0, microsecond=0)
    if _mode == "fast" and _sim0 is not None:
        elapsed = (time.time() - _t0_real) * _factor
        return _sim0 + timedelta(seconds=elapsed % 86400)
    return datetime.now()


def describe() -> str:
    if _mode == "fixed":
        return f"fix {_fixed[0]:02d}:{_fixed[1]:02d}"
    if _mode == "fast":
        return f"Zeitraffer x{_factor:g}"
    return "Echtzeit"


# Startwert aus der Umgebung übernehmen.
set_clock(os.environ.get("CLOCK"))
