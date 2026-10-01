-- One row per release with development variance and a matched-window engagement delta:
-- sessions, active players, crash rate and average session length in the 10 days
-- before vs
-- the 10 days after the release. This is the backbone of live-ops health analysis and
-- makes
-- the engineered "bad major -> rollback" story measurable.
with
    releases as (select * from {{ ref("stg_releases") }}),

    sessions as (
        select
            title_id,
            player_id,
            session_start_at,
            crashed_flag,
            is_valid_session,
            duration_minutes
        from {{ ref("int_play_sessions_enriched") }}
    ),

    joined as (
        select
            r.release_id,
            r.title_id,
            r.app_version,
            r.released_at,
            r.release_type,
            r.is_rollback,
            r.dev_days_estimated,
            r.dev_days_actual,
            r.qa_bug_count,
            s.player_id,
            s.crashed_flag,
            s.is_valid_session,
            s.duration_minutes,
            (
                s.session_start_at is not null and s.session_start_at < r.released_at
            ) as is_pre,
            (
                s.session_start_at is not null and s.session_start_at >= r.released_at
            ) as is_post
        from releases as r
        left join
            sessions as s
            on r.title_id = s.title_id
            and s.session_start_at >= dateadd('day', -10, r.released_at)
            and s.session_start_at < dateadd('day', 10, r.released_at)
    ),

    agg as (
        select
            release_id,
            title_id,
            app_version,
            released_at,
            release_type,
            is_rollback,
            dev_days_estimated,
            dev_days_actual,
            qa_bug_count,
            count_if(is_pre) as sessions_10d_before,
            count_if(is_post) as sessions_10d_after,
            count(
                distinct case when is_pre then player_id end
            ) as active_players_10d_before,
            count(
                distinct case when is_post then player_id end
            ) as active_players_10d_after,
            count_if(is_pre and crashed_flag) as crashes_10d_before,
            count_if(is_post and crashed_flag) as crashes_10d_after,
            avg(
                case when is_pre and is_valid_session then duration_minutes end
            ) as avg_minutes_10d_before,
            avg(
                case when is_post and is_valid_session then duration_minutes end
            ) as avg_minutes_10d_after
        from joined
        group by 1, 2, 3, 4, 5, 6, 7, 8, 9
    )

select
    release_id::varchar as release_id,
    title_id::varchar as title_id,
    app_version::varchar as app_version,
    released_at::timestamp_ntz as released_at,
    released_at::date as released_date,
    release_type::varchar as release_type,
    is_rollback::boolean as is_rollback,

    dev_days_estimated::integer as dev_days_estimated,
    dev_days_actual::INTEGER as dev_days_actual,
    qa_bug_count::integer as qa_bug_count,

    sessions_10d_before::integer as sessions_10d_before,
    sessions_10d_after::integer as sessions_10d_after,
    active_players_10d_before::integer as active_players_10d_before,
    active_players_10d_after::integer as active_players_10d_after,

    (dev_days_actual - dev_days_estimated)::integer as dev_days_variance,
    round(
        (dev_days_actual - dev_days_estimated) / nullif(dev_days_estimated, 0), 4
    )::number(9, 4) as dev_days_variance_pct,
    (dev_days_actual > dev_days_estimated)::boolean as is_over_budget,
    (sessions_10d_after - sessions_10d_before)::integer as session_count_delta,

    round(crashes_10d_before / nullif(sessions_10d_before, 0), 4)::number(
        6, 4
    ) as crash_rate_10d_before,
    round(crashes_10d_after / nullif(sessions_10d_after, 0), 4)::number(
        6, 4
    ) as crash_rate_10d_after,
    round(avg_minutes_10d_before, 2)::number(12, 2) as avg_minutes_10d_before,
    round(avg_minutes_10d_after, 2)::number(12, 2) as avg_minutes_10d_after,

    -- Did the release make things worse? Fewer post-release sessions or a higher
    -- crash rate.
    (
        (sessions_10d_after - sessions_10d_before) < 0
        or coalesce(crashes_10d_after / nullif(sessions_10d_after, 0), 0)
        > coalesce(crashes_10d_before / nullif(sessions_10d_before, 0), 0) + 0.05
    )::boolean as made_engagement_worse
from agg
