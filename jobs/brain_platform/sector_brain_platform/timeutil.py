from __future__ import annotations

import datetime as dt


def iso(t: dt.datetime | None) -> str | None:
    if t is None:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_time(s: str | None) -> dt.datetime | None:
    if not s or not isinstance(s, str):
        return None
    try:
        t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def age_hours(at: str | None, now: dt.datetime) -> float | None:
    t = parse_time(at)
    return None if t is None else round((now - t).total_seconds() / 3600, 2)
