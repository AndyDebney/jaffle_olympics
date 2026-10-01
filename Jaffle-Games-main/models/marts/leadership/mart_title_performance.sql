-- Title x month performance for leadership and product. Built on a complete title-month
-- spine (every month from a title's launch through the window end) so declines and
-- droughts
-- show as low/zero rows rather than disappearing. Sparse cells are flagged, not hidden.
with
    months as (
        select distinct month_start_date
        from {{ ref("dim_dates") }}
        where is_within_history_window
    ),

    titles as (
        select title_id, title_name, monetization_model, lifecycle_stage, launch_date
        from {{ ref("dim_titles") }}
    ),

    spine as (
        select
            t.title_id,
            t.title_name,
            t.monetization_model,
            t.lifecycle_stage,
            m.month_start_date as activity_month
        from titles as t
        cross join months as m
        where m.month_start_date >= date_trunc('month', t.launch_date)
    ),

    sessions as (
        select
            title_id,
            session_month,
            count(*) as sessions,
            count_if(is_valid_session) as valid_sessions,
            count(distinct player_id) as monthly_active_players,
            avg(
                case when is_valid_session then session_duration_minutes end
            ) as avg_session_minutes
        from {{ ref("fct_play_sessions") }}
        group by 1, 2
    ),

    revenue as (
        select
            title_id,
            transaction_month,
            sum(net_amount_usd) as net_revenue_usd,
            sum(studio_net_revenue_usd) as studio_net_revenue_usd,
            count(
                distinct case when net_amount_usd > 0 then player_id end
            ) as paying_players
        from {{ ref("fct_transactions") }}
        group by 1, 2
    ),

    reviews as (
        select
            title_id,
            cast(date_trunc('month', reviewed_at) as date) as review_month,
            avg(rating) as avg_review_rating,
            count(*) as review_count
        from {{ ref("stg_reviews") }}
        group by 1, 2
    ),

    joined as (
        select
            spine.title_id,
            spine.title_name,
            spine.monetization_model,
            spine.lifecycle_stage,
            spine.activity_month,
            sessions.avg_session_minutes,
            reviews.avg_review_rating,
            coalesce(sessions.monthly_active_players, 0) as monthly_active_players,
            coalesce(sessions.sessions, 0) as sessions,
            coalesce(sessions.valid_sessions, 0) as valid_sessions,
            coalesce(revenue.net_revenue_usd, 0) as net_revenue_usd,
            coalesce(revenue.studio_net_revenue_usd, 0) as studio_net_revenue_usd,
            coalesce(revenue.paying_players, 0) as paying_players,
            coalesce(reviews.review_count, 0) as review_count
        from spine
        left join
            sessions
            on spine.title_id = sessions.title_id
            and spine.activity_month = sessions.session_month
        left join
            revenue
            on spine.title_id = revenue.title_id
            and spine.activity_month = revenue.transaction_month
        left join
            reviews
            on spine.title_id = reviews.title_id
            and spine.activity_month = reviews.review_month
    ),

    final as (
        select
            title_id,
            title_name,
            monetization_model,
            lifecycle_stage,
            activity_month,
            monthly_active_players,
            sessions,
            valid_sessions,
            paying_players,
            review_count,

            round(
                valid_sessions / nullif(monthly_active_players, 0), 2
            ) as sessions_per_active_player,
            round(avg_session_minutes, 2) as avg_session_minutes,
            round(net_revenue_usd, 2) as net_revenue_usd,
            round(studio_net_revenue_usd, 2) as studio_net_revenue_usd,
            round(net_revenue_usd / nullif(monthly_active_players, 0), 2) as arpu_usd,
            round(net_revenue_usd / nullif(paying_players, 0), 2) as arppu_usd,
            round(
                paying_players / nullif(monthly_active_players, 0), 4
            ) as payer_conversion_rate,
            round(avg_review_rating, 2) as avg_review_rating,

            -- Month-over-month deltas within each title.
            monthly_active_players - lag(monthly_active_players) over (
                partition by title_id order by activity_month
            ) as map_mom_delta,
            round(
                net_revenue_usd - lag(net_revenue_usd) over (
                    partition by title_id order by activity_month
                ),
                2
            ) as net_revenue_mom_delta,

            -- Be explicit about thin cells instead of implying they are reliable.
            (
                monthly_active_players >= {{ var("min_active_players_threshold") }}
            ) as has_sufficient_volume
        from joined
    )

select *
from final
