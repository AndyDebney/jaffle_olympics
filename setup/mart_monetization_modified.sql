-- Monetization at title x purchase-category x month. Revenue, attach rate,
-- first-purchase
-- conversion and refund rate by what was actually sold. premium unit sales (no SKU) are
-- bucketed as 'premium_base'; DLC/expansions, battle passes, currency and cosmetics
-- come
-- from the SKU category.
with
    tx as (
        select
            t.*,
            case
                when t.transaction_type = 'premium_purchase'
                then 'premium_base'
                else coalesce(s.sku_category, 'other')
            end as purchase_category
        from {{ ref("fct_transactions") }} as t
        -- Match on the current SKU id, falling back to the pre-migration id for
        -- catalogue rows that never got renumbered.
        left join {{ ref("dim_skus") }} as s
            on t.sku_id = coalesce(s.sku_id, s.legacy_sku_id)
    ),

    titles as (
        select title_id, title_name
        from {{ ref('dim_titles') }}
    ),

    -- Monthly active players per title, to normalize attach/conversion.
    active as (
        select
            title_id,
            session_month as activity_month,
            count(distinct player_id) as monthly_active_players
        from {{ ref("fct_play_sessions") }}
        group by 1, 2
    ),

    agg as (
        select
            title_id,
            purchase_category,
            transaction_month as activity_month,
            sum(
                case
                    when transaction_type not in ('refund', 'chargeback')
                    then gross_amount_usd
                    else 0
                end
            ) as gross_revenue_usd,
            sum(net_amount_usd) as net_revenue_usd,
            sum(studio_net_revenue_usd) as studio_net_revenue_usd,
            sum(
                case
                    when transaction_type in ('refund', 'chargeback')
                    then gross_amount_usd
                    else 0
                end
            ) as refund_gross_usd,
            count(
                case when transaction_type not in ('refund', 'chargeback') then 1 end
            ) as purchase_count,
            count(
                case when transaction_type in ('refund', 'chargeback') then 1 end
            ) as refund_count,
            count(
                distinct case when net_amount_usd > 0 then player_id end
            ) as paying_players,
            count(case when is_first_purchase then 1 end) as first_purchases
        from tx
        group by 1, 2, 3
    )

select
    agg.title_id,
    titles.title_name,
    agg.purchase_category,
    agg.activity_month,
    agg.purchase_count,
    agg.refund_count,
    agg.paying_players,
    agg.first_purchases,
    round(agg.gross_revenue_usd, 2) as gross_revenue_usd,
    round(agg.net_revenue_usd, 2) as net_revenue_usd,
    round(agg.studio_net_revenue_usd, 2) as studio_net_revenue_usd,
    round(agg.refund_gross_usd, 2) as refund_gross_usd,
    coalesce(active.monthly_active_players, 0) as monthly_active_players,

    -- Attach rate: share of the title's monthly actives who bought in this category.
    round(
        agg.paying_players / nullif(active.monthly_active_players, 0), 4
    ) as attach_rate,
    -- First-purchase conversion: first-time buyers in this category over monthly
    -- actives.
    round(
        agg.first_purchases / nullif(active.monthly_active_players, 0), 4
    ) as first_purchase_conversion_rate,
    -- Refund rate: refunded gross over gross sold in the category-month.
    round(agg.refund_gross_usd / nullif(agg.gross_revenue_usd, 0), 4) as refund_rate
from agg
left join titles on agg.title_id = titles.title_id
left join
    active
    on agg.title_id = active.title_id
    and agg.activity_month = active.activity_month
order by 1, 4, 3
