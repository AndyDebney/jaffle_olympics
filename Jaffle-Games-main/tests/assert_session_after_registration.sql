-- Business rule: a play session can never start before the player registered.
-- Returns offending sessions; the test passes when there are none.

select
    s.session_id,
    s.player_id,
    s.session_start_at,
    p.registered_at
from {{ ref('fct_play_sessions') }} as s
inner join {{ ref('dim_players') }} as p
    on s.player_id = p.player_id
where s.session_start_at < p.registered_at
