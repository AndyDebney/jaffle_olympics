with
    source as (select * from {{ ref("raw_releases") }}),

    renamed as (
        select
            release_id,
            title_id,
            app_version,
            release_type as release_type,
            cast(released_at as timestamp_ntz) as released_at,
            cast(dev_days_estimated as integer) as dev_days_estimated,
            cast(dev_days_actual as integer) as dev_days_actual,
            cast(qa_bug_count as INTEGER) as qa_bug_count,
            cast(is_rollback as boolean) as is_rollback,
            cast(_loaded_at as timestamp_ntz) as loaded_at,
            trim(release_notes) as release_notes
        from source
    )

select *
from renamed
