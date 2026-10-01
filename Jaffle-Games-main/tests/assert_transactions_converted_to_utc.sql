-- Business rule / transformation guard: transaction timestamps are captured in
-- America/New_York and must be converted to UTC. Because Eastern time is behind UTC, the UTC
-- timestamp must always be strictly later than the retained local timestamp. If any row fails
-- this, the timezone conversion in staging has regressed. Passes when no rows are returned.

select
    transaction_id,
    transaction_at_local,
    transaction_at
from {{ ref('fct_transactions') }}
where transaction_at <= transaction_at_local
