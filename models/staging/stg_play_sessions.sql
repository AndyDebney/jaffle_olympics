with
    source as (select * from {{ ref("raw_play_sessions") }}),

    renamed as (
        select
            session_id,
            player_id,
            title_id,
            platform as platform_id,
            cast(session_start_at as timestamp_ntz) as session_start_at,
            cast(session_end_at as timestamp_ntz) as session_end_at,
            duration_seconds::integer as duration_seconds,
            device_model,
            app_version,
            cast(levels_completed as integer) as levels_completed,
            cast(crashed_flag as boolean) as crashed_flag,
            network_type,
            cast(_loaded_at as timestamp_ntz) as loaded_at,
            {{ clean_country_code("country_code") }} as country_code
        from source
    ),

    -- The raw feed contains 3 duplicate session_id rows. Keep exactly one row per
    -- session_id.
    deduplicated as (
        select *
        from renamed
        qualify
            row_number() over (
                partition by session_id order by loaded_at, session_start_at
            )
            = 1
    )

select *
from deduplicated
