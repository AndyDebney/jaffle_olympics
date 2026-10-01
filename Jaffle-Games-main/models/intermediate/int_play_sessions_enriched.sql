-- Session-grain enrichment reused by fct_play_sessions and the retention marts:
--   * duration in minutes and a validity flag that excludes idle outliers / null-end crashes
--   * the release in effect for the title at session time
--   * the player's registration cohort month and the week offset from registration (retention)

with sessions as (
    select * from {{ ref('stg_play_sessions') }}
),

players as (
    select player_id, registered_at from {{ ref('stg_players') }}
),

releases as (
    select release_id, title_id, released_at, app_version from {{ ref('stg_releases') }}
),

joined as (
    select
        s.session_id,
        s.player_id,
        s.title_id,
        s.platform_id,
        s.session_start_at,
        s.session_end_at,
        s.duration_seconds,
        s.device_model,
        s.app_version,
        s.country_code,
        s.levels_completed,
        s.crashed_flag,
        s.network_type,
        p.registered_at,
        r.release_id     as release_id_in_effect,
        r.app_version    as release_version_in_effect
    from sessions as s
    inner join players as p
        on s.player_id = p.player_id
    -- Release in effect = the most recent release for this title on/before the session start.
    left join releases as r
        on s.title_id = r.title_id
       and s.session_start_at >= r.released_at
    qualify row_number() over (
        partition by s.session_id
        order by r.released_at desc nulls last
    ) = 1
)

select
    session_id,
    player_id,
    title_id,
    platform_id,
    session_start_at,
    session_end_at,
    duration_seconds,
    device_model,
    app_version,
    country_code,
    levels_completed,
    crashed_flag,
    network_type,
    release_id_in_effect,
    release_version_in_effect,
    registered_at,

    round(duration_seconds / 60.0, 2) as duration_minutes,

    -- A session is valid for engagement metrics when it closed cleanly and has a sane length.
    -- Excludes the 4 null-end (crash) rows and the 2 multi-hour idle outliers (> 6 hours).
    (duration_seconds is not null and duration_seconds between 1 and 21600) as is_valid_session,

    cast(date_trunc('month', registered_at) as date) as registration_cohort_month,
    cast(date_trunc('month', session_start_at) as date) as session_month,
    date_trunc('week', session_start_at)::date as session_week,

    -- Whole weeks elapsed between registration and the session (0 = registration week).
    floor(datediff('day', registered_at, session_start_at) / 7) as week_offset_from_registration,

    (dayofweekiso(session_start_at) in (6, 7)) as is_weekend_session

from joined
