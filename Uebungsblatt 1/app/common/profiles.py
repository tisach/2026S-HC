"""Realistische Verhaltensprofile fuer die simulierten Sensoren.

Statt reiner Zufallswerte erzeugen diese Funktionen plausible Tagesverlaeufe
(Tag/Nacht-Temperatur, Anwesenheit am Abend). Genau hier laesst sich generative
KI andocken: Die Profile koennen durch ein LLM erzeugte Szenarien ersetzt oder
ergaenzt werden (z. B. "Arbeitstag", "Urlaub", "Party"), ohne dass sich die
Schnittstelle der Geraete aendert.
"""
import math
import random
from datetime import datetime


def _hour(now: datetime | None = None) -> float:
    now = now or datetime.now()
    return now.hour + now.minute / 60.0


def temperature(now: datetime | None = None) -> float:
    """Diurnaler Verlauf um ca. 21.5 C, Minimum morgens, Maximum nachmittags."""
    h = _hour(now)
    base = 21.5 + 2.5 * math.sin((h - 9) / 24 * 2 * math.pi)
    return round(base + random.gauss(0, 0.15), 2)


def is_occupied(now: datetime | None = None) -> bool:
    """Anwesenheit morgens (6-9 Uhr) und abends (17-23 Uhr)."""
    h = _hour(now)
    return (6 <= h < 9) or (17 <= h < 23)


def ultrasonic_distance(now: datetime | None = None) -> float:
    """HC-SR04 misst 2..400 cm. Bei Anwesenheit ist jemand nah am Sensor."""
    if is_occupied(now):
        return round(max(2.0, random.gauss(70, 25)), 1)
    return round(min(400.0, random.gauss(280, 30)), 1)
