"""
Das Startszenario kommt aus der Umgebungsvariable SCENARIO. Zur Laufzeit kann es
über den Bus gewechselt werden (Topic home/_control/scenario): set_scenario()
wird dann aufgerufen und alle Sensoren spielen ab sofort das neue Profil ab.
Ist kein Profil aktiv oder die Datei fehlt, fallen die Sensoren auf die Formeln
in profiles.py zurück. Die Geräteschnittstelle bleibt unverändert.
"""
import json
import os
import random
from datetime import datetime
from pathlib import Path

from common import profiles
from common import simclock

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_current: str | None = (os.environ.get("SCENARIO") or "").strip() or None
_cache: dict[str, dict | None] = {}


def set_scenario(name: str | None) -> None:
    #Aktives Szenario wechseln (z. B. ueber das Control-Topic)
    global _current
    _current = (name or "").strip() or None


def current() -> str | None:
    return _current


def available() -> list[str]:
    return sorted(p.stem for p in _DATA_DIR.glob("*.json"))


def _profile() -> dict | None:
    name = _current
    if not name:
        return None
    if name not in _cache:
        try:
            _cache[name] = json.loads((_DATA_DIR / f"{name}.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _cache[name] = None
    return _cache[name]


def _segment(area: str, now: datetime) -> dict | None:
    prof = _profile()
    if not prof:
        return None
    segs = prof.get("areas", {}).get(area)
    if not segs:
        return None
    minutes_now = now.hour * 60 + now.minute
    chosen = segs[-1]  # Umlauf: vor dem ersten 'from' gilt das letzte Segment des Vortags
    for seg in segs:
        h, m = map(int, seg["from"].split(":"))
        if h * 60 + m <= minutes_now:
            chosen = seg
    return chosen


def temperature(area: str, now: datetime | None = None) -> float:
    now = now or simclock.now()
    seg = _segment(area, now)
    if seg is None:
        return profiles.temperature(now)  # Fallback Formel
    return round(seg["temp"] + random.gauss(0, 0.15), 2)


def distance(area: str, now: datetime | None = None) -> float:
    #HC-SR04: 2..400 cm. Anwesenheit -> jemand nah; sonst -> Raum leer
    now = now or simclock.now()
    seg = _segment(area, now)
    if seg is None:
        return profiles.ultrasonic_distance(now)  # Fallback Formel
    if seg.get("presence"):
        return round(max(2.0, random.gauss(70, 25)), 1)
    return round(min(400.0, random.gauss(280, 30)), 1)
