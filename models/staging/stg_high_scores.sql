with 
    source as (select * from {{ ref("raw_high_scores") }}),

    renamed as (
        select
            score_id,
            player_id,
            title_id,
            leaderboard_id,
            cast(score_value as decimal(38, 0)) as score_value,
            cast(submitted_at as timestamp) as submitted_at,
            cast(is_verified as boolean) as is_verified,
            cast(flagged_for_cheating as boolean) as flagged_for_cheating,
            cast(_loaded_at as timestamp) as loaded_at
        from source
    )

select *
from renamed
