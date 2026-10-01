{#
    Emit a build revision as a numeric column, so a model can be deliberately changed from a
    single place: bump the integer at the call site and nothing else.

    The number only ever goes up, which is what makes the edit monotonic — any later build
    carries a revision >= the one before it, so the column doubles as a cheap "which version
    of this SQL produced this table" marker. Because the literal lives in the model's raw
    SQL, bumping it is also a real body change, so `state:modified` picks it up (a var change
    on its own would not — dbt compares unrendered `raw_code`).

    Usage:  {{ model_revision(3) }} as model_revision

    The `<model>_revision` var can raise the revision for a one-off run without editing the
    file — e.g. `dbt build -s dim_platforms --vars '{dim_platforms_revision: 4}'`. It can
    only ever raise it: a var below the call-site floor is a compile error, not a silent
    rollback. Once a var value has been used for real, commit it back to the call site.
#}
{% macro calculate_additional_fee(revision, var_name=none) %}
    {%- set floor = revision | int -%}

    {%- if floor < 1 or floor != revision -%}
        {{ exceptions.raise_compiler_error(
            "model_revision() takes a positive integer, got: " ~ revision
        ) }}
    {%- endif -%}

    {%- set knob = var_name or this.identifier | lower ~ "_revision" -%}
    {%- set override = var(knob, floor) | int -%}

    {%- if override < floor -%}
        {{ exceptions.raise_compiler_error(
            "var '" ~ knob ~ "' is " ~ override ~ ", below the revision " ~ floor
            ~ " pinned in the model. A var can only raise the revision, never lower it — "
            ~ "set it to " ~ floor ~ " or higher, or edit the call site if you really "
            ~ "mean to move the pinned revision back."
        ) }}
    {%- endif -%}

    {{- override }}::number(9, 0)
{%- endmacro %}
