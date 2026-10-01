-- One row per title, enriched with lifecycle stage. Stage is derived from age plus
-- recent
-- engagement so the underperformer surfaces as a sunset_candidate and the aging premium
-- back-catalogue surfaces as declining. Thresholds come from project vars.
with
    titles as (select * from {{ ref("stg_titles") }}),

    activity as (select * from {{ ref("int_title_activity") }}),

    platform_rollup as (
        select
            title_id,
            count(*) as platform_count,
            min(platform_launch_date) as earliest_platform_launch_date
        from {{ ref("stg_title_platforms") }}
        group by 1
    ),

    joined as (
        select
            titles.*,
            activity.lifetime_sessions,
            activity.lifetime_players,
            activity.first_session_at,
            activity.last_session_at,
            activity.sessions_last_60d,
            activity.active_players_last_90d,
            activity.days_since_last_session,
            activity.avg_review_rating,
            activity.review_count,
            activity.recommend_rate,
            platform_rollup.platform_count,
            platform_rollup.earliest_platform_launch_date,
            datediff(
                'day',
                titles.launch_date,
                cast('{{ var("analysis_as_of_date") }}' as date)
            ) as days_since_launch
        from titles
        left join activity on titles.title_id = activity.title_id
        left join platform_rollup on titles.title_id = platform_rollup.title_id
    )

select
    cast(title_id as varchar) as title_id,
    cast(title_name as varchar) as title_name,
    cast(genre as varchar) as genre,
    cast(sub_genre as varchar) as sub_genre,
    cast(monetization_model as varchar) as monetization_model,
    cast(is_live_service as boolean) as is_live_service,
    cast(launch_date as date) as launch_date,
    cast(list_price_usd as number(12,2)) as list_price_usd,
    cast(internal_team as varchar) as internal_team,
    cast(engine as varchar) as engine,
    cast(esrb_rating as varchar) as esrb_rating,
    cast(sunset_date as date) as sunset_date,
    cast(days_since_launch as integer) as days_since_launch,
    cast(earliest_platform_launch_date as date) as earliest_platform_launch_date,
    cast(first_session_at as timestamp_ntz) as first_session_at,
    cast(last_session_at as timestamp_ntz) as last_session_at,
    cast(days_since_last_session as integer) as days_since_last_session,

    cast(coalesce(platform_count,0) as integer) as platform_count,

    -- Lifecycle stage. Order matters: launch first, then the sunset test, then
    -- activity.
    cast(
        (
            case
                when days_since_launch <= 90
                then 'launch_window'
                when
                    coalesce(days_since_last_session, 9999) > 60 and days_since_launch > 365
                then 'sunset_candidate'
                when days_since_launch <= 365
                then 'growth'
                when
                    coalesce(active_players_last_90d, 0)
                    >= {{ var("min_active_players_threshold") }}
                then 'mature'
                else 'declining'
            end
        ) as varchar
    ) as lifecycle_stage,

    cast(coalesce(lifetime_sessions,0) as integer) as lifetime_sessions,
    cast(coalesce(lifetime_players,0) as integer) as lifetime_players,
    cast(coalesce(sessions_last_60d,0) as integer) as sessions_last_60d,
    cast(coalesce(active_players_last_90d,0) as integer) as active_players_last_90d,
    cast(round(avg_review_rating,2) as number(4,2)) as avg_review_rating,
    cast(coalesce(review_count,0) as integer) as review_count,
    cast(round(recommend_rate,4) as number(5,4)) as recommend_rate
from joined
