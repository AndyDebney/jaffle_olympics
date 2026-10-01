with platforms as (select * from {{ ref("stg_platforms") }})

select
    platform_id::varchar as platform_id,
    platform_family::varchar as platform_family,
    storefront_fee_rate::number(4, 3) as storefront_fee_rate,
    {{ calculate_additional_fee(3) }} as additional_fee
from platforms
