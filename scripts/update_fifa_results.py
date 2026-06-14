#!/usr/bin/env python3
"""Update fifa-schedule.html with the latest FIFA World Cup results.

Data source: TheSportsDB free API (no key required; falls back to the public
test key "3"). For each match row in the schedule whose result is reported as
final by the API, this fills the Result column and highlights the winner.

Design goals:
- Standard library only (no pip installs needed in CI).
- Safe: only a match the API confirms as finished is touched. A result the
  script cannot confirm is never erased, and existing rows are left byte-for-byte
  unchanged when the data already matches (so re-runs produce no noise).
- Network failures exit 0 without changing the file, so the schedule never
  breaks the page or commits empty diffs.

Knockout rows that still read "Match NN Winner" / "Group X Runners Up" are
placeholders, so they are skipped until they hold real team names.
"""
import json
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone

API_KEY = os.environ.get("THESPORTSDB_KEY", "3")
LEAGUE_ID = os.environ.get("FIFA_LEAGUE_ID", "4429")   # TheSportsDB: FIFA World Cup
SEASON = os.environ.get("FIFA_SEASON", "2026")
HTML_PATH = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "fifa-schedule.html")
)
TIMEOUT = 30

# Map provider / display spellings to one canonical key so API team names line
# up with the names printed in the schedule.
ALIASES = {
    "czech republic": "czechia",
    "bosnia herzegovina": "bosnia and herzegovina",
    "cote d ivoire": "ivory coast",
    "cote divoire": "ivory coast",
    "cabo verde": "cape verde",
    "korea republic": "south korea",
    "republic of korea": "south korea",
    "united states": "usa",
    "united states of america": "usa",
    "turkey": "turkiye",
    "dr congo": "congo dr",
    "democratic republic of congo": "congo dr",
    "congo democratic republic": "congo dr",
}

# Statuses we must not treat as a final score.
LIVE = {"1h", "2h", "ht", "et", "live", "break", "p", "pen live"}
NOT_STARTED = {"ns", "not started", "tbd", "postp.", "postponed",
               "cancelled", "canceled", "susp.", "suspended", "abandoned"}


def canon(name):
    """Normalise a team name to a comparison key (accent/punct insensitive)."""
    s = (name or "").strip().lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return ALIASES.get(s, s)


def fetch_events():
    url = (f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"
           f"/eventsseason.php?id={LEAGUE_ID}&s={SEASON}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "fifa-schedule-updater/1.0"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return (json.loads(resp.read().decode("utf-8")).get("events") or [])


def build_result_index(events):
    """Index final results by the unordered pair of canonical team names."""
    index = {}
    for e in events:
        home, away = e.get("strHomeTeam"), e.get("strAwayTeam")
        hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
        status = (e.get("strStatus") or "").strip().lower()
        if not home or not away or hs in (None, "") or as_ in (None, ""):
            continue
        if status in LIVE or status in NOT_STARTED:
            continue
        try:
            hs, as_ = int(hs), int(as_)
        except (TypeError, ValueError):
            continue
        ch, ca = canon(home), canon(away)
        index[frozenset((ch, ca))] = {ch: hs, ca: as_}
    return index


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


TR_RE = re.compile(r"^(\s*)(<tr[^>]*>)(.*)(</tr>)\s*$")
TD_RE = re.compile(r"<td[^>]*>.*?</td>")
TD_INNER_RE = re.compile(r"<td[^>]*>(.*)</td>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def update_row(line, index):
    """Return (new_line, changed) for a single schedule row."""
    m = TR_RE.match(line)
    if not m:
        return line, False
    indent, tr_open, inner, tr_close = m.groups()
    tds = TD_RE.findall(inner)
    if len(tds) != 7:                       # stage banners / header rows
        return line, False

    matchup_inner = TD_INNER_RE.match(tds[2]).group(1)
    text = TAG_RE.sub("", matchup_inner).strip()
    if " v " not in text:
        return line, False
    home_name, away_name = (p.strip() for p in text.split(" v ", 1))

    ch, ca = canon(home_name), canon(away_name)
    res = index.get(frozenset((ch, ca)))
    if not res or ch not in res or ca not in res:
        return line, False

    hs, as_ = res[ch], res[ca]
    h, a = esc(home_name), esc(away_name)
    if hs > as_:
        matchup = f'<span class="winner-team">{h}</span> v {a}'
    elif as_ > hs:
        matchup = f'{h} v <span class="winner-team">{a}</span>'
    else:
        matchup = f"{h} v {a}"
    result = f'<span class="result-done">FT: {h} {hs}-{as_} {a}</span>'

    tds[2] = f"<td>{matchup}</td>"
    tds[6] = f"<td>{result}</td>"
    new_line = f"{indent}{tr_open}{''.join(tds)}{tr_close}"
    return new_line, (new_line != line)


def main():
    try:
        events = fetch_events()
    except Exception as ex:                  # network / parse failure
        print(f"WARN: could not fetch results: {ex}", file=sys.stderr)
        return 0
    if not events:
        print("No events returned; leaving page unchanged.")
        return 0

    index = build_result_index(events)
    print(f"Fetched {len(events)} events; {len(index)} have a final result.")

    with open(HTML_PATH, encoding="utf-8") as f:
        lines = f.read().split("\n")

    changed = 0
    for i, line in enumerate(lines):
        new_line, did = update_row(line, index)
        if did:
            lines[i] = new_line
            changed += 1

    if changed == 0:
        print("Page already up to date; nothing to write.")
        return 0

    html = "\n".join(lines)
    stamp = f"{datetime.now(timezone.utc).day} {datetime.now(timezone.utc):%b %Y}"
    html = re.sub(r"(Updated )\d{1,2} \w{3} \d{4}", rf"\g<1>{stamp}", html, count=1)
    with open(HTML_PATH, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Applied {changed} result update(s); stamped '{stamp}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
