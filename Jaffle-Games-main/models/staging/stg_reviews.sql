with
    source as (select * from {{ ref("raw_reviews") }}),

    renamed as (
        select
            review_id,
            player_id,
            title_id,
            platform as platform_id,
            cast(rating as integer) as rating,
            cast(review_text_length as integer) as review_text_length,
            cast(reviewed_at as timestamp_ntz) as reviewed_at,
            cast(is_recommended as boolean) as is_recommended,
            playtime_at_review_hours::number(6, 1) as playtime_at_review_hours
        from source
    )

select *
from renamed
