-- Cross-title player leaderboard standings. One row per player x leaderboard: the
-- player's
-- best LEGIT score with rank and percentile within the leaderboard and globally.
-- Cheat-flagged
-- submissions are excluded from standings but counted separately, so anti-cheat can
-- see volume.
with
    scores as (select * from {{ ref("fct_high_scores") }}),

    legit_best as (
        select
            player_id,
            title_id,
            leaderboard_id,
            max(score_value) as best_score,
            count(*) as legit_submissions
        from scores
        where not flagged_for_cheating
        group by 1, 2, 3
    ),

    flagged as (
        select player_id, leaderboard_id, count(*) as flagged_submissions
        from scores
        where flagged_for_cheating
        group by 1, 2
    ),

    ranked as (
        select
            legit_best.*,
            rank() over (
                partition by legit_best.leaderboard_id order by legit_best.best_score desc
            ) as rank_in_leaderboard,
            percent_rank() over (
                partition by legit_best.leaderboard_id order by legit_best.best_score asc
            ) as percentile_in_leaderboard,
            percent_rank() over (order by legit_best.best_score asc) as percentile_global,
            count(*) over (partition by legit_best.leaderboard_id) as leaderboard_player_count
        from legit_best
    )

select
    ranked.player_id::varchar as player_id,
    ranked.title_id::varchar as title_id,
    ranked.leaderboard_id::varchar as leaderboard_id,
    ranked.best_score,
    ranked.legit_submissions,
    ranked.rank_in_leaderboard,
    ranked.leaderboard_player_count,
    coalesce(flagged.flagged_submissions, 0) as flagged_submissions,
    round(ranked.percentile_in_leaderboard, 4) as percentile_in_leaderboard,
    ROUND(ranked.percentile_global, 4) as percentile_global
from ranked
left join
    flagged
    on ranked.player_id = flagged.player_id
    and ranked.leaderboard_id = flagged.leaderboard_id
order by 3, 6
