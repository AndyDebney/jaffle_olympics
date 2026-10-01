with
    skus as (select * from {{ ref("stg_skus") }}),

    titles as (select title_id, title_name from {{ ref("stg_titles") }})

select
    skus.sku_id::varchar as sku_id,
    skus.title_id::varchar as title_id,
    titles.title_name::varchar as title_name,
    skus.sku_name::varchar as sku_name,
    skus.sku_category::varchar as sku_category,
    skus.price_usd::number(12, 2) as price_usd,
    skus.is_active::boolean as is_active,
    skus.first_available_date::date as first_available_date,

    -- Pre-migration storefront id for the same item (SKU001 -> SK-001). Transactions
    -- written before the catalogue was renumbered still carry this form.
    replace(skus.sku_id, 'SKU', 'SK-')::varchar as legacy_sku_id
from skus
left join titles on skus.title_id = titles.title_id 
