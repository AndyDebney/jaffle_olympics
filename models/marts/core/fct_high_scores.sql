
-- One row per leaderboard submission. Cheat-flagged submissions are kept (and
-- counted) but
-- are excluded from competitive ranking: ranks and percentiles are computed only among
-- non-flagged submissions on each leaderboard.
with
    scores as (select * from {{ ref("stg_high_scores") }}),

    ranked as (
        select
            *,
            -- Rank/percentile within each leaderboard, among legitimate (non-flagged)
            -- rows only.
            case
                when not flagged_for_cheating
                then
                    rank() over (
                        partition by leaderboard_id, flagged_for_cheating
                        order by score_value desc
                    )
            end as leaderboard_rank,
            case
                when not flagged_for_cheating
                then
                    percent_rank() over (
                        partition by leaderboard_id, flagged_for_cheating
                        order by score_value asc
                    )
            end as score_percentile
        from scores
    )

select
    score_id::varchar as score_id,
    player_id::varchar as player_id,
    title_id::varchar as title_id,
    leaderboard_id::varchar as leaderboard_id,
    score_value::decimal(38, 0) as score_value,
    submitted_at as submitted_at,
    submitted_at::date as submitted_date,
    is_verified::boolean as is_verified,
    flagged_for_cheating::boolean as flagged_for_cheating,
    leaderboard_rank::integer as leaderboard_rank,
    round(score_percentile, 4)::decimal(6, 4) as score_percentile
from ranked
