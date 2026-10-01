-- Release health for live ops. One row per release: the matched 10-day before/after
-- windows
-- for engagement (from fct_releases) plus net revenue per active player over the same
-- windows,
-- and a single regressed_release flag combining engagement, crash and spend-overrun
-- signals.
with
    releases as (select * from {{ ref("fct_releases") }}),

    titles as (
        select title_id, title_name, lifecycle_stage from {{ ref("dim_titles") }}
    ),

    -- Net revenue in the matched windows around each release.
    revenue as (
        select
            r.release_id,
            sum(
                case
                    when t.transaction_at < r.released_at then t.net_amount_usd else 0
                end
            ) as net_revenue_10d_before,
            sum(
                case
                    when t.transaction_at >= r.released_at then t.net_amount_usd else 0
                end
            ) as net_revenue_10d_after
        from releases as r
        left join
            {{ ref("fct_transactions") }} as t
            on r.title_id = t.title_id
            and t.transaction_at >= dateadd('day', -10, r.released_at)
            and t.transaction_at < dateadd('day', 10, r.released_at)
        group by 1
    )

select
    releases.release_id,
    releases.title_id,
    titles.title_name,
    titles.lifecycle_stage,
    releases.app_version,
    releases.released_date,
    releases.release_type,
    releases.is_rollback,

    -- Engineering execution.
    releases.dev_days_estimated,
    releases.dev_days_actual,
    releases.dev_days_variance,
    releases.dev_days_variance_pct,
    releases.is_over_budget,
    releases.qa_bug_count,

    -- Engagement, matched windows.
    releases.sessions_10d_before,
    releases.sessions_10d_after,
    releases.session_count_delta,
    releases.active_players_10d_before,
    releases.active_players_10d_after,
    releases.avg_minutes_10d_before,
    releases.avg_minutes_10d_after,
    releases.crash_rate_10d_before,
    releases.crash_rate_10d_after,
    releases.made_engagement_worse,

    (
        releases.active_players_10d_after - releases.active_players_10d_before
    ) as active_players_delta,
    round(
        releases.avg_minutes_10d_after - releases.avg_minutes_10d_before, 2
    ) as avg_minutes_delta,
    round(
        releases.crash_rate_10d_after - releases.crash_rate_10d_before, 4
    ) as crash_rate_delta,

    -- Revenue per active player, matched windows.
    round(coalesce(revenue.net_revenue_10d_before, 0), 2) as net_revenue_10d_before,
    round(coalesce(revenue.net_revenue_10d_after, 0), 2) as net_revenue_10d_after,
    round(
        coalesce(revenue.net_revenue_10d_before, 0)
        / nullif(releases.active_players_10d_before, 0),
        2
    ) as net_rev_per_active_before,
    round(
        coalesce(revenue.net_revenue_10d_after, 0)
        / nullif(releases.active_players_10d_after, 0),
        2
    ) as net_rev_per_active_after,

    -- Overall regression flag: engagement fell, crashes spiked, or the build shipped
    -- badly late.
    (
        releases.made_engagement_worse
        or releases.crash_rate_10d_after > 0.15
        or (releases.is_over_budget and releases.dev_days_variance_pct > 0.30)
    ) as regressed_release
from releases
left join titles on releases.title_id = titles.title_id
left join revenue on releases.release_id = revenue.release_id
order by 6
