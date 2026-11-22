"""Southwestern Power Administration daily generation schedule (www.energy.gov/swpa/<mon..sun>.htm): projected MEGAWATTS per hour per project.

The page is fixed-width text: a header row starting "HR" lists the project columns, then 24 "hour ending" rows (row 14 = 1 PM to 2 PM,
US Central time). SWPA publishes megawatts, not unit counts and not discharge: each window carries `generationMw` with `unitsOn` absent.
The old Engine derived units and cfs from plant capacity; the Brain does not (owner rule: real measured or official operator data only).

The page is keyed by weekday, so last week's page sits at the same URL until SWPA replaces it. A page is used only when its own date field
(the header above the grid, MM/DD/YYYY or "Month D, YYYY") states exactly the local day asked for; a date elsewhere on the page never counts.
Hours are elapsed hours after local midnight, each with its own UTC offset: a DST change day must carry 23 (spring) or 25 (fall) rows. Access: source_access.json
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


def midnight_utc(d: date) -> datetime:
    """Local midnight of `d` as a UTC instant. Midnight precedes the 02:00 switch, so it carries the PREVIOUS day's offset (on the spring and fall
    change days the offset at midnight is the one before the change)."""
    return datetime(d.year, d.month, d.day, tzinfo=central(d - timedelta(days=1))).astimezone(timezone.utc)


def hours_in_day(d: date) -> int:
    """23 on the spring change day, 25 on the fall change day, else 24."""
    return int((midnight_utc(d + timedelta(days=1)) - midnight_utc(d)).total_seconds() // 3600)


def local_date(now: datetime) -> date:
    for d in (now.date() - timedelta(days=1), now.date(), now.date() + timedelta(days=1)):
        if midnight_utc(d) <= now < midnight_utc(d + timedelta(days=1)):
            return d
    return now.date()


def header_and_grid(text: str):
    lines = text.splitlines()
    head = next((i for i, l in enumerate(lines) if l.strip().startswith("HR ")), None)
    return (("\n".join(lines[:head]), lines[head:]) if head is not None else (text, None))


def parse_grid(text: str, n_hours: int = 24) -> dict[str, list[int]] | None:
    """The hourly grid; exactly `n_hours` hour-ending rows (23 / 24 / 25 on a DST change day) or None."""
    _, lines = header_and_grid(text)
    if not lines:
        return None
    cols = lines[0].split()[1:]
    if not cols:
        return None
    grid = {c: [] for c in cols}
    for line in lines[1:]:
        parts = line.split()
        if parts and parts[0].upper() in ("TOT", "TOTAL"):
            break
        if len(parts) != len(cols) + 1 or not parts[0].isdigit() or not 1 <= int(parts[0]) <= 25:
            continue
        if any(not p.lstrip("-").isdigit() for p in parts[1:]):
            continue
        for c, v in zip(cols, parts[1:]):
            grid[c].append(int(v))
    return grid if all(len(v) == n_hours for v in grid.values()) else None


def windows(hourly_mw: list[int], d: date) -> list[dict]:
    """Contiguous hours of equal megawatts -> windows. Row i (hour ending, 1-based) is the i-th elapsed hour after local midnight, so every
    hour carries its own UTC offset (23 rows on the spring change day, 25 on the fall one)."""
    mid = midnight_utc(d)
    n = len(hourly_mw)
    out, start = [], 0
    for h in range(1, n + 1):
        if h == n or hourly_mw[h] != hourly_mw[start]:
            out.append({"start": iso(mid + timedelta(hours=start)), "end": iso(mid + timedelta(hours=h)), "generationMw": float(hourly_mw[start]),
                        "statedBy": "operator", "unitsStated": False})
            start = h
    return out


def read(binding: dict, fetcher, now: datetime) -> Reading:
    d = local_date(now)
    page = DAYS[d.weekday()]
    series = [f"swpa:{page}.htm:{binding['project']}"]
    r = fetcher.get("swpa", f"{BASE}/{page}.htm", accept="text/html")
    if not r.ok:
        return failed("swpa", AGENCY, f"SWPA {page}.htm: {r.error}", series)
    text = text_of(r.body.decode("utf-8", errors="replace"))
    header, _ = header_and_grid(text)
    dates = stated_dates(header)
    if dates != {d}:
        return failed("swpa", AGENCY, f"SWPA {page}.htm: the page's own date (header above the grid) is {sorted(x.isoformat() for x in dates) or 'absent'}, "
                      f"not {d.isoformat()} (an old page is never used)", series)
    n = hours_in_day(d)
    grid = parse_grid(text, n)
    if grid is None:
        return failed("swpa", AGENCY, f"SWPA {page}.htm: the hourly grid is not complete ({n} rows expected for {d.isoformat()})", series)
    mw = grid.get(binding["project"])
    if mw is None:
        return failed("swpa", AGENCY, f"SWPA {page}.htm has no column {binding['project']}", series)
    return Reading("swpa", AGENCY, True, None, [], windows(mw, d), series, cadence_min=1440, lag_min=0)
