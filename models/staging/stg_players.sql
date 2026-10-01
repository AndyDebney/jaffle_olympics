with
    source as (select * from {{ ref("raw_players") }}),

    renamed as (
        select
            player_id,
            cast(registered_at as timestamp_ntz) as registered_at,
            platform_registered_on as platform_registered_on_id,
            cast(birth_year as integer) as birth_year,
            cast(marketing_opt_in as boolean) as marketing_opt_in,
            account_status,
            cast(last_login_at as timestamp_ntz) as last_login_at,
            cast(_loaded_at as timestamp_ntz) as loaded_at,

            -- Trim + uppercase the country code; empty -> null.
            {{ clean_country_code("country_code") }} as country_code,

            -- Normalize the acquisition channel: the raw feed contains "Paid Social"
            -- alongside
            -- "paid_social". Lowercasing and swapping spaces for underscores
            -- collapses both.
            lower(replace(trim(acquisition_channel), ' ', '_')) as acquisition_channel,

            nullif(trim(acquisition_campaign_id), '') as acquisition_campaign_id,

            -- Aliased off "email" (an unreserved Snowflake keyword) to avoid RF04.
            lower(trim(email)) as email_address
        from source
    )

select *
from renamed
