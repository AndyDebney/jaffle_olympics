{#
    Convert a wall-clock TIMESTAMP_NTZ captured in `source_tz` into UTC, returned as a
    TIMESTAMP_NTZ. Used to bring raw_transactions (America/New_York) onto the same UTC
    footing as every other source. CONVERT_TIMEZONE with three arguments treats the input
    as being in `source_tz` and returns the equivalent wall-clock time in the target zone.
#}
{% macro to_utc(column_name, source_tz='America/New_York') %}
    convert_timezone('{{ source_tz }}', 'UTC', {{ column_name }})
{% endmacro %}
