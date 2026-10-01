{#
    Normalize a raw country_code: strip surrounding whitespace, uppercase, and turn any
    resulting empty string into NULL. The raw seeds contain deliberately dirty values such
    as " us", "Us " and "de " — this macro is the single place that fix lives.
#}
{% macro clean_country_code(column_name) %}
    nullif(upper(trim({{ column_name }})), '')
{% endmacro %}
