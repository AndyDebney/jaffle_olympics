# Seed generation — Jaffle Games

The CSVs in `seeds/` are produced deterministically by [`generate_seeds.py`](generate_seeds.py).
The script is hand-authored rather than sampled from distributions: at a few hundred rows the
demo narrative only survives if cohorts, payer segments, and patch effects are placed
deliberately. **The CSVs are the source of truth** — hand-edit a single row to sharpen a
story if you like; re-run the script only when you want to regenerate or rescale everything.

## Regenerating

```bash
python3 setup/generate_seeds.py
```

Requires Python 3 and pandas is *not* needed (standard library only). A fixed random seed
(`SEED = 20260805`) makes output byte-identical on every run. Row counts, the history window,
payer targets, and data-quality knobs are all constants at the top of the script.

## History window

All events fall between **2025-08-01 and 2026-08-05** (12 months). Do not widen this — with a
few hundred sessions, a longer window leaves every chart too sparse to read.

## The stories the data is engineered to tell

- **Flagship carries the portfolio.** Griddle Royale is ~44% of all sessions and the clear #1
  title by revenue.
- **One whale ≈ a third of in-app revenue.** Player `P025` alone is ~30% of live-service (IAP)
  net revenue. Payer segments are fixed counts: 1 whale, 4 dolphins, 14 minnows, 101 non-payers.
- **A sunset candidate.** Preserve (`T003`) has ~15 sessions all year and none after February —
  a visible drought against a 12-month window.
- **A recent launch still spiking.** Batter Up! (`T008`) launched 2026-05-15 and is pre-revenue
  by design; its story is the engagement spike, not monetization.
- **Acquisition channel quality gap.** `paid_social` cohorts retain far worse than `organic`
  (roughly 20% vs 55%+ week-1 return) and `paid_social` campaigns are the most expensive per
  install — a "burning money" story for the marketing review.
- **A release that regressed, then rolled back.** Griddle Royale `v4.0.0` (major, 2026-03-10)
  ships severe crash regressions and drops engagement; `v4.0.1` (hotfix, 2026-03-14,
  `is_rollback = true`) reverts it. A content drop (`v3.2.0`, 2025-11-15) lifts sessions instead.

## Deliberate data-quality imperfections

Real raw data is dirty; the staging layer demonstrates handling it. Counts are absolute (a
percentage of ~600 rounds to nothing).

| # | Imperfection | Where | Count | Handled in |
|---|---|---|---|---|
| 1 | Duplicate `session_id` rows (whole-row dupes) | `raw_play_sessions` | 3 | `stg_play_sessions` (dedupe via `qualify row_number`) |
| 2 | Mixed-case / whitespace-padded `country_code` | `raw_play_sessions` | ~15 | `stg_*` (`clean_country_code` macro: trim + upper) |
| 3 | `NULL` `session_end_at` (client crashed before close) | `raw_play_sessions` | 4 | `fct_play_sessions.is_valid_session` excludes them |
| 4 | `duration_seconds` idle outliers (tens of thousands of seconds) | `raw_play_sessions` | 2 | `fct_play_sessions.is_valid_session` excludes them (> 6h) |
| 5 | Refunds/chargebacks stored as **positive** amounts | `raw_transactions` | all reversals | `int_transactions` / `signed_net_amount` macro negates them |
| 6 | Two spellings of one channel: `paid_social` and `Paid Social` | `raw_players` | 2 | `stg_players` normalizes to `paid_social` |
| 7 | Transaction timestamps in **America/New_York**, everything else UTC | `raw_transactions` | all rows | `stg_transactions` / `to_utc` macro; guarded by a singular test |

## Rescaling

Change the row-count and target constants at the top of the script (e.g. `N_PLAYERS`,
`TARGET_SESSIONS`, `SEGMENT_REVENUE_TARGET`, `PREMIUM_CATALOG`). The generator validates
referential integrity and prints three sanity checks (retention by cohort, revenue
concentration, the underperformer's drought) before writing any CSV — if a change breaks the
narrative, you will see it in that output. Keep the dataset small on purpose: if a mart looks
sparse, prefer a coarser grain or redistributing rows over adding more.
