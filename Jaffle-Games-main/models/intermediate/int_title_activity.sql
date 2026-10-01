-- Per-title engagement rollup used by dim_titles to derive lifecycle stage and recency.
-- Recency windows are measured against the fixed analysis "as of" date so results are stable.

with sessions as (
    select * from {{ ref('int_play_sessions_enriched') }}
),

reviews as (
    select
        title_id,
        avg(rating)                       as avg_review_rating,
        count(*)                          as review_count,
        avg(case when is_recommended then 1.0 else 0.0 end) as recommend_rate
    from {{ ref('stg_reviews') }}
    group by 1
),

session_rollup as (
    select
        title_id,
        count(*)                                                       as lifetime_sessions,
        count(distinct player_id)                                      as lifetime_players,
        min(session_start_at)                                          as first_session_at,
        max(session_start_at)                                          as last_session_at,
        count_if(session_start_at >= dateadd('day', -60, cast('{{ var("analysis_as_of_date") }}' as date))) as sessions_last_60d,
        count(distinct case
            when session_start_at >= dateadd('day', -90, cast('{{ var("analysis_as_of_date") }}' as date))
            then player_id end)                                        as active_players_last_90d
    from sessions
    group by 1
)

select
    session_rollup.title_id,
    session_rollup.lifetime_sessions,
    session_rollup.lifetime_players,
    session_rollup.first_session_at,
    session_rollup.last_session_at,
    session_rollup.sessions_last_60d,
    session_rollup.active_players_last_90d,
    reviews.avg_review_rating,
    reviews.review_count,
    reviews.recommend_rate,
    datediff('day', session_rollup.last_session_at, cast('{{ var("analysis_as_of_date") }}' as date)) as days_since_last_session
from session_rollup
left join reviews on session_rollup.title_id = reviews.title_id
