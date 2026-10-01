-- Normalized transactions: one row per transaction with signed amounts, studio net revenue,
-- and a revenue-stream classification. This is the single place transaction sign and stream
-- logic lives, so every finance/monetization mart agrees by construction.

with transactions as (
    select * from {{ ref('stg_transactions') }}
)

select
    transaction_id,
    player_id,
    title_id,
    platform_id,
    sku_id,
    transaction_at,
    transaction_at_local,
    transaction_type,
    currency_code,
    payment_method,
    is_first_purchase,

    gross_amount_usd,
    platform_fee_usd,

    -- Refunds and chargebacks arrive positive; negate them so SUM(net_amount_usd) is true net.
    {{ signed_net_amount('transaction_type', 'gross_amount_usd') }}  as net_amount_usd,
    {{ signed_net_amount('transaction_type', 'platform_fee_usd') }}  as signed_platform_fee_usd,

    -- Studio-recognized revenue: net of the storefront's cut, with fees reversing on refunds.
    {{ signed_net_amount('transaction_type', 'gross_amount_usd') }}
        - {{ signed_net_amount('transaction_type', 'platform_fee_usd') }} as studio_net_revenue_usd,

    -- Grouped revenue stream. Live-service (iap + season_pass) drives payer segmentation;
    -- premium unit sales + DLC are catalogue revenue; refunds/chargebacks are reversals.
    case
        when transaction_type in ('iap', 'season_pass')      then 'live_service'
        when transaction_type in ('premium_purchase', 'dlc') then 'catalog'
        when transaction_type in ('refund', 'chargeback')    then 'reversal'
    end as revenue_stream_group,

    (transaction_type in ('iap', 'season_pass', 'refund', 'chargeback')) as is_live_service_revenue

FROM transactions
