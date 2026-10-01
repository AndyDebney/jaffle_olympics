with
    source as (select * from {{ ref("raw_transactions") }}),

    renamed as (
        select
            transaction_id,
            player_id,
            title_id,
            transaction_type,
            currency_code,
            payment_method,
            platform as platform_id,
            -- Keep the raw local timestamp for auditability.
            cast(transaction_at as timestamp_ntz) as transaction_at_local,
            
            cast(gross_amount_usd as number(12, 2)) as gross_amount_usd,
            
            cast(platform_fee_usd as number(12, 2)) as platform_fee_usd,
            cast(local_amount as number(14, 2)) as local_amount,
            cast(is_first_purchase as boolean) as is_first_purchase,
            cast(_loaded_at as timestamp_ntz) as loaded_at,
            -- Source arrives in America/New_York wall-clock; bring it onto UTC like
            -- every other feed.
            {{ to_utc("transaction_at") }} as transaction_at,
            cast(gross_amount_usd as number(12,2)) * -1 as gross_amount_usd_signed,
            nullif(trim(sku_id), '') as sku_id
        from source
    )

select *
from renamed
