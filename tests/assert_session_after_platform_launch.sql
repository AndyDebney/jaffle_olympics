-- Business rule: a session on a (title, platform) cannot predate that platform's launch of
-- the title. Guards against impossible telemetry. Passes when no rows are returned.

select
    s.session_id,
    s.title_id,
    s.platform_id,
    s.session_start_at,
    tp.platform_launch_date
from {{ ref('fct_play_sessions') }} as s
inner join {{ ref('stg_title_platforms') }} as tp
    on s.title_id = tp.title_id
   and s.platform_id = tp.platform_id
where cast(s.session_start_at as date) < tp.platform_launch_date
