-- Reference queries (compiled by `dbt compile`, not materialized) that mirror the three
-- Checkpoint-1 sanity checks against the built models. Handy for validating a fresh build.

-- (a) Retention curve by channel: week-1/2/4 return rates with cohort sizes exposed.
with retention as (
    select
        acquisition_channel,
        week_offset,
        sum(retained_players)                                    as retained_players,
        sum(cohort_size)                                         as cohort_players,
        round(sum(retained_players) / nullif(sum(cohort_size), 0), 3) as retention_rate
    from {{ ref('mart_player_retention') }}
    where week_offset in (1, 2, 4) and is_observable
    group by 1, 2
    order by 1, 2
)
select * from retention

-- (b) Revenue concentration — top players by lifetime IAP spend:
-- select player_id, payer_segment, live_service_net_usd, lifetime_net_revenue_usd
-- from {{ ref('dim_players') }} order by live_service_net_usd desc limit 10;

-- (c) Underperformer drought — sessions by title with last-played recency:
-- select title_id, title_name, lifecycle_stage, lifetime_sessions, days_since_last_session
-- from {{ ref('dim_titles') }} order by lifetime_sessions desc;
