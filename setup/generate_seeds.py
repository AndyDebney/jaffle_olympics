#!/usr/bin/env python3
"""
generate_seeds.py — deterministic seed generator for the Jaffle Games dbt project.

This produces the CSVs in ../seeds/. It is intentionally hand-authored rather than
sampled from distributions: at a few hundred rows the narrative only survives if the
cohorts, payer segments, and patch effects are placed deliberately. See setup/README.md
for the demo stories these numbers are engineered to tell, and for the list of
deliberate data-quality imperfections.

Design rules honoured here:
  * Fixed random seed -> byte-identical output on every run.
  * Row counts and the history window are parameters at the top of the file.
  * Referential integrity is validated before any CSV is written.
  * The largest table is a few hundred rows. Do not scale this up casually; if a mart
    looks sparse, redistribute rows, do not add them.

Run:  python3 setup/generate_seeds.py
"""

from __future__ import annotations

import csv
import os
import random
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta

# --------------------------------------------------------------------------------------
# Configuration (parameterised for regeneration / rescaling)
# --------------------------------------------------------------------------------------

SEED = 20260805
RNG = random.Random(SEED)

SEEDS_DIR = os.path.join(os.path.dirname(__file__), "..", "seeds")

# History window: 12 months. Do not stretch further back — sparse charts read as broken.
WINDOW_START = date(2025, 8, 1)
WINDOW_END = date(2026, 8, 5)

N_PLAYERS = 120
N_MONTHLY_COHORTS = 12  # ~10 players per monthly registration cohort

# Target session volume (logical sessions, before duplicate injection).
TARGET_SESSIONS = 600
FLAGSHIP_SESSION_SHARE = 0.40  # Griddle Royale carries ~40% of all sessions.

# The underperformer's drought: capped total, and nothing in the trailing window.
UNDERPERFORMER_SESSION_CAP = 15
UNDERPERFORMER_QUIET_AFTER = date(2026, 6, 5)  # no sessions in the last two months

# Payer segments as FIXED COUNTS, not probabilities. These sum to N_PLAYERS.
# NOTE: "payer" here means live-service monetisation (IAP + season_pass + dlc). Premium
# unit sales are a SEPARATE revenue stream with a broader buyer base, so a non_payer can
# still have bought a premium title. This keeps the whale = ~1/3 of IAP story clean.
SEGMENT_COUNTS = {"whale": 1, "dolphin": 4, "minnow": 14, "non_payer": 101}

# Target lifetime IAP/season/dlc spend (USD) per payer segment. Tuned so the single whale
# is ~a third of total IAP revenue (brief's headline). Dolphin/minnow are a touch above the
# brief's rough $80/$15 to make that one-third math hold — flag at review if undesired.
SEGMENT_REVENUE_TARGET = {"whale": 400.0, "dolphin": 115.0, "minnow": 24.0}

# Storefront fee rates by platform (mobile qualifies for small-business program rates).
PLATFORM_FEE_RATE = {
    "steam": 0.30,
    "playstation": 0.30,
    "xbox": 0.30,
    "switch": 0.30,
    "ios": 0.15,
    "android": 0.15,
}
PLATFORM_FAMILY = {
    "steam": "pc",
    "playstation": "console",
    "xbox": "console",
    "switch": "console",
    "ios": "mobile",
    "android": "mobile",
}

# FX rates used to derive local_amount from USD (illustrative, fixed).
FX = {"USD": 1.0, "EUR": 0.92, "GBP": 0.79, "JPY": 150.0, "BRL": 5.10, "KRW": 1330.0}
COUNTRY_CURRENCY = {"US": "USD", "DE": "EUR", "GB": "GBP", "JP": "JPY", "BR": "BRL", "KR": "KRW"}

# Country weighting (US/DE/GB/JP/BR/KR carry most rows; a long tail exists).
COUNTRY_WEIGHTS = {"US": 40, "DE": 16, "GB": 14, "JP": 12, "BR": 9, "KR": 7, "CA": 4, "FR": 4, "AU": 3, "MX": 3}

LOADED_AT = "2026-08-05 06:00:00"  # batch _loaded_at stamp (UTC)

# --------------------------------------------------------------------------------------
# Reference data — titles (the portfolio narrative lives here)
# --------------------------------------------------------------------------------------

# role is not written to a seed; it drives generation and documents intent.
TITLES = [
    # id     name              genre        sub_genre        model            launch       price  team           engine    esrb  live   role
    ("T001", "Jaffle Quest",   "RPG",       "Action RPG",    "premium",        "2019-03-12", 39.99, "Team Marmalade", "Unreal", "T",  False, "aging_premium"),
    ("T002", "Neon Cabinet",   "Arcade",    "Twin-stick",    "premium_plus_dlc","2020-06-25", 19.99, "Team Griddle",   "Unity",  "E",  False, "aging_premium"),
    ("T003", "Preserve",       "Puzzle",    "Farming sim",   "premium",        "2020-11-05", 24.99, "Team Marmalade", "Godot",  "E",  False, "underperformer"),
    ("T004", "Toastlands",     "Platformer","Precision",     "premium_plus_dlc","2021-09-30", 29.99, "Team Griddle",   "Unity",  "E10","False", "aging_premium"),
    ("T005", "Griddle Royale", "Shooter",   "Battle Royale", "f2p",            "2022-04-18",  0.00, "Team Skillet",   "Unreal", "T",  True,  "flagship"),
    ("T006", "Crumb Rally",    "Racing",    "Arcade racer",  "premium",        "2023-08-22", 34.99, "Team Skillet",   "Unreal", "E",  False, "mid_premium"),
    ("T007", "Marmalade Siege","Strategy",  "Tower defense", "f2p",            "2024-02-14",  0.00, "Team Preserve",  "Unity",  "E10","True", "mid_f2p"),
    ("T008", "Batter Up!",     "Sports",    "Arcade sports", "f2p",            "2026-05-15",  0.00, "Team Preserve",  "Unity",  "E",  True,  "recent_launch"),
]
TITLE_BY_ID = {t[0]: t for t in TITLES}
TITLE_ROLE = {t[0]: t[11] for t in TITLES}
TITLE_LAUNCH = {t[0]: datetime.strptime(t[5], "%Y-%m-%d").date() for t in TITLES}
TITLE_PRICE = {t[0]: t[6] for t in TITLES}
TITLE_MODEL = {t[0]: t[4] for t in TITLES}

FLAGSHIP_ID = "T005"
UNDERPERFORMER_ID = "T003"
RECENT_LAUNCH_ID = "T008"
F2P_TITLES = [t[0] for t in TITLES if t[4] == "f2p"]        # T005, T007, T008
PREMIUM_TITLES = [t[0] for t in TITLES if t[4] != "f2p"]   # everything else

# Platforms each title ships on (title x platform ~= 24 rows) with a launch date each.
TITLE_PLATFORMS = {
    "T001": [("steam", "2019-03-12"), ("playstation", "2019-03-12"), ("xbox", "2019-03-12"), ("switch", "2020-05-01")],
    "T002": [("steam", "2020-06-25"), ("switch", "2020-06-25")],
    "T003": [("steam", "2020-11-05"), ("ios", "2021-02-10")],
    "T004": [("steam", "2021-09-30"), ("playstation", "2021-09-30"), ("switch", "2021-09-30")],
    "T005": [("steam", "2022-04-18"), ("playstation", "2022-04-18"), ("xbox", "2022-04-18"), ("ios", "2022-09-01"), ("android", "2022-09-01")],
    "T006": [("steam", "2023-08-22"), ("playstation", "2023-08-22"), ("xbox", "2023-08-22")],
    "T007": [("ios", "2024-02-14"), ("android", "2024-02-14"), ("steam", "2024-06-01")],
    "T008": [("ios", "2026-05-15"), ("android", "2026-05-15")],
}
# Per-title platform weights for session placement (mobile titles skew ios/android).
TITLE_PLATFORM_WEIGHTS = {
    "T001": {"steam": 5, "playstation": 3, "xbox": 2, "switch": 2},
    "T002": {"steam": 6, "switch": 4},
    "T003": {"steam": 7, "ios": 3},
    "T004": {"steam": 4, "playstation": 3, "switch": 3},
    "T005": {"steam": 4, "playstation": 3, "xbox": 2, "ios": 5, "android": 4},
    "T006": {"steam": 5, "playstation": 3, "xbox": 2},
    "T007": {"ios": 5, "android": 4, "steam": 2},
    "T008": {"ios": 5, "android": 4},
}

DEVICE_BY_PLATFORM = {
    "steam": ["PC (Windows)", "PC (Linux)", "Steam Deck"],
    "playstation": ["PS5", "PS4"],
    "xbox": ["Xbox Series X", "Xbox Series S", "Xbox One"],
    "switch": ["Switch OLED", "Switch"],
    "ios": ["iPhone 14", "iPhone 15", "iPhone 13", "iPad Air"],
    "android": ["Pixel 7", "Galaxy S23", "Pixel 8", "OnePlus 11"],
}
NETWORK_BY_FAMILY = {"pc": ["ethernet", "wifi"], "console": ["ethernet", "wifi"], "mobile": ["wifi", "cellular"]}

# --------------------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------------------

def weighted_choice(weights: dict):
    keys = list(weights.keys())
    return RNG.choices(keys, weights=[weights[k] for k in keys], k=1)[0]


def iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def random_time_on(d: date, weekend_evening_bias: bool = True) -> datetime:
    """A plausible play time: evenings peak, weekends skew later."""
    if weekend_evening_bias and d.weekday() >= 5:
        hour = RNG.choices(range(24), weights=[1,1,1,1,1,1,2,3,4,5,6,7,7,8,8,9,9,9,10,10,9,7,4,2])[0]
    else:
        hour = RNG.choices(range(24), weights=[1,1,1,1,1,1,2,3,4,4,4,5,6,5,4,4,5,7,9,10,10,8,5,3])[0]
    return datetime.combine(d, time(hour, RNG.randint(0, 59), RNG.randint(0, 59)))


def month_iter(start: date, n: int):
    y, m = start.year, start.month
    for _ in range(n):
        yield date(y, m, 1)
        m += 1
        if m > 12:
            m = 1
            y += 1


# --------------------------------------------------------------------------------------
# Players — 12 monthly cohorts, fixed channel + engagement + segment assignment
# --------------------------------------------------------------------------------------

# Channel counts (sum = 120). Two paid_social rows are deliberately mis-spelled later.
CHANNEL_COUNTS = {"organic": 45, "paid_social": 30, "influencer": 15, "store_featured": 18, "cross_promo": 12}

# Engagement tiers define which week-offsets a player returns in (relative to registration).
# Counts are chosen so the AGGREGATE curve lands near 40% wk1 / 20% wk2 / 10% wk4.
#   bounce -> week 0 only            (churns after install)
#   trier  -> weeks 0-1              (one comeback)
#   return -> weeks 0,1,2 (+a little)
#   core   -> reaches ~week 12
#   loyal  -> reaches ~week 40+
#   return reaches week 3 but NOT week 4 (so week-4 return stays ~10%, core+loyal only).
TIER_WEEK_OFFSETS = {
    "bounce": [0],
    "trier":  [0, 1],
    "return": [0, 1, 2, 3],
    "core":   [0, 1, 2, 3, 4, 6, 8, 12, 16, 20],
    "loyal":  [0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 26, 32, 40, 46],
}
# Total f2p-primary sessions a player of each tier produces (>= number of active weeks,
# so every listed offset is covered at least once; the surplus is scattered across them).
TIER_TOTAL_SESSIONS = {
    "bounce": 1,
    "trier":  2,
    "return": 6,
    "core":   12,
    "loyal":  22,
}

# Deliberate tier allocation PER CHANNEL. Column sums hit the global tier targets;
# paid_social / cross_promo are visibly worse (mostly bounce), organic much stickier.
TIER_ALLOCATION = {
    #             bounce trier return core loyal
    "paid_social":   (24,   6,    0,    0,   0),
    "cross_promo":   ( 9,   3,    0,    0,   0),
    "store_featured":(12,   4,    2,    0,   0),
    "influencer":    ( 8,   4,    2,    1,   0),
    "organic":       (19,   7,    8,    7,   4),
}
TIER_ORDER = ["bounce", "trier", "return", "core", "loyal"]


def build_players():
    """Return (players list-of-dict, per-player context dict keyed by player_id)."""
    # 1) Assign cohort months: ~10 per month across 12 months.
    cohort_months = list(month_iter(WINDOW_START, N_MONTHLY_COHORTS))
    per_cohort = N_PLAYERS // N_MONTHLY_COHORTS  # 10
    player_cohort = []
    for cm in cohort_months:
        player_cohort.extend([cm] * per_cohort)
    # (120 == 12*10 exactly; no remainder to scatter.)

    # 2) Assign channels as a flat pool, then shuffle deterministically.
    channel_pool = []
    for ch, n in CHANNEL_COUNTS.items():
        channel_pool.extend([ch] * n)
    RNG.shuffle(channel_pool)

    # 3) Assign an engagement tier to each channel-group by the allocation table.
    tier_by_channel_queue = {}
    for ch, alloc in TIER_ALLOCATION.items():
        tiers = []
        for tier, cnt in zip(TIER_ORDER, alloc):
            tiers.extend([tier] * cnt)
        RNG.shuffle(tiers)
        tier_by_channel_queue[ch] = tiers

    players = []
    ctx = {}
    for i in range(N_PLAYERS):
        pid = f"P{i+1:03d}"
        cohort = player_cohort[i]
        channel = channel_pool[i]
        tier = tier_by_channel_queue[channel].pop()

        # Registration timestamp: a random day within the cohort month, inside window.
        last_day = 27  # keep to <=27 so every month is safe
        reg_day = RNG.randint(1, last_day)
        reg_dt = random_time_on(date(cohort.year, cohort.month, reg_day), weekend_evening_bias=False)
        if reg_dt.date() < WINDOW_START:
            reg_dt = random_time_on(WINDOW_START, weekend_evening_bias=False)

        country = weighted_choice(COUNTRY_WEIGHTS)
        birth_year = RNG.randint(1972, 2008)
        platform_reg = weighted_choice({"steam": 5, "ios": 5, "android": 4, "playstation": 3, "xbox": 2, "switch": 2})
        opt_in = RNG.random() < 0.62

        players.append({
            "player_id": pid,
            "registered_at": iso(reg_dt),
            "country_code": country,
            "platform_registered_on": platform_reg,
            "acquisition_channel": channel,
            "acquisition_campaign_id": None,  # filled after marketing spend exists
            "birth_year": birth_year,
            "email": f"player{i+1:03d}@example.com",
            "marketing_opt_in": opt_in,
            "account_status": None,  # derived from last_login after sessions exist
            "last_login_at": None,
            "_loaded_at": LOADED_AT,
        })
        ctx[pid] = {
            "cohort": cohort,
            "channel": channel,
            "tier": tier,
            "reg_dt": reg_dt,
            "country": country,
            "segment": "non_payer",  # assigned below
            "titles_owned": set(),   # premium titles the player has bought
            "primary_title": None,
            "sessions": [],          # filled by session generator
        }
    return players, ctx


def assign_segments(ctx):
    """Assign 1 whale / 4 dolphins / 14 minnows deliberately to the stickiest players."""
    loyal = [p for p, c in ctx.items() if c["tier"] == "loyal"]
    core = [p for p, c in ctx.items() if c["tier"] == "core"]
    ret = [p for p, c in ctx.items() if c["tier"] == "return"]
    # Deterministic ordering already fixed by RNG; sort for stability then pick.
    loyal.sort(); core.sort(); ret.sort()

    whale = loyal[0]
    ctx[whale]["segment"] = "whale"
    dolphins = loyal[1:4] + core[:1]          # 3 loyal + 1 core = 4
    for p in dolphins:
        ctx[p]["segment"] = "dolphin"
    minnow_pool = core[1:] + ret               # 7 core + 12 return = 19 candidates
    minnows = minnow_pool[:14]
    for p in minnows:
        ctx[p]["segment"] = "minnow"
    # everyone else stays non_payer
    counts = Counter(c["segment"] for c in ctx.values())
    assert counts == Counter(SEGMENT_COUNTS), f"segment counts off: {counts}"


# --------------------------------------------------------------------------------------
# Releases — patch history; three releases are placed to matter (documented in README)
# --------------------------------------------------------------------------------------

def build_releases():
    """Return (releases list-of-dict, release_index) where release_index maps
    title_id -> sorted list of (released_at_date, app_version) for version-in-effect lookups."""
    #  title  version    date          type          rollback  est  act  bugs  note
    spec = [
        # Flagship: dense live-service cadence; the three engineered releases are marked.
        ("T005", "3.0.0", "2025-08-01", "major",       False, 40, 44, 12, "Season 3 launch: new map rotation and ranked reset."),
        ("T005", "3.1.0", "2025-09-10", "minor",       False, 12, 13,  4, "Weapon balance pass and matchmaking tweaks."),
        ("T005", "3.2.0", "2025-11-15", "content_drop",False, 25, 27,  6, "Autumn content drop: new operator, LTM, and cosmetics."),  # <-- lift
        ("T005", "3.2.1", "2025-11-20", "hotfix",      False,  2,  2,  1, "Fix cosmetic store pricing bug."),
        ("T005", "3.3.0", "2025-12-18", "event",       False, 10, 11,  3, "Winter event: limited-time festive mode."),
        ("T005", "3.4.0", "2026-01-22", "minor",       False, 12, 12,  3, "Ranked season roll and audio fixes."),
        ("T005", "3.5.0", "2026-02-14", "content_drop",False, 24, 26,  5, "Valentine's collab skins and new POI."),
        ("T005", "4.0.0", "2026-03-10", "major",       False, 45, 71, 38, "Engine 5 upgrade. Shipped with severe crash regressions."),  # <-- tanks
        ("T005", "4.0.1", "2026-03-14", "hotfix",      True,   3,  4,  2, "Rollback of 4.0.0 renderer changes after crash spike."),      # <-- rollback
        ("T005", "4.0.2", "2026-03-18", "hotfix",      False,  4,  5,  3, "Re-land Engine 5 upgrade behind a flag."),
        ("T005", "4.1.0", "2026-04-20", "minor",       False, 14, 15,  4, "Stability and anti-cheat improvements."),
        ("T005", "4.2.0", "2026-05-22", "content_drop",False, 26, 28,  6, "Summer content drop and battle pass 12."),
        ("T005", "4.3.0", "2026-06-20", "event",       False, 11, 12,  3, "Anniversary event and login rewards."),
        ("T005", "4.4.0", "2026-07-15", "minor",       False, 13, 14,  4, "Performance pass on mobile clients."),
        # Marmalade Siege: live-service, lighter cadence.
        ("T007", "2.4.0", "2025-08-05", "minor",       False, 10, 11,  3, "New defensive tower line."),
        ("T007", "2.5.0", "2025-10-01", "content_drop",False, 18, 20,  5, "Campaign chapter 5 and event tokens."),
        ("T007", "2.5.1", "2025-10-08", "hotfix",      False,  2,  2,  1, "Fix token grant duplication."),
        ("T007", "2.6.0", "2025-12-10", "event",       False,  9, 10,  2, "Holiday siege event."),
        ("T007", "2.7.0", "2026-02-20", "minor",       False, 11, 12,  3, "Guild features and balance."),
        ("T007", "2.8.0", "2026-04-15", "content_drop",False, 17, 18,  4, "Campaign chapter 6."),
        ("T007", "2.9.0", "2026-06-05", "minor",       False, 10, 10,  2, "Quality-of-life and localisation."),
        ("T007", "2.9.1", "2026-07-20", "hotfix",      False,  2,  3,  1, "Fix crash on guild-war join."),
        # Batter Up!: recent launch, still spiking.
        ("T008", "1.0.0", "2026-05-15", "major",       False, 60, 66, 15, "Worldwide launch."),
        ("T008", "1.0.1", "2026-05-22", "hotfix",      False,  3,  4,  4, "Launch stability fixes."),
        ("T008", "1.1.0", "2026-06-18", "content_drop",False, 16, 17,  4, "Season 1 pass and new stadiums."),
        ("T008", "1.2.0", "2026-07-25", "minor",       False, 12, 13,  3, "Online multiplayer improvements."),
        # Aging premium titles: sparse patches.
        ("T001", "1.7.0", "2025-08-01", "minor",       False,  8,  9,  2, "Compatibility patch for latest OS."),
        ("T001", "1.7.1", "2025-11-02", "hotfix",      False,  2,  2,  1, "Fix save corruption on Switch."),
        ("T001", "1.8.0", "2026-03-01", "minor",       False,  9, 10,  3, "Accessibility options update."),
        ("T002", "2.1.0", "2025-08-01", "minor",       False,  6,  6,  2, "Leaderboard fixes."),
        ("T002", "2.2.0", "2025-10-15", "content_drop",False, 14, 16,  4, "Neon Nights DLC pack."),
        ("T002", "2.2.1", "2026-01-10", "hotfix",      False,  2,  2,  1, "Fix DLC unlock entitlement."),
        ("T004", "1.4.0", "2025-08-01", "minor",       False,  7,  7,  2, "Controller remap support."),
        ("T004", "1.5.0", "2025-12-05", "content_drop",False, 15, 16,  4, "Frozen Peaks level pack."),
        ("T004", "1.5.1", "2026-02-02", "hotfix",      False,  2,  3,  1, "Fix speedrun timer drift."),
        ("T006", "1.2.0", "2025-08-01", "minor",       False,  8,  8,  2, "New time-trial tracks."),
        ("T006", "1.3.0", "2025-11-28", "content_drop",False, 16, 17,  4, "Dessert Circuit expansion."),
        ("T006", "1.3.1", "2026-04-05", "hotfix",      False,  2,  2,  1, "Fix ghost data desync."),
        # Underperformer: last touched early; nothing recent (reinforces the drought).
        ("T003", "1.3.0", "2025-08-10", "minor",       False,  6,  7,  2, "Localisation and bug fixes."),
        ("T003", "1.3.1", "2025-09-15", "hotfix",      False,  2,  2,  1, "Fix cloud-save conflict."),
    ]
    releases = []
    release_index = defaultdict(list)
    for i, (tid, ver, d, rtype, rollback, est, act, bugs, note) in enumerate(spec):
        rid = f"R{i+1:03d}"
        rel_date = datetime.strptime(d, "%Y-%m-%d").date()
        released_at = iso(random_time_on(rel_date, weekend_evening_bias=False))
        releases.append({
            "release_id": rid,
            "title_id": tid,
            "app_version": ver,
            "released_at": released_at,
            "release_type": rtype,
            "release_notes": note,
            "dev_days_estimated": est,
            "dev_days_actual": act,
            "qa_bug_count": bugs,
            "is_rollback": rollback,
            "_loaded_at": LOADED_AT,
        })
        release_index[tid].append((rel_date, ver))
    for tid in release_index:
        release_index[tid].sort()
    return releases, release_index


def version_in_effect(release_index, tid: str, when: date) -> str:
    """Latest app_version released on/before `when` for title `tid` (fallback: earliest)."""
    versions = release_index.get(tid, [])
    if not versions:
        return "1.0.0"
    effective = versions[0][1]
    for rel_date, ver in versions:
        if rel_date <= when:
            effective = ver
        else:
            break
    return effective


# --------------------------------------------------------------------------------------
# Play sessions — retention schedules + patch clustering + title/platform mix
# --------------------------------------------------------------------------------------

# Key dates for hand-placed patch effects on the flagship.
CONTENT_DROP_LIFT = (date(2025, 11, 15), date(2025, 11, 25))   # extra sessions here
BAD_MAJOR_WINDOW = (date(2026, 3, 10), date(2026, 3, 14))       # high crash, then rollback


def playable_f2p_titles(reg_dt: datetime):
    """F2P titles already launched by the player's registration date."""
    out = []
    for tid in F2P_TITLES:
        if TITLE_LAUNCH[tid] <= reg_dt.date():
            out.append(tid)
    return out


# Deliberate live-service spend plan for the 19 payers: the flagship gets the whale and
# the bulk of spend; Marmalade Siege gets a handful so it isn't a zero-revenue f2p title.
# (Batter Up! is intentionally pre-revenue — its story is the engagement spike.)
PAYER_SPEND_PLAN = {
    "whale":   ["T005"],
    "dolphin": ["T005", "T005", "T005", "T007"],
    "minnow":  ["T005"] * 10 + ["T007"] * 4,
}


def assign_primary_titles(ctx):
    """Assign each player a live-service primary title (drives the retention backbone).
    Non-payers are weighted toward the flagship; the 19 payers are placed onto their
    planned spend title so sessions and monetisation line up."""
    # Non-payers: weighted f2p choice.
    for pid, c in ctx.items():
        if c["segment"] != "non_payer":
            continue
        f2p_avail = playable_f2p_titles(c["reg_dt"]) or [FLAGSHIP_ID]
        weights = {}
        for tid in f2p_avail:
            if tid == FLAGSHIP_ID:
                weights[tid] = 48
            elif tid == RECENT_LAUNCH_ID:
                weights[tid] = 18
            else:
                weights[tid] = 26
        c["primary_title"] = weighted_choice(weights)

    # Payers: assign by the deliberate spend plan (stable order for determinism).
    plan_queue = {seg: list(titles) for seg, titles in PAYER_SPEND_PLAN.items()}
    for seg in ("whale", "dolphin", "minnow"):
        seg_players = sorted([p for p, c in ctx.items() if c["segment"] == seg])
        for pid in seg_players:
            tid = plan_queue[seg].pop(0) if plan_queue[seg] else FLAGSHIP_ID
            # Marmalade launched pre-window, so it is always playable; guard anyway.
            if TITLE_LAUNCH[tid] > ctx[pid]["reg_dt"].date():
                tid = FLAGSHIP_ID
            ctx[pid]["primary_title"] = tid
            ctx[pid]["spend_title"] = tid


def pick_platform_for_title(tid: str, reg_dt: datetime, when: date):
    """Choose a platform available for this title (launched on/before `when`)."""
    available = {}
    launch_map = {p: datetime.strptime(d, "%Y-%m-%d").date() for p, d in TITLE_PLATFORMS[tid]}
    for plat, w in TITLE_PLATFORM_WEIGHTS[tid].items():
        if plat in launch_map and launch_map[plat] <= when:
            available[plat] = w
    if not available:
        return None
    return weighted_choice(available)


def session_duration_seconds(family: str) -> int:
    if family == "mobile":
        return RNG.randint(180, 1500)      # 3–25 min
    return RNG.randint(900, 5400)          # 15–90 min


class SeqCounter:
    """Monotonic session-id sequence shared across generation passes."""
    def __init__(self):
        self.n = 0
    def next(self):
        self.n += 1
        return self.n


def _place_offsets(total, offsets):
    """Distribute `total` sessions across week `offsets`, covering each offset once first."""
    counts = {wk: 1 for wk in offsets}
    remaining = total - len(offsets)
    while remaining > 0:
        counts[RNG.choice(offsets)] += 1
        remaining -= 1
    return counts


def generate_sessions(ctx, release_index, seq):
    """Pass 1: the f2p retention backbone. Each player plays only their f2p primary,
    with an explicit session total placed across their tier's return-week offsets."""
    sessions = []
    for pid in sorted(ctx.keys()):
        c = ctx[pid]
        reg = c["reg_dt"]
        tid = c["primary_title"]
        counts = _place_offsets(TIER_TOTAL_SESSIONS[c["tier"]], TIER_WEEK_OFFSETS[c["tier"]])
        for wk, n_sess in counts.items():
            week_start = (reg + timedelta(weeks=wk)).date()
            if week_start > WINDOW_END:
                continue
            for _ in range(n_sess):
                day_weights = [10, 10, 10, 10, 12, 16, 16]  # Mon..Sun (~1.5x weekend)
                dow = RNG.choices(range(7), weights=day_weights)[0]
                sday = week_start + timedelta(days=dow)
                if sday < reg.date():
                    sday = reg.date()
                if sday > WINDOW_END or TITLE_LAUNCH[tid] > sday:
                    continue
                plat = pick_platform_for_title(tid, reg, sday)
                if plat is None:
                    continue
                sessions.append(_make_session(seq.next(), pid, c, tid, plat, sday, release_index))

    _add_seasonal_bump(sessions, ctx, release_index, seq)
    _add_content_drop_lift(sessions, ctx, release_index, seq)
    return sessions


# Per-premium-title session/owner targets and temporal shape.
#   temporal: 'early' -> declining engagement over the window (aging back-catalogue)
#             'flat'  -> steady
PREMIUM_CATALOG = {
    "T006": {"sessions": 60, "owners": 12, "temporal": "flat"},   # Crumb Rally
    "T001": {"sessions": 52, "owners": 10, "temporal": "early"},  # Jaffle Quest
    "T002": {"sessions": 48, "owners": 11, "temporal": "early"},  # Neon Cabinet
    "T004": {"sessions": 44, "owners": 10, "temporal": "early"},  # Toastlands
    "T003": {"sessions": 15, "owners": 4,  "temporal": "early"},  # Preserve (underperformer)
}


def build_premium_catalog(ctx, release_index, seq):
    """Pass 2: premium back-catalogue engagement + ownership.
    Gives the premium titles enough monthly density to chart, and records who bought
    what (drives premium_purchase transactions). Ownership is independent of payer segment.
    Returns (sessions, ownership) where ownership = list of (player_id, title_id, purchase_date)."""
    sessions = []
    ownership = []
    all_players = sorted(ctx.keys())

    for tid, cfg in PREMIUM_CATALOG.items():
        launch = TITLE_LAUNCH[tid]
        is_underperf = tid == UNDERPERFORMER_ID
        # Choose owners. Underperformer: a few early registrants only.
        if is_underperf:
            pool = sorted([p for p in all_players if ctx[p]["reg_dt"].date() < date(2025, 11, 1)],
                          key=lambda p: ctx[p]["reg_dt"])
            owners = pool[:cfg["owners"]]
        else:
            pool = [p for p in all_players if ctx[p]["reg_dt"].date() <= WINDOW_END]
            owners = RNG.sample(pool, min(cfg["owners"], len(pool)))
        owners = sorted(owners)
        if not owners:
            continue

        # Purchase dates: after registration, after title launch, within window.
        purchase_date = {}
        for p in owners:
            reg = ctx[p]["reg_dt"].date()
            earliest = max(reg, launch)
            if is_underperf:
                latest = date(2026, 1, 31)
            else:
                latest = WINDOW_END
            if earliest > latest:
                earliest = latest
            span = (latest - earliest).days
            purchase_date[p] = earliest + timedelta(days=RNG.randint(0, max(0, span)))
            ownership.append((p, tid, purchase_date[p]))

        # Distribute sessions roughly evenly across owners, min 1 each.
        target = cfg["sessions"]
        per_owner = {p: 1 for p in owners}
        for _ in range(max(0, target - len(owners))):
            per_owner[RNG.choice(owners)] += 1

        for p in owners:
            c = ctx[p]
            for _ in range(per_owner[p]):
                start_bound = max(purchase_date[p], launch)
                if is_underperf:
                    end_bound = date(2026, 2, 28)  # drought: dead well before window end
                else:
                    end_bound = WINDOW_END
                if start_bound >= end_bound:
                    sday = start_bound
                else:
                    span = (end_bound - start_bound).days
                    u = RNG.random()
                    frac = u * u if cfg["temporal"] == "early" else u  # early-heavy -> decline
                    sday = start_bound + timedelta(days=int(frac * span))
                plat = pick_platform_for_title(tid, c["reg_dt"], sday)
                if plat is None:
                    continue
                sessions.append(_make_session(seq.next(), p, c, tid, plat, sday, release_index))

    return sessions, ownership


def _make_session(seq, pid, c, tid, plat, sday, release_index, force_crash=None):
    family = PLATFORM_FAMILY[plat]
    start_dt = random_time_on(sday)
    # A same-day session must still start after the account was registered.
    if start_dt < c["reg_dt"]:
        start_dt = c["reg_dt"] + timedelta(minutes=RNG.randint(2, 240))
    dur = session_duration_seconds(family)
    end_dt = start_dt + timedelta(seconds=dur)

    # Crash rate: baseline low; spikes for the flagship during the bad-major window.
    if force_crash is not None:
        crashed = force_crash
    elif tid == FLAGSHIP_ID and BAD_MAJOR_WINDOW[0] <= sday <= BAD_MAJOR_WINDOW[1]:
        crashed = RNG.random() < 0.45
    else:
        crashed = RNG.random() < 0.03

    levels = RNG.randint(0, 3) if family == "mobile" else RNG.randint(0, 8)
    return {
        "session_id": f"S{seq:04d}",
        "player_id": pid,
        "title_id": tid,
        "platform": plat,
        "session_start_at": iso(start_dt),
        "session_end_at": iso(end_dt),
        "duration_seconds": dur,
        "device_model": RNG.choice(DEVICE_BY_PLATFORM[plat]),
        "app_version": version_in_effect(release_index, tid, sday),
        "country_code": c["country"],
        "levels_completed": levels,
        "crashed_flag": crashed,
        "network_type": RNG.choice(NETWORK_BY_FAMILY[family]),
        "_loaded_at": LOADED_AT,
        "_day": sday,  # scratch field, dropped before write
    }


def _add_seasonal_bump(sessions, ctx, release_index, seq):
    """~14 extra December sessions from players already active by December."""
    dec_active = sorted([p for p, c in ctx.items()
                         if c["reg_dt"].date() <= date(2025, 12, 1) and c["tier"] in ("return", "core", "loyal")])
    for _ in range(14):
        pid = RNG.choice(dec_active)
        c = ctx[pid]
        tid = c["primary_title"]
        sday = date(2025, 12, RNG.randint(10, 28))
        if TITLE_LAUNCH[tid] > sday:
            continue
        plat = pick_platform_for_title(tid, c["reg_dt"], sday)
        if plat is None:
            continue
        sessions.append(_make_session(seq.next(), pid, c, tid, plat, sday, release_index))


def _add_content_drop_lift(sessions, ctx, release_index, seq):
    """Cluster ~20 extra flagship sessions in the content-drop window for a visible lift."""
    flagship_players = sorted([p for p, c in ctx.items()
                               if c["primary_title"] == FLAGSHIP_ID and c["reg_dt"].date() <= CONTENT_DROP_LIFT[1]])
    span = (CONTENT_DROP_LIFT[1] - CONTENT_DROP_LIFT[0]).days
    for _ in range(20):
        pid = RNG.choice(flagship_players)
        c = ctx[pid]
        sday = CONTENT_DROP_LIFT[0] + timedelta(days=RNG.randint(0, span))
        plat = pick_platform_for_title(FLAGSHIP_ID, c["reg_dt"], sday)
        if plat is None:
            continue
        sessions.append(_make_session(seq.next(), pid, c, FLAGSHIP_ID, plat, sday, release_index))


# --------------------------------------------------------------------------------------
# SKUs
# --------------------------------------------------------------------------------------

def build_skus():
    """~30 purchasable items. F2P titles get cosmetics/currency/battle_pass; premium get expansions."""
    skus = []
    idx = 0

    def add(tid, name, category, price, active, first):
        nonlocal idx
        idx += 1
        skus.append({
            "sku_id": f"SKU{idx:03d}",
            "title_id": tid,
            "sku_name": name,
            "sku_category": category,
            "price_usd": price,
            "is_active": active,
            "first_available_date": first,
        })

    # Flagship (T005): rich store.
    add("T005", "Griddle Royale — Battle Pass S3", "battle_pass", 9.99, True, "2025-08-01")
    add("T005", "Griddle Royale — Battle Pass S4", "battle_pass", 9.99, True, "2026-03-18")
    add("T005", "Skillet Coins — Small", "currency_pack", 4.99, True, "2022-04-18")
    add("T005", "Skillet Coins — Medium", "currency_pack", 9.99, True, "2022-04-18")
    add("T005", "Skillet Coins — Large", "currency_pack", 19.99, True, "2022-04-18")
    add("T005", "Skillet Coins — Mega", "currency_pack", 49.99, True, "2022-04-18")
    add("T005", "Operator Skin — Chrome Chef", "cosmetic", 14.99, True, "2025-11-15")
    add("T005", "Operator Skin — Neon Line Cook", "cosmetic", 12.99, True, "2026-02-14")
    add("T005", "Weapon Wrap — Maple Glaze", "cosmetic", 7.99, True, "2025-08-01")
    add("T005", "Emote Bundle — Sizzle", "cosmetic", 4.99, False, "2025-08-01")
    # Marmalade Siege (T007).
    add("T007", "Marmalade Siege — Season Pass", "battle_pass", 7.99, True, "2024-02-14")
    add("T007", "Jam Jars — Small", "currency_pack", 2.99, True, "2024-02-14")
    add("T007", "Jam Jars — Large", "currency_pack", 14.99, True, "2024-02-14")
    add("T007", "Tower Skin — Golden Turret", "cosmetic", 5.99, True, "2025-10-01")
    add("T007", "Campaign Chapter 6", "expansion", 6.99, True, "2026-04-15")
    # Batter Up! (T008).
    add("T008", "Batter Up! — Season 1 Pass", "battle_pass", 9.99, True, "2026-06-18")
    add("T008", "Batter Bucks — Small", "currency_pack", 4.99, True, "2026-05-15")
    add("T008", "Batter Bucks — Large", "currency_pack", 19.99, True, "2026-05-15")
    add("T008", "Stadium Skin — Sunset Park", "cosmetic", 6.99, True, "2026-06-18")
    # Premium titles: paid expansions / DLC.
    add("T001", "Jaffle Quest — Crumbcastle DLC", "expansion", 14.99, True, "2020-01-15")
    add("T001", "Jaffle Quest — Art & Soundtrack", "cosmetic", 9.99, True, "2019-06-01")
    add("T002", "Neon Cabinet — Neon Nights Pack", "expansion", 9.99, True, "2025-10-15")
    add("T002", "Neon Cabinet — Retro Skins", "cosmetic", 3.99, True, "2021-01-01")
    add("T004", "Toastlands — Frozen Peaks Pack", "expansion", 12.99, True, "2025-12-05")
    add("T004", "Toastlands — Golden Toast Skin", "cosmetic", 2.99, True, "2022-01-01")
    add("T006", "Crumb Rally — Dessert Circuit", "expansion", 11.99, True, "2025-11-28")
    add("T006", "Crumb Rally — Chrome Kart Pack", "cosmetic", 5.99, True, "2024-01-01")
    add("T003", "Preserve — Orchard Expansion", "expansion", 7.99, False, "2021-06-01")
    add("T003", "Preserve — Cottage Decor Pack", "cosmetic", 3.99, False, "2021-06-01")
    return skus


# --------------------------------------------------------------------------------------
# Transactions — payer segments drive spend; refunds/chargebacks stored positive
# --------------------------------------------------------------------------------------

def build_transactions(ctx, skus, ownership):
    """Generate ~200 transactions across three streams:
      * premium_purchase  — one per (player, premium title) from catalogue ownership
      * iap/season/dlc     — from the 19 live-service payers, to their segment target
      * refund/chargeback  — mirror prior positive purchases, stored as POSITIVE amounts
    Timestamps arrive in America/New_York wall-clock (the one non-UTC seed)."""
    skus_by_title = defaultdict(list)
    for s in skus:
        skus_by_title[s["title_id"]].append(s)

    transactions = []
    tx_seq = 0

    def add_tx(pid, tid, ttype, amount, sku_id, when_dt):
        nonlocal tx_seq
        tx_seq += 1
        c = ctx[pid]
        plat = pick_platform_for_title(tid, None, when_dt.date()) or "steam"
        currency = COUNTRY_CURRENCY.get(c["country"], "USD")
        pm = {"ios": "apple_pay", "android": "google_play", "steam": RNG.choice(["card", "paypal"]),
              "playstation": "platform_wallet", "xbox": "platform_wallet", "switch": "platform_wallet"}[plat]
        transactions.append({
            "transaction_id": f"TX{tx_seq:04d}",
            "player_id": pid,
            "title_id": tid,
            "platform": plat,
            "transaction_at": iso(when_dt),  # America/New_York wall-clock
            "transaction_type": ttype,
            "sku_id": sku_id,
            "gross_amount_usd": round(amount, 2),
            "platform_fee_usd": round(amount * PLATFORM_FEE_RATE[plat], 2),
            "currency_code": currency,
            "local_amount": round(amount * FX.get(currency, 1.0), 2),
            "payment_method": pm,
            "is_first_purchase": False,  # set after all rows exist (earliest per player)
            "_loaded_at": LOADED_AT,
        })
        return transactions[-1]

    def et_ts(after_dt):
        span = max(1, (WINDOW_END - after_dt.date()).days)
        return random_time_on(after_dt.date() + timedelta(days=RNG.randint(0, span)))

    # 1) Premium unit sales from catalogue ownership.
    for pid, tid, pdate in ownership:
        price = TITLE_PRICE[tid]
        if price > 0:
            add_tx(pid, tid, "premium_purchase", price,
                   None, random_time_on(pdate))

    # 2) Live-service monetisation from the 19 payers, to their segment target.
    payers = sorted([p for p, c in ctx.items() if c["segment"] != "non_payer"],
                    key=lambda p: (ctx[p]["segment"] != "whale", ctx[p]["segment"] != "dolphin", p))
    positive_iap = defaultdict(list)
    for pid in payers:
        c = ctx[pid]
        seg = c["segment"]
        target = SEGMENT_REVENUE_TARGET[seg]
        f2p_title = c["primary_title"] if c["primary_title"] in F2P_TITLES else FLAGSHIP_ID
        title_skus = [s for s in skus_by_title[f2p_title] if s["is_active"]]
        # Basket shape by segment: whales reach for large packs, dolphins for mid packs,
        # minnows for small ones. Smaller baskets => more transactions per dollar.
        def pack_weight(s):
            price = s["price_usd"]
            if seg == "whale":
                return max(1, int(price))
            if seg == "dolphin":
                return max(1, int(15 - abs(price - 10)))
            return max(1, int(30 - price))  # minnow
        spent = 0.0
        # Everyone buys the season pass once, then currency/cosmetics to target.
        bp = [s for s in title_skus if s["sku_category"] == "battle_pass"]
        if bp:
            sku = bp[0]
            t = add_tx(pid, f2p_title, "season_pass", sku["price_usd"], sku["sku_id"], et_ts(c["reg_dt"]))
            positive_iap[pid].append(t); spent += sku["price_usd"]
        iap_skus = [s for s in title_skus if s["sku_category"] in ("currency_pack", "cosmetic")]
        guard = 0
        while spent < target - 2.0 and guard < 200 and iap_skus:
            guard += 1
            sku = RNG.choices(iap_skus, weights=[pack_weight(s) for s in iap_skus])[0]
            if spent + sku["price_usd"] > target + 15:  # near target: prefer a small pack
                small = sorted(iap_skus, key=lambda s: s["price_usd"])[0]
                sku = small
            t = add_tx(pid, f2p_title, "iap", sku["price_usd"], sku["sku_id"], et_ts(c["reg_dt"]))
            positive_iap[pid].append(t); spent += sku["price_usd"]

    # 3) DLC / expansion sales: some premium owners also buy the paid expansion.
    for pid, tid, pdate in ownership:
        exps = [s for s in skus_by_title[tid] if s["sku_category"] == "expansion" and s["is_active"]]
        if exps and RNG.random() < 0.40:
            sku = RNG.choice(exps)
            when = min(pdate + timedelta(days=RNG.randint(3, 120)), WINDOW_END)
            add_tx(pid, tid, "dlc", sku["price_usd"], sku["sku_id"], random_time_on(when))

    # 4) Refunds (6) and chargebacks (3): mirror positive IAP, stored POSITIVE amounts.
    #    Whales are excluded (they don't churn/chargeback) so their share stays clean.
    pool = [t for pid, lst in positive_iap.items() if ctx[pid]["segment"] != "whale" for t in lst]
    RNG.shuffle(pool)
    for t in pool[:6]:
        base = datetime.strptime(t["transaction_at"], "%Y-%m-%d %H:%M:%S")
        add_tx(t["player_id"], t["title_id"], "refund", t["gross_amount_usd"], t["sku_id"],
               base + timedelta(days=RNG.randint(1, 10)))
    for t in pool[6:9]:
        base = datetime.strptime(t["transaction_at"], "%Y-%m-%d %H:%M:%S")
        add_tx(t["player_id"], t["title_id"], "chargeback", t["gross_amount_usd"], t["sku_id"],
               base + timedelta(days=RNG.randint(5, 30)))

    # is_first_purchase: earliest acquisition transaction per player.
    acq = ("premium_purchase", "iap", "season_pass", "dlc")
    first_seen = set()
    for t in sorted(transactions, key=lambda t: t["transaction_at"]):
        if t["transaction_type"] in acq and t["player_id"] not in first_seen:
            t["is_first_purchase"] = True
            first_seen.add(t["player_id"])

    return transactions


# --------------------------------------------------------------------------------------
# High scores
# --------------------------------------------------------------------------------------

LEADERBOARD_TITLES = {  # titles that have competitive leaderboards
    "T005": ["gr_ranked_global", "gr_ltm_weekly"],
    "T002": ["nc_arcade_classic"],
    "T006": ["cr_time_trial"],
    "T008": ["bu_home_run_derby"],
    "T004": ["tl_speedrun"],
}


def build_high_scores(ctx, cheater_players):
    """~250 leaderboard submissions. A small number are flagged for cheating."""
    scores = []
    seq = 0
    # Players who ever played a leaderboard title become eligible submitters.
    eligible = defaultdict(list)  # title -> [players]
    for pid, c in ctx.items():
        titles_played = {s["title_id"] for s in c["sessions"]}
        for tid in titles_played:
            if tid in LEADERBOARD_TITLES:
                eligible[tid].append(pid)

    total_target = 250
    # Weight submissions toward the flagship.
    title_weights = {"T005": 150, "T002": 30, "T006": 30, "T008": 25, "T004": 15}
    for tid, n in title_weights.items():
        boards = LEADERBOARD_TITLES[tid]
        players = eligible.get(tid) or [p for p, c in ctx.items() if c["primary_title"] == tid]
        if not players:
            continue
        for _ in range(n):
            seq += 1
            pid = RNG.choice(players)
            board = RNG.choice(boards)
            is_cheater = pid in cheater_players
            base = RNG.randint(1000, 90000)
            score = base * (12 if is_cheater and RNG.random() < 0.8 else 1)
            # submitted within window, after player registration
            reg = ctx[pid]["reg_dt"].date()
            span = max(1, (WINDOW_END - reg).days)
            sday = reg + timedelta(days=RNG.randint(0, span))
            scores.append({
                "score_id": f"HS{seq:04d}",
                "player_id": pid,
                "title_id": tid,
                "leaderboard_id": board,
                "score_value": score,
                "submitted_at": iso(random_time_on(sday)),
                "is_verified": (not is_cheater) and RNG.random() < 0.9,
                "flagged_for_cheating": bool(is_cheater and RNG.random() < 0.85),
                "_loaded_at": LOADED_AT,
            })
    return scores


# --------------------------------------------------------------------------------------
# Reviews
# --------------------------------------------------------------------------------------

def build_reviews(ctx):
    """~90 store reviews. Rating profile encodes each title's health story."""
    reviews = []
    seq = 0
    # (count, rating weights 1..5) per title
    profile = {
        "T005": (26, [1, 2, 6, 12, 15]),   # flagship: mostly positive, some rage
        "T007": (12, [1, 2, 5, 8, 6]),
        "T008": (12, [1, 1, 3, 8, 12]),    # recent launch: strong early buzz
        "T001": (10, [2, 3, 5, 6, 6]),
        "T002": (8,  [1, 3, 4, 5, 4]),
        "T004": (8,  [1, 2, 4, 6, 5]),
        "T006": (8,  [1, 2, 5, 6, 4]),
        "T003": (6,  [6, 5, 3, 1, 1]),     # underperformer: sour reviews
    }
    for tid, (n, weights) in profile.items():
        players = [p for p, c in ctx.items() if tid in {s["title_id"] for s in c["sessions"]}]
        if not players:
            players = [p for p, c in ctx.items() if c["primary_title"] == tid]
        if not players:
            players = list(ctx.keys())
        platforms = [p for p, _ in TITLE_PLATFORMS[tid]]
        for _ in range(n):
            seq += 1
            pid = RNG.choice(players)
            rating = RNG.choices([1, 2, 3, 4, 5], weights=weights)[0]
            reg = ctx[pid]["reg_dt"].date()
            span = max(1, (WINDOW_END - reg).days)
            sday = reg + timedelta(days=RNG.randint(1, span))
            reviews.append({
                "review_id": f"RV{seq:04d}",
                "player_id": pid,
                "title_id": tid,
                "platform": RNG.choice(platforms),
                "rating": rating,
                "review_text_length": RNG.randint(0, 40) if rating >= 4 else RNG.randint(40, 400),
                "reviewed_at": iso(random_time_on(sday)),
                "is_recommended": rating >= 4,
                "playtime_at_review_hours": round(RNG.uniform(0.5, 120.0), 1),
            })
    return reviews


# --------------------------------------------------------------------------------------
# Marketing spend — weekly per campaign; paid_social looks inefficient
# --------------------------------------------------------------------------------------

def build_marketing_spend():
    """~120 rows: campaign x week. Returns (rows, campaign_index_by_channel)."""
    rows = []
    seq = 0
    campaigns = []  # (campaign_id, title_id, channel)
    # A handful of campaigns; paid_social is the expensive, low-quality one.
    campaign_specs = [
        ("T005", "paid_social",    date(2025, 8, 4),  20),   # long-running, inefficient
        ("T005", "influencer",     date(2025, 11, 3), 8),
        ("T005", "store_featured", date(2026, 2, 9),  6),
        ("T008", "paid_social",    date(2026, 5, 11), 10),   # launch blitz for Batter Up!
        ("T008", "influencer",     date(2026, 5, 18), 6),
        ("T007", "cross_promo",    date(2025, 9, 1),  8),
        ("T007", "paid_social",    date(2026, 1, 5),  6),
        ("T006", "store_featured", date(2025, 11, 24),4),
    ]
    channel_eff = {  # installs-per-1000-impressions and cost profile
        "paid_social":    {"cpm": 12.0, "ctr": 0.010, "cvr": 0.06},  # burns money
        "influencer":     {"cpm": 22.0, "ctr": 0.030, "cvr": 0.18},
        "store_featured": {"cpm": 6.0,  "ctr": 0.040, "cvr": 0.22},
        "cross_promo":    {"cpm": 4.0,  "ctr": 0.035, "cvr": 0.20},
    }
    for tid, channel, start, weeks in campaign_specs:
        seq_c = len(campaigns) + 1
        cid = f"CMP{seq_c:03d}"
        campaigns.append((cid, tid, channel))
        eff = channel_eff[channel]
        for w in range(weeks):
            wk = start + timedelta(weeks=w)
            if wk > WINDOW_END:
                break
            seq += 1
            spend = round(RNG.uniform(1500, 6000) * (1.6 if channel == "paid_social" else 1.0), 2)
            impressions = int(spend / eff["cpm"] * 1000)
            clicks = int(impressions * eff["ctr"] * RNG.uniform(0.8, 1.2))
            installs = int(clicks * eff["cvr"] * RNG.uniform(0.8, 1.2))
            rows.append({
                "campaign_id": cid,
                "title_id": tid,
                "channel": channel,
                "week_start_date": wk.strftime("%Y-%m-%d"),
                "spend_usd": spend,
                "impressions": impressions,
                "clicks": clicks,
                "installs": installs,
            })
    return rows, campaigns


# --------------------------------------------------------------------------------------
# Post-processing: account status, campaign links, dirty data, duplicates
# --------------------------------------------------------------------------------------

def finalize_players(players, ctx, campaigns):
    campaign_by_channel = defaultdict(list)
    for cid, tid, channel in campaigns:
        campaign_by_channel[channel].append(cid)

    for p in players:
        pid = p["player_id"]
        c = ctx[pid]
        # last_login_at = latest session start (or registration if none).
        if c["sessions"]:
            last = max(datetime.strptime(s["session_start_at"], "%Y-%m-%d %H:%M:%S") for s in c["sessions"])
        else:
            last = c["reg_dt"]
        p["last_login_at"] = iso(last)
        days_since = (datetime.combine(WINDOW_END, time(6, 0, 0)) - last).days
        p["account_status"] = ("active" if days_since <= 30 else
                               "dormant" if days_since <= 90 else "churned")
        # Attach an acquisition_campaign_id for paid channels when one exists.
        norm_channel = c["channel"].strip().lower().replace(" ", "_")
        if norm_channel in campaign_by_channel and campaign_by_channel[norm_channel]:
            p["acquisition_campaign_id"] = RNG.choice(campaign_by_channel[norm_channel])
        else:
            p["acquisition_campaign_id"] = None


def apply_dirty_data(players, sessions, cheater_players, ctx):
    """Inject the documented, deliberate imperfections (absolute counts)."""
    # (a) Two spellings of one acquisition channel: 2 rows become 'Paid Social'.
    ps_players = [p for p in players if p["acquisition_channel"] == "paid_social"]
    for p in ps_players[:2]:
        p["acquisition_channel"] = "Paid Social"

    # (b) ~15 mixed-case / whitespace-padded country_code values in sessions.
    dirty_variants = [" us", "Us ", "de ", " DE", "Gb", "jp ", " Kr", "us", "Br ", "GB ",
                      " de", "Jp", "kr", " gb", "US "]
    for i, s in enumerate(sessions[:15]):
        s["country_code"] = dirty_variants[i % len(dirty_variants)]

    # (c) 4 sessions with NULL session_end_at (client crashed before close event).
    for s in sessions[20:24]:
        s["session_end_at"] = None
        s["duration_seconds"] = None
        s["crashed_flag"] = True

    # (d) 2 duration_seconds outliers in the tens of thousands (idle sessions).
    for s, dur in zip(sessions[30:32], [46800, 71400]):
        start = datetime.strptime(s["session_start_at"], "%Y-%m-%d %H:%M:%S")
        s["duration_seconds"] = dur
        s["session_end_at"] = iso(start + timedelta(seconds=dur))

    # (e) Mark cheaters' account_status = 'banned'.
    for p in players:
        if p["player_id"] in cheater_players:
            p["account_status"] = "banned"

    # (f) 3 duplicate session_id rows (whole-row dupes needing dedupe in staging).
    dupes = [dict(sessions[40]), dict(sessions[41]), dict(sessions[42])]
    sessions.extend(dupes)


# --------------------------------------------------------------------------------------
# Build reference seeds
# --------------------------------------------------------------------------------------

def build_titles():
    rows = []
    for tid, name, genre, sub, model, launch, price, team, engine, esrb, live, role in TITLES:
        rows.append({
            "title_id": tid,
            "title_name": name,
            "genre": genre,
            "sub_genre": sub,
            "monetization_model": model,
            "launch_date": launch,
            "list_price_usd": price,
            "internal_team": team,
            "engine": engine,
            "esrb_rating": esrb,
            "is_live_service": bool(live) if isinstance(live, bool) else str(live).lower() == "true",
            "sunset_date": None,  # none formally sunset yet — the demo decision is whether Preserve should be
            "_loaded_at": LOADED_AT,
        })
    return rows


def build_title_platforms():
    rows = []
    for tid, plats in TITLE_PLATFORMS.items():
        for plat, launch in plats:
            slug = TITLE_BY_ID[tid][1].lower().replace(" ", "-").replace("!", "").replace("'", "")
            rows.append({
                "title_id": tid,
                "platform": plat,
                "platform_launch_date": launch,
                "store_page_url": f"https://store.example.com/{plat}/{slug}",
            })
    return rows


def build_platforms():
    return [{"platform": p, "platform_family": PLATFORM_FAMILY[p], "storefront_fee_rate": PLATFORM_FEE_RATE[p]}
            for p in ["steam", "playstation", "xbox", "switch", "ios", "android"]]


# --------------------------------------------------------------------------------------
# Validation — referential integrity + narrative sanity, BEFORE writing anything
# --------------------------------------------------------------------------------------

def validate(all_data):
    players = all_data["raw_players"]
    titles = all_data["raw_titles"]
    skus = all_data["raw_skus"]
    sessions = all_data["raw_play_sessions"]
    transactions = all_data["raw_transactions"]
    scores = all_data["raw_high_scores"]
    reviews = all_data["raw_reviews"]
    title_platforms = all_data["raw_title_platforms"]

    player_ids = {p["player_id"] for p in players}
    title_ids = {t["title_id"] for t in titles}
    sku_ids = {s["sku_id"] for s in skus}
    tp_pairs = {(r["title_id"], r["platform"]) for r in title_platforms}
    reg_by_player = {p["player_id"]: datetime.strptime(p["registered_at"], "%Y-%m-%d %H:%M:%S") for p in players}
    launch_by_tp = {(r["title_id"], r["platform"]): datetime.strptime(r["platform_launch_date"], "%Y-%m-%d")
                    for r in title_platforms}

    errors = []

    def check(cond, msg):
        if not cond:
            errors.append(msg)

    # Referential integrity.
    for s in sessions:
        check(s["player_id"] in player_ids, f"session {s['session_id']} orphan player")
        check(s["title_id"] in title_ids, f"session {s['session_id']} orphan title")
        check((s["title_id"], s["platform"]) in tp_pairs, f"session {s['session_id']} title/platform not released")
        start = datetime.strptime(s["session_start_at"], "%Y-%m-%d %H:%M:%S")
        check(start >= reg_by_player[s["player_id"]], f"session {s['session_id']} before registration")
        check(start >= launch_by_tp[(s["title_id"], s["platform"])], f"session {s['session_id']} before platform launch")
    for t in transactions:
        check(t["player_id"] in player_ids, f"tx {t['transaction_id']} orphan player")
        check(t["title_id"] in title_ids, f"tx {t['transaction_id']} orphan title")
        check(t["sku_id"] is None or t["sku_id"] in sku_ids, f"tx {t['transaction_id']} orphan sku")
    for s in scores:
        check(s["player_id"] in player_ids, f"score {s['score_id']} orphan player")
        check(s["title_id"] in title_ids, f"score {s['score_id']} orphan title")
    for r in reviews:
        check(r["player_id"] in player_ids, f"review {r['review_id']} orphan player")
        check(r["title_id"] in title_ids, f"review {r['review_id']} orphan title")
    for s in skus:
        check(s["title_id"] in title_ids, f"sku {s['sku_id']} orphan title")

    if errors:
        raise SystemExit("VALIDATION FAILED:\n  " + "\n  ".join(errors[:30]) +
                         (f"\n  ... and {len(errors)-30} more" if len(errors) > 30 else ""))
    return True


# --------------------------------------------------------------------------------------
# Sanity reporting (the three Checkpoint-1 proofs), printed at generation time
# --------------------------------------------------------------------------------------

def report(all_data, ctx):
    players = all_data["raw_players"]
    sessions = [s for s in all_data["raw_play_sessions"]]
    transactions = all_data["raw_transactions"]

    print("\n" + "=" * 78)
    print("ROW COUNTS")
    print("=" * 78)
    for name, rows in all_data.items():
        print(f"  {name:24s} {len(rows):>5d}")

    # ---- (a) Retention curve by cohort (session in week N after registration) ----
    print("\n" + "=" * 78)
    print("(a) RETENTION — % of cohort with a session in week 1 / 2 / 4 after registration")
    print("=" * 78)
    reg = {p["player_id"]: datetime.strptime(p["registered_at"], "%Y-%m-%d %H:%M:%S") for p in players}
    by_player_weeks = defaultdict(set)
    logical = {}
    for s in sessions:
        logical[s["session_id"]] = s  # dedupe the 3 duplicate ids
    for s in logical.values():
        start = datetime.strptime(s["session_start_at"], "%Y-%m-%d %H:%M:%S")
        wk = (start - reg[s["player_id"]]).days // 7
        by_player_weeks[s["player_id"]].add(wk)

    def rate(pool, wk):
        if not pool:
            return 0.0
        return 100.0 * sum(1 for p in pool if wk in by_player_weeks[p]) or 0.0

    all_players = list(reg.keys())
    for label, pool in [("ALL", all_players),
                        ("organic", [p for p in all_players if ctx[p]["channel"] == "organic"]),
                        ("paid_social", [p for p in all_players if ctx[p]["channel"] in ("paid_social",)])]:
        n = len(pool)
        def pct(wk):
            return 100.0 * sum(1 for p in pool if wk in by_player_weeks[p]) / n if n else 0
        print(f"  {label:14s} n={n:3d}   wk1={pct(1):5.1f}%   wk2={pct(2):5.1f}%   wk4={pct(4):5.1f}%")

    # ---- (b) Revenue concentration on the whale ----
    print("\n" + "=" * 78)
    print("(b) REVENUE CONCENTRATION")
    print("=" * 78)
    def net(t):
        sign = -1 if t["transaction_type"] in ("refund", "chargeback") else 1
        return sign * t["gross_amount_usd"]
    # Live-service monetisation (drives payer_segment) = iap + season_pass only.
    # DLC/expansion is catalogue revenue (grouped with premium unit sales), so a
    # non_payer can buy DLC and still be a non_payer in the live-service sense.
    live_streams = ("iap", "season_pass")
    net_by_player = defaultdict(float)     # all streams
    iap_by_player = defaultdict(float)     # live-service streams only
    stream_total = defaultdict(float)
    for t in transactions:
        net_by_player[t["player_id"]] += net(t)
        stream_total[t["transaction_type"]] += net(t)
        if t["transaction_type"] in live_streams:
            iap_by_player[t["player_id"]] += t["gross_amount_usd"]
        elif t["transaction_type"] in ("refund", "chargeback"):
            iap_by_player[t["player_id"]] += net(t)  # reversals hit the live-service pool
    total_net = sum(net_by_player.values())
    total_iap = sum(iap_by_player.values())
    whale = [p for p, c in ctx.items() if c["segment"] == "whale"][0]
    print(f"  transactions:                   {len(transactions)}")
    print(f"  total net revenue (all tx):     ${total_net:,.2f}")
    print(f"  total live-service (IAP) net:   ${total_iap:,.2f}")
    print(f"  whale ({whale}) IAP net:          ${iap_by_player[whale]:,.2f}")
    print(f"  whale share of IAP net:         {100*iap_by_player[whale]/total_iap if total_iap else 0:5.1f}%")
    print("  net revenue by stream:")
    for st in ("premium_purchase", "iap", "season_pass", "dlc", "refund", "chargeback"):
        print(f"    {st:18s} ${stream_total[st]:9,.2f}")
    print("  live-service (IAP) net by segment:")
    for seg in ("whale", "dolphin", "minnow", "non_payer"):
        n = sum(1 for c in ctx.values() if c["segment"] == seg)
        seg_iap = sum(iap_by_player[p] for p, c in ctx.items() if c["segment"] == seg)
        print(f"    {seg:10s} n={n:3d}   IAP net=${seg_iap:9,.2f}")

    # ---- (c) Underperformer session drought ----
    print("\n" + "=" * 78)
    print("(c) UNDERPERFORMER SESSION DROUGHT (Preserve, T003)")
    print("=" * 78)
    up = [s for s in logical.values() if s["title_id"] == UNDERPERFORMER_ID]
    print(f"  total Preserve sessions:        {len(up)}")
    last = max((datetime.strptime(s['session_start_at'], '%Y-%m-%d %H:%M:%S') for s in up), default=None)
    print(f"  last Preserve session:          {last}")
    print(f"  sessions in last 2 months:      {sum(1 for s in up if datetime.strptime(s['session_start_at'],'%Y-%m-%d %H:%M:%S').date() >= UNDERPERFORMER_QUIET_AFTER)}")
    # Sessions by title (portfolio shape).
    by_title = Counter(s["title_id"] for s in logical.values())
    print("\n  sessions by title:")
    for tid, _n in sorted(by_title.items(), key=lambda x: -x[1]):
        name = TITLE_BY_ID[tid][1]
        print(f"    {name:16s} {by_title[tid]:4d}  ({100*by_title[tid]/len(logical):4.1f}%)  [{TITLE_ROLE[tid]}]")


# --------------------------------------------------------------------------------------
# CSV writer
# --------------------------------------------------------------------------------------

def write_csv(name, rows):
    if not rows:
        return
    # Drop scratch fields.
    clean = []
    for r in rows:
        clean.append({k: v for k, v in r.items() if not k.startswith("_day")})
    fieldnames = list(clean[0].keys())
    path = os.path.join(SEEDS_DIR, f"{name}.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in clean:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------

def main():
    os.makedirs(SEEDS_DIR, exist_ok=True)

    players, ctx = build_players()
    assign_segments(ctx)
    releases, release_index = build_releases()
    assign_primary_titles(ctx)

    seq = SeqCounter()
    sessions = generate_sessions(ctx, release_index, seq)
    premium_sessions, ownership = build_premium_catalog(ctx, release_index, seq)
    sessions.extend(premium_sessions)
    # Attach sessions back to ctx for downstream generators.
    for s in sessions:
        ctx[s["player_id"]]["sessions"].append(s)

    skus = build_skus()
    transactions = build_transactions(ctx, skus, ownership)

    # Cheaters: pick 2 players who submit scores and flag/ban them.
    score_candidates = sorted([p for p, c in ctx.items()
                               if any(s["title_id"] in LEADERBOARD_TITLES for s in c["sessions"])])
    cheater_players = set(score_candidates[:2]) if len(score_candidates) >= 2 else set(list(ctx.keys())[:2])

    scores = build_high_scores(ctx, cheater_players)
    reviews = build_reviews(ctx)
    marketing, campaigns = build_marketing_spend()

    finalize_players(players, ctx, campaigns)
    apply_dirty_data(players, sessions, cheater_players, ctx)

    all_data = {
        "raw_platforms": build_platforms(),
        "raw_titles": build_titles(),
        "raw_title_platforms": build_title_platforms(),
        "raw_skus": skus,
        "raw_players": players,
        "raw_releases": releases,
        "raw_play_sessions": sessions,
        "raw_transactions": transactions,
        "raw_high_scores": scores,
        "raw_reviews": reviews,
        "raw_marketing_spend": marketing,
    }

    validate(all_data)
    for name, rows in all_data.items():
        write_csv(name, rows)
    report(all_data, ctx)
    print("\nAll seeds written to", os.path.abspath(SEEDS_DIR))


if __name__ == "__main__":
    main()
