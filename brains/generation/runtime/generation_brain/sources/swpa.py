"""Southwestern Power Administration daily generation schedule (www.energy.gov/swpa/<mon..sun>.htm): projected MEGAWATTS per hour per project.

The page is fixed-width text: a header row starting "HR" lists the project columns, then 24 "hour ending" rows (row 14 = 1 PM to 2 PM,
US Central time). SWPA publishes megawatts, not unit counts and not discharge: each window carries `generationMw` with `unitsOn` absent.
The old Engine derived units and cfs from plant capacity; the Brain does not (owner rule: real measured or official operator data only).

The page is keyed by weekday, so last week's page sits at the same URL until SWPA replaces it. A page is used only when it states the
schedule date (MM/DD/YYYY or "Month D, YYYY") and that date is the day asked for; otherwise it is refused. Access: source_access.json
lists SWPA as ACCESS_CHECK_REQUIRED, so the runtime refuses it until a release records the robots.txt / terms check."""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from ..contract import iso
from . import Reading, failed

AGENCY = "Southwestern Power Administration"
BASE = "https://www.energy.gov/swpa"
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MONTHS = {m: i for i, m in enumerate(("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
                                       "november", "december"), start=1)}


def central(d: date) -> timezone:
    """US Central with the DST rule in force since 2007 (second Sunday of March to first Sunday of November)."""
    def nth_sunday(y, m, n):
        first = date(y, m, 1)
        return first + timedelta(days=(6 - first.weekday()) % 7 + 7 * (n - 1))
    dst = nth_sunday(d.year, 3, 2) <= d < nth_sunday(d.year, 11, 1)
    return timezone(timedelta(hours=-5 if dst else -6), "CDT" if dst else "CST")


def text_of(html: str) -> str:
    s = re.sub(r"(?is)<(script|style)\b.*?</\1>", "", html)
    s = re.sub(r"<[^>]+>", "", s)
    return s.replace("&nbsp;", " ").replace("&amp;", "&")


def stated_dates(text: str) -> set[date]:
    out = set()
    for m, d, y in re.findall(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text):
        try:
            out.add(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    for mon, d, y in re.findall(r"(?i)\b(" + "|".join(MONTHS) + r")\s+(\d{1,2}),\s*(\d{4})\b", text):
        try:
            out.add(date(int(y), MONTHS[mon.lower()], int(d)))
        except ValueError:
            pass
    return out


def parse_grid(text: str) -> dict[str, list[int]] | None:
    lines = text.splitlines()
    head = next((i for i, l in enumerate(lines) if l.strip().startswith("HR ")), None)
    if head is None:
        return None
    cols = lines[head].split()[1:]
    if not cols:
        return None
    grid = {c: [] for c in cols}
    for line in lines[head + 1:]:
        parts = line.split()
        if parts and parts[0].upper() in ("TOT", "TOTAL"):
            break
        if len(parts) != len(cols) + 1 or not parts[0].isdigit() or not 1 <= int(parts[0]) <= 24:
            continue
        if any(not p.lstrip("-").isdigit() for p in parts[1:]):
            continue
        for c, v in zip(cols, parts[1:]):
            grid[c].append(int(v))
        if len(grid[cols[0]]) == 24:
            break
    return grid if all(len(v) == 24 for v in grid.values()) else None


def windows(hourly_mw: list[int], d: date) -> list[dict]:
    """Contiguous hours of equal megawatts -> windows. Row h (hour ending) is [h-1, h) local."""
    tz = central(d)
    mid = datetime(d.year, d.month, d.day, tzinfo=tz)
    out, start = [], 0
    for h in range(1, 25):
        if h == 24 or hourly_mw[h] != hourly_mw[start]:
            out.append({"start": iso(mid + timedelta(hours=start)), "end": iso(mid + timedelta(hours=h)), "generationMw": float(hourly_mw[start]),
                        "statedBy": "operator", "unitsStated": False})
            start = h
    return out


def read(binding: dict, fetcher, now: datetime) -> Reading:
    d = now.astimezone(central(now.date())).date()
    page = DAYS[d.weekday()]
    series = [f"swpa:{page}.htm:{binding['project']}"]
    r = fetcher.get("swpa", f"{BASE}/{page}.htm", accept="text/html")
    if not r.ok:
        return failed("swpa", AGENCY, f"SWPA {page}.htm: {r.error}", series)
    text = text_of(r.body.decode("utf-8", errors="replace"))
    if d not in stated_dates(text):
        return failed("swpa", AGENCY, f"SWPA {page}.htm does not state {d.isoformat()} (an old page is never used)", series)
    grid = parse_grid(text)
    if grid is None:
        return failed("swpa", AGENCY, f"SWPA {page}.htm: the hourly grid is not complete (24 rows)", series)
    mw = grid.get(binding["project"])
    if mw is None:
        return failed("swpa", AGENCY, f"SWPA {page}.htm has no column {binding['project']}", series)
    return Reading("swpa", AGENCY, True, None, [], windows(mw, d), series, cadence_min=1440, lag_min=0)
