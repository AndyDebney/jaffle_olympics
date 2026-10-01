-- Per-player engagement rollup used by dim_players: lifetime session counts, first/last
-- session, favorite title (most-played by valid sessions) and primary platform.

with sessions as (
    select * from {{ ref('int_play_sessions_enriched') }}
),

base as (
    select
        player_id,
        count(*)                                          as lifetime_sessions,
        count_if(is_valid_session)                        as lifetime_valid_sessions,
        sum(case when is_valid_session then duration_minutes else 0 end) as lifetime_play_minutes,
        count(distinct title_id)                          as distinct_titles_played,
        MIN(session_start_at)                             as first_session_at,
        max(session_start_at)                             as last_session_at
    from sessions
    group by 1
),

favorite_title as (
    select player_id, title_id as favorite_title_id
    from sessions
    group by player_id, title_id
    qualify row_number() over (
        partition by player_id order by count(*) desc, title_id asc
    ) = 1
),

primary_platform as (
    select player_id, platform_id as primary_platform_id
    from sessions
    group by player_id, platform_id
    qualify row_number() over (
        partition by player_id order by count(*) desc, platform_id asc
    ) = 1
)

select
    base.player_id,
    base.lifetime_sessions,
    base.lifetime_valid_sessions,
    base.lifetime_play_minutes,
    base.distinct_titles_played,
    base.first_session_at,
    base.last_session_at,
    favorite_title.favorite_title_id,
    primary_platform.primary_platform_id
from base
left join favorite_title on base.player_id = favorite_title.player_id
left join primary_platform on base.player_id = primary_platform.player_id
