{% snapshot snap_player_account_status %}

{#
    Track each player's account_status over time (active -> dormant -> churned, or -> banned).
    A slowly-changing history the player-experience team can use to date state transitions.
#}
{{
    config(
        target_database=target.database,
        target_schema=target.schema,
        unique_key='player_id',
        strategy='check',
        check_cols=['account_status']
    )
}}

select
    player_id,
    account_status,
    last_login_at
from {{ ref('stg_players') }}

{% endsnapshot %}
