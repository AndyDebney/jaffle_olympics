-- Cohort retention triangle at registration-cohort x acquisition-channel x week-offset.
-- Cohort size is on EVERY row so any rate is read against its denominator
-- (denominators are
-- single-digit at this scale). is_observable marks cells whose week has not fully
-- elapsed yet,
-- so late cohorts are not mistaken for churn.
--
-- Title is deliberately NOT a slice here: at ~10 players per cohort, splitting
-- further by
-- title leaves nothing to read. Channel is the slice with real signal (organic vs
-- paid_social).
with
    players as (
        select player_id, registration_cohort_month, acquisition_channel
        from {{ ref("dim_players") }}
    ),

    cohorts as (
        select registration_cohort_month, acquisition_channel, count(*) as cohort_size
        from players
        group by 1, 2
    ),

    week_offsets as (
        select column1 as week_offset
        from (values (0), (1), (2), (3), (4), (5), (6), (7), (8))
    ),

    -- Which (cohort, channel, player) were active at each week offset.
    player_weeks as (
        select distinct
            p.registration_cohort_month,
            p.acquisition_channel,
            s.player_id,
            s.week_offset_from_registration as week_offset
        from {{ ref("fct_play_sessions") }} as s
        inner join players as p on s.player_id = p.player_id
    ),

    retained as (
        select
            registration_cohort_month,
            acquisition_channel,
            week_offset,
            count(distinct player_id) as retained_players
        from player_weeks
        group by 1, 2, 3
    ),

    spine as (
        select
            c.registration_cohort_month,
            c.acquisition_channel,
            c.cohort_size,
            w.week_offset
        from cohorts as c
        cross join week_offsets as w
    )

select
    spine.registration_cohort_month,
    spine.acquisition_channel,
    spine.week_offset,
    spine.cohort_size,
    coalesce(retained.retained_players, 0) as retained_players,

    -- The week has fully elapsed only if cohort_month + week_offset weeks <= analysis
    -- date.
    (
        dateadd('week', spine.week_offset, spine.registration_cohort_month)
        <= cast('{{ var("analysis_as_of_date") }}' as date)
    ) as is_observable,

    case
        when
            dateadd('week', spine.week_offset, spine.registration_cohort_month)
            > cast('{{ var("analysis_as_of_date") }}' as date)
        then null
        else
            round(
                coalesce(retained.retained_players, 0) / nullif(spine.cohort_size, 0), 4
            )
    end as retention_rate
from spine
left join
    retained
    on spine.registration_cohort_month = retained.registration_cohort_month
    and spine.acquisition_channel = retained.acquisition_channel
    and spine.week_offset = retained.week_offset
order by 1, 2, 3
