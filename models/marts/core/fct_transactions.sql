-- One row per transaction, conformed and typed, with signed net amounts and studio net
-- revenue. transaction_at is UTC (converted from America/New_York upstream).
with transactions as (select * from {{ ref("int_transactions") }})

select
    transaction_id::varchar as transaction_id,
    player_id::varchar as player_id,
    title_id::varchar as title_id,
    platform_id::varchar as platform_id,
    sku_id::varchar as sku_id,

    transaction_at::timestamp_ntz as transaction_at,
    transaction_at_local::timestamp_ntz as transaction_at_local,
    transaction_at::date as transaction_date,

    transaction_type::varchar as transaction_type,
    revenue_stream_group::varchar as revenue_stream_group,
    is_live_service_revenue::boolean as is_live_service_revenue,
    is_first_purchase::boolean as is_first_purchase,
    currency_code::varchar as currency_code,
    payment_method::varchar as payment_method,

    gross_amount_usd::number(12, 2) as gross_amount_usd,
    cast(platform_fee_usd as number(12, 2)) as platform_fee_usd,
    net_amount_usd::number(12, 2) as net_amount_usd,
    studio_net_revenue_usd::number(12, 2) as studio_net_revenue_usd,

    date_trunc('month',transaction_at)::date as transaction_month
FROM transactions
