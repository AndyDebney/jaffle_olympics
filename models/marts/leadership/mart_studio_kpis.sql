-- Studio x month executive summary. One row per month: actives, revenue by stream,
-- concentration (top title / top player share), acquisition and blended CAC, and
-- portfolio
-- health counts. This is the board-deck grain.
with
    months as (
        select distinct month_start_date as activity_month
        from {{ ref("dim_dates") }}
        where is_within_history_window
    ),

    actives as (
        select
            session_month as activity_month,
            count(distinct player_id) as monthly_active_players,
            count(*) as sessions
        from {{ ref("fct_play_sessions") }}
        group by 1
    ),

    new_players as (
        select
            cast(date_trunc('month', registered_at) as date) as activity_month,
            count(*) as new_registrations
        from {{ ref("dim_players") }}
        group by 1
    ),

    tx as (select * from {{ ref("fct_transactions") }}),

    revenue_by_month as (
        select
            transaction_month as activity_month,
            sum(net_amount_usd) as net_revenue_usd,
            sum(studio_net_revenue_usd) as studio_net_revenue_usd,
            sum(
                case
                    when transaction_type = 'premium_purchase'
                    then net_amount_usd
                    else 0
                end
            ) as net_revenue_premium_usd,
            sum(
                case when transaction_type = 'iap' then net_amount_usd else 0 end
            ) as net_revenue_iap_usd,
            sum(
                case
                    when transaction_type = 'season_pass' then net_amount_usd else 0
                end
            ) as net_revenue_season_pass_usd,
            sum(
                case when transaction_type = 'dlc' then net_amount_usd else 0 end
            ) as net_revenue_dlc_usd,
            sum(
                case
                    when transaction_type in ('refund', 'chargeback')
                    then net_amount_usd
                    else 0
                end
            ) as refunds_chargebacks_usd,
            count(
                distinct case when net_amount_usd > 0 then player_id end
            ) as paying_players
        from tx
        group by 1
    ),

    -- Top title share of net revenue within each month.
    title_share as (
        select
            activity_month, max(title_net) as top_title_net, sum(title_net) as month_net
        from
            (
                select
                    transaction_month as activity_month,
                    title_id,
                    sum(net_amount_usd) as title_net
                from tx
                group by 1, 2
            ) as title_month_net
        group by 1
    ),

    -- Top player share of net revenue within each month.
    player_share as (
        select
            activity_month,
            max(player_net) as top_player_net,
            sum(player_net) as month_net
        from
            (
                select
                    transaction_month as activity_month,
                    player_id,
                    sum(net_amount_usd) as player_net
                from tx
                group by 1, 2
            ) as player_month_net
        group by 1
    ),

    marketing as (
        select
            cast(date_trunc('month', week_start_date) as date) as activity_month,
            sum(spend_usd) as marketing_spend_usd,
            sum(installs) as marketing_installs
        from {{ ref("stg_marketing_spend") }}
        group by 1
    ),

    -- Portfolio health: how many titles sit in each concerning lifecycle stage
    -- (constant per month
    -- here, since lifecycle is evaluated at the analysis date; carried for
    -- at-a-glance context).
    portfolio as (
        select
            count_if(lifecycle_stage = 'sunset_candidate') as titles_sunset_candidate,
            count_if(lifecycle_stage = 'declining') as titles_declining,
            count_if(lifecycle_stage = 'launch_window') as titles_in_launch,
            count(*) as titles_total
        from {{ ref("dim_titles") }}
    )

select
    months.activity_month,
    portfolio.titles_total,
    portfolio.titles_in_launch,
    portfolio.titles_declining,
    portfolio.titles_sunset_candidate,

    coalesce(actives.monthly_active_players, 0) as monthly_active_players,
    coalesce(actives.sessions, 0) as sessions,
    coalesce(new_players.new_registrations, 0) as new_registrations,

    round(coalesce(revenue_by_month.net_revenue_usd, 0), 2) as net_revenue_usd,
    round(
        coalesce(revenue_by_month.studio_net_revenue_usd, 0), 2
    ) as studio_net_revenue_usd,
    round(
        coalesce(revenue_by_month.net_revenue_premium_usd, 0), 2
    ) as net_revenue_premium_usd,
    round(coalesce(revenue_by_month.net_revenue_iap_usd, 0), 2) as net_revenue_iap_usd,
    round(
        coalesce(revenue_by_month.net_revenue_season_pass_usd, 0), 2
    ) as net_revenue_season_pass_usd,
    round(coalesce(revenue_by_month.net_revenue_dlc_usd, 0), 2) as net_revenue_dlc_usd,
    round(
        coalesce(revenue_by_month.refunds_chargebacks_usd, 0), 2
    ) as refunds_chargebacks_usd,
    coalesce(revenue_by_month.paying_players, 0) as paying_players,
    round(
        coalesce(revenue_by_month.paying_players, 0)
        / nullif(actives.monthly_active_players, 0),
        4
    ) as payer_conversion_rate,
    round(
        coalesce(revenue_by_month.net_revenue_usd, 0)
        / nullif(actives.monthly_active_players, 0),
        2
    ) as arpu_usd,

    round(
        title_share.top_title_net / nullif(title_share.month_net, 0), 4
    ) as top_title_revenue_share,
    round(
        player_share.top_player_net / nullif(player_share.month_net, 0), 4
    ) as top_player_revenue_share,

    round(coalesce(marketing.marketing_spend_usd, 0), 2) as marketing_spend_usd,
    coalesce(marketing.marketing_installs, 0) as marketing_installs,
    round(
        coalesce(marketing.marketing_spend_usd, 0)
        / nullif(new_players.new_registrations, 0),
        2
    ) as blended_cac_usd
from months
left join actives on months.activity_month = actives.activity_month
left join new_players on months.activity_month = new_players.activity_month
left join revenue_by_month on months.activity_month = revenue_by_month.activity_month
left join title_share on months.activity_month = title_share.activity_month
left join player_share on months.activity_month = player_share.activity_month
left join marketing on months.activity_month = marketing.activity_month
cross join portfolio
order by 1
