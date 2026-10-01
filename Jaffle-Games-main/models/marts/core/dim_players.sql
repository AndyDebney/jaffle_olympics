-- One row per player with lifecycle attributes. Combines cleaned source attributes
-- with the
-- engagement rollup (int_player_activity) and monetization rollup (int_player_spend).
-- Behavioural churn (is_churned) is defined on session recency; account_status is the
-- source-system state and can differ (e.g. banned cheaters).
with
    players as (select * from {{ ref("stg_players") }}),

    activity as (select * from {{ ref("int_player_activity") }}),

    spend as (select * from {{ ref("int_player_spend") }}),

    favorite as (
        select p.player_id, a.favorite_title_id, t.title_name as favorite_title_name
        from players as p
        left join activity as a on p.player_id = a.player_id
        left join {{ ref("stg_titles") }} as t on a.favorite_title_id = t.title_id
    ),

    joined as (
        select
            players.*,
            activity.lifetime_sessions,
            activity.lifetime_valid_sessions,
            activity.lifetime_play_minutes,
            activity.distinct_titles_played,
            activity.first_session_at,
            activity.last_session_at,
            activity.primary_platform_id,
            favorite.favorite_title_id,
            favorite.favorite_title_name,
            spend.live_service_net_usd,
            spend.lifetime_net_revenue_usd,
            spend.lifetime_studio_net_usd,
            spend.premium_net_usd,
            spend.payer_segment,
            spend.is_payer,
            spend.first_purchase_at,
            datediff(
                'day',
                activity.last_session_at,
                cast('{{ var("analysis_as_of_date") }}' as date)
            ) as days_since_last_session
        from players
        left join activity on players.player_id = activity.player_id
        left join spend on players.player_id = spend.player_id
        left join favorite on players.player_id = favorite.player_id
    )

select
    cast(player_id as varchar) as player_id,
    cast(registered_at as timestamp_ntz) as registered_at,
    cast(country_code as varchar) as country_code,
    cast(platform_registered_on_id as varchar) as platform_registered_on_id,
    cast(acquisition_channel as varchar) as acquisition_channel,
    cast(acquisition_campaign_id as varchar) as acquisition_campaign_id,
    cast(birth_year as INTEGER) as birth_year,
    cast(marketing_opt_in as boolean) as marketing_opt_in,
    cast(account_status as varchar) as account_status,
    cast(last_login_at as timestamp_ntz) as last_login_at,
    cast(first_session_at as timestamp_ntz) as first_session_at,
    cast(last_session_at as timestamp_ntz) as last_session_at,
    cast(days_since_last_session as integer) as days_since_last_session,
    cast(favorite_title_id as varchar) as favorite_title_id,
    cast(favorite_title_name as varchar) as favorite_title_name,
    cast(primary_platform_id as varchar) as primary_platform_id,
    cast(first_purchase_at as timestamp_ntz) as first_purchase_at,

    cast(date_trunc('month', registered_at) as date) as registration_cohort_month,
    cast(
        (extract(year from cast('{{ var("analysis_as_of_date") }}' as date)) - birth_year) as integer
    ) as age_years,
    cast(coalesce(lifetime_sessions,0) as integer) as lifetime_sessions,
    cast(coalesce(lifetime_valid_sessions,0) as integer) as lifetime_valid_sessions,
    cast(round(coalesce(lifetime_play_minutes,0),2) as number(12,2)) as lifetime_play_minutes,
    cast(coalesce(distinct_titles_played,0) as integer) as distinct_titles_played,
    cast(round(coalesce(live_service_net_usd,0),2) as number(12,2)) as live_service_net_usd,
    cast(round(coalesce(lifetime_net_revenue_usd,0),2) as number(12,2)) as lifetime_net_revenue_usd,
    cast(round(coalesce(lifetime_studio_net_usd,0),2) as number(12,2)) as lifetime_studio_net_usd,
    cast(coalesce(payer_segment,'non_payer') as varchar) as payer_segment,
    cast(coalesce(is_payer,false) as boolean) as is_payer,

    -- Behavioural churn: no session within the churn window as of the analysis date.
    cast(
        (coalesce(days_since_last_session, 99999) > {{ var("churn_days_threshold") }}) as boolean
    ) as is_churned
from joined
