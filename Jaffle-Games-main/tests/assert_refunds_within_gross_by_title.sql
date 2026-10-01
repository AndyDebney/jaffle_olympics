-- Business rule: for any title, total refunded/charged-back gross must never exceed the
-- gross revenue ever collected for that title (you cannot refund more than you sold).
-- Passes when no titles violate.

with by_title as (
    select
        title_id,
        sum(case when transaction_type not in ('refund', 'chargeback') then gross_amount_usd else 0 end) as gross_sold,
        sum(case when transaction_type in ('refund', 'chargeback')     then gross_amount_usd else 0 end) as gross_refunded
    from {{ ref('fct_transactions') }}
    group by 1
)

select *
from by_title
where gross_refunded > gross_sold
