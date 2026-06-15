import math
import random
from datetime import datetime


def _hour(now: datetime | None = None) -> float:
    now = now or datetime.now()
    return now.hour + now.minute / 60.0


def temperature(now: datetime | None = None) -> float:
    h = _hour(now)
    base = 21.5 + 2.5 * math.sin((h - 9) / 24 * 2 * math.pi)
    return round(base + random.gauss(0, 0.15), 2)


def is_occupied(now: datetime | None = None) -> bool:
    h = _hour(now)
    return (6 <= h < 9) or (17 <= h < 23)


def ultrasonic_distance(now: datetime | None = None) -> float:
    if is_occupied(now):
        return round(max(2.0, random.gauss(70, 25)), 1)
    return round(min(400.0, random.gauss(280, 30)), 1)
