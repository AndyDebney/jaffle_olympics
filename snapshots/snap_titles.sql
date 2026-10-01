{% snapshot snap_titles %}

{#
    Track changes to a title's list price and sunset status over time using the check
    strategy. Lets finance and leadership see when a title was repriced or formally retired.
    Snapshots land in the same database/schema as the run's target (no hardcoded names).
#}
{{
    config(
        target_database=target.database,
        target_schema=target.schema,
        unique_key='title_id',
        strategy='check',
        check_cols=['list_price_usd', 'sunset_date']
    )
}}

select
    title_id,
    title_name,
    monetization_model,
    list_price_usd,
    sunset_date
from {{ ref('stg_titles') }}

{% endsnapshot %}
