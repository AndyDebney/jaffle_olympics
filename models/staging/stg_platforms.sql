{{ config(
    materialized='table'
) }}
with
    source as (select * from {{ ref("raw_platforms") }}),

    renamed as (
        select
            platform as platform_id,
            platform_family,
            storefront_fee_rate,
            {{ calculate_additional_fee(3) }} as additional_fee
        from source
    )

select *
from renamed
