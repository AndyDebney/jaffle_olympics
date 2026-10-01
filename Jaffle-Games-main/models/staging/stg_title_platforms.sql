with
    source as (select * from {{ ref("raw_title_platforms") }}),

    renamed as (
        select
            title_id,
            platform as platform_id,
            cast(platform_launch_date as date) as platform_launch_date,
            store_page_url
        from source
    )

select *
from renamed
