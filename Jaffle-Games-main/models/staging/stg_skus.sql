with
    source as (select * from {{ ref("raw_skus") }}),

    renamed as (
        select
            sku_id,
            title_id,
            sku_category as sku_category,
            cast(price_usd as number(10, 2)) as price_usd,
            cast(is_active as BOOLEAN) as is_active,
            cast(first_available_date as date) as first_available_date,
            trim(sku_name) as sku_name
        from source
    )

select *
from renamed
