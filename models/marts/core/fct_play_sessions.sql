-- One row per play session. Grain and keys come straight from the enriched
-- intermediate;
-- this model exposes the conformed, typed session fact with the release in effect and
-- the
-- retention week offset already computed.
with sessions as (select * from {{ ref("int_play_sessions_enriched") }})

select
    session_id::varchar as session_id,
    player_id::varchar as player_id,
    title_id::varchar as title_id,
    platform_id::varchar as platform_id,
    release_id_in_effect::varchar as release_id_in_effect,

    session_start_at::timestamp_ntz as session_start_at,
    session_end_at::timestamp_ntz as session_end_at,
    session_start_at::date as session_date,
    session_month::date as session_month,
    session_week::date as session_week,

    duration_seconds::integer as duration_seconds,
    duration_minutes::number(12, 2) as session_duration_minutes,
    is_valid_session::boolean as is_valid_session,

    levels_completed::integer as levels_completed,
    cast(crashed_flag as boolean) as crashed_flag,
    network_type::varchar as network_type,
    device_model::varchar as device_model,
    app_version::varchar as app_version,
    release_version_in_effect::varchar as release_version_in_effect,
    country_code::varchar as country_code,

    registration_cohort_month::date as registration_cohort_month,
    week_offset_from_registration::integer as week_offset_from_registration,
    is_weekend_session::boolean as is_weekend_session
from sessions
