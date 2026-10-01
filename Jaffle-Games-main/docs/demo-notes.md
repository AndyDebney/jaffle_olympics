# Demo notes — what the data supports and where to click

This project's seed data is engineered so specific analytics stories land clearly at small
scale. Use this as a run sheet when demoing. All figures reflect the deterministic generator
(`setup/generate_seeds.py`, `SEED = 20260805`); regenerating reproduces them exactly.

Analysis "as of" date: **2026-08-05** (the close of the 12-month history window).

## 1. The flagship carries the portfolio

**Griddle Royale** (`T005`, free-to-play battle royale) is ~44% of all sessions and the clear #1
title by revenue — roughly 3x the next title.

- Click: `mart_title_performance` filtered to `Griddle Royale`, versus the rest of the portfolio.
- Chart: monthly active players by title from `mart_title_performance` — one dominant line, a mid
  line (Marmalade Siege), a recent riser (Batter Up!), several low declining lines, and one flat.

## 2. One whale is about a third of in-app revenue

Player **`P025`** alone is ~30% of live-service (IAP) net revenue. Payer segments are fixed
counts: **1 whale, 4 dolphins, 14 minnows, 101 non-payers**.

- Click: `dim_players` sorted by `live_service_net_usd` desc — `P025` sits far above everyone.
- Click: `mart_studio_kpis.top_player_revenue_share` for the monthly concentration.
- Note the definition: `payer_segment` is driven by IAP + season-pass spend only. Premium unit
  sales and DLC feed `lifetime_net_revenue_usd` but never make someone a "payer" — so a
  `non_payer` can still have bought a premium title.

## 3. The sunset candidate

**Preserve** (`T003`, premium puzzle) has ~15 sessions across the whole year and **none after
February 2026** — a visible drought against a 12-month window.

- Click: `dim_titles` where `lifecycle_stage = 'sunset_candidate'` → Preserve, with a large
  `days_since_last_session`.
- Chart: Preserve's line in `mart_title_performance` flatlines to zero mid-year while others
  continue. Poor reviews back it up (`avg_review_rating` is the lowest in the portfolio).

## 4. A recent launch still spiking

**Batter Up!** (`T008`) launched **2026-05-15** and is intentionally pre-revenue — its story is
the engagement spike, not monetization yet.

- Click: `dim_titles` where `lifecycle_stage = 'launch_window'`.
- Chart: Batter Up! appears only in the final months of `mart_title_performance`, climbing.

## 5. Acquisition channel quality — paid_social is burning money

`paid_social` cohorts retain far worse than `organic` (roughly 20% vs 55%+ week-1 return), and
`paid_social` is the most expensive channel per install.

- Click: `mart_player_retention` — compare `retention_rate` across `acquisition_channel` at
  `week_offset` 1, 2 and 4. `cohort_size` is on every row so the small denominators are explicit.
- Cross-reference: `mart_studio_kpis.blended_cac_usd` and the marketing spend behind
  campaign `CMP001` (a long-running, inefficient paid_social campaign).

## 6. A release that regressed, then rolled back

Griddle Royale **`v4.0.0`** (major, 2026-03-10, an "Engine 5 upgrade") shipped severe crash
regressions and dropped engagement. **`v4.0.1`** (hotfix, 2026-03-14, `is_rollback = true`)
reverted it.

- Click: `mart_live_ops_health` where `regressed_release = true` → `v4.0.0` shows a negative
  `session_count_delta`, a jump in `crash_rate_10d_after`, and an over-budget dev-day variance.
  The rollback hotfix follows four days later.
- Contrast with the good story: `v3.2.0` (content drop, 2025-11-15) shows a positive engagement
  delta — the hand-placed 10-day lift.

## 7. Data-quality handling on stage (optional deep-dive)

If the audience is technical, show the raw-to-staging cleanup: `raw_play_sessions` has 3
duplicate `session_id`s, ~15 dirty `country_code` values, 4 null-end crash sessions and 2 idle
duration outliers; `raw_transactions` stores refunds as positive amounts in America/New_York
time. Walk `stg_play_sessions` (dedupe), the `clean_country_code` / `to_utc` / `signed_net_amount`
macros, and the singular tests in `tests/` that guard each rule. Full inventory in
[`setup/README.md`](../setup/README.md).

## Caveats to pre-empt

- **Small denominators are intentional.** Retention percentages sit on single-digit cohorts;
  `cohort_size` and `has_sufficient_volume` are surfaced everywhere so this is honest, not hidden.
- **Whale share vs. per-segment targets.** Dolphin/minnow spend is tuned slightly above the
  original brief so the whale lands near one-third of IAP; adjust `SEGMENT_REVENUE_TARGET` in the
  generator if you prefer the reverse trade-off.
