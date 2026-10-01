-- Per-player monetization rollup used to segment payers and report lifetime value.
-- Payer segmentation is driven ONLY by live-service spend (iap + season_pass, net of
-- reversals). Premium unit sales and DLC contribute to lifetime_net_revenue but never
-- turn a player into a "payer" — a non_payer can still have bought a premium title.

with tx as (
    select * from {{ ref('int_transactions') }}
),

player_rollup as (
    select
        player_id,

        -- Live-service spend (the segmentation basis): iap + season_pass net of reversals.
        sum(case when transaction_type in ('iap', 'season_pass', 'refund', 'chargeback')
                 then net_amount_usd else 0 end)                       as live_service_net_usd,

        -- All-stream lifetime net revenue.
        sum(net_amount_usd)                                            as lifetime_net_revenue_usd,
        sum(studio_net_revenue_usd)                                    as lifetime_studio_net_usd,

        sum(case when transaction_type = 'premium_purchase' then net_amount_usd else 0 end) as premium_net_usd,
        sum(case when transaction_type = 'iap'              then net_amount_usd else 0 end) as iap_net_usd,
        sum(case when transaction_type = 'season_pass'      then net_amount_usd else 0 end) as season_pass_net_usd,
        sum(case when transaction_type = 'dlc'              then net_amount_usd else 0 end) as dlc_net_usd,
        sum(case when transaction_type in ('refund', 'chargeback') then gross_amount_usd else 0 end) as refunded_gross_usd,

        count(*)                                                       as lifetime_transactions,
        min(case when is_first_purchase then transaction_at end)       as first_purchase_at
    from tx
    group by 1
)

select
    player_rollup.*,

    -- Segment on lifetime live-service spend, using project-level thresholds.
    case
        when player_rollup.live_service_net_usd >= {{ var('payer_whale_min_usd') }}   then 'whale'
        when player_rollup.live_service_net_usd >= {{ var('payer_dolphin_min_usd') }} then 'dolphin'
        when player_rollup.live_service_net_usd >= {{ var('payer_minnow_min_usd') }}  then 'minnow'
        else 'non_payer'
    end as payer_segment,

    (player_rollup.live_service_net_usd >= {{ var('payer_minnow_min_usd') }}) as is_payer
from player_rollup
