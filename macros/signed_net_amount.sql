{#
    Turn a positive gross amount into a signed net amount based on transaction_type.
    Refunds and chargebacks arrive as POSITIVE numbers in the source and must be negated so
    that a straight SUM(net_amount) gives true net revenue. This is the one definition of
    "which transaction types reduce revenue", reused by staging tests and the intermediate.
#}
{% macro signed_net_amount(type_column, amount_column) %}
    case
        when {{ type_column }} in ('refund', 'chargeback') then -1 * {{ amount_column }}
        else {{ amount_column }}
    end
{% endmacro %}
