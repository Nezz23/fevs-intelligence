{# A fingerprint of the reference data that silver depends on (the crosswalk and each question's scale type).
   Incremental models store it beside each row, so a reviewed change to the mapping rebuilds every wave it
   touches, not only waves whose source file changed. #}

{% macro string_agg_ordered(expr, order_by) -%}
    {{ return(adapter.dispatch('string_agg_ordered')(expr, order_by)) }}
{%- endmacro %}

{% macro default__string_agg_ordered(expr, order_by) -%}
    string_agg({{ expr }}, ',' order by {{ order_by }})
{%- endmacro %}

{% macro snowflake__string_agg_ordered(expr, order_by) -%}
    listagg({{ expr }}, ',') within group (order by {{ order_by }})
{%- endmacro %}

{% macro reference_version() -%}
    {%- if not execute -%}{{ return('') }}{%- endif -%}
    {%- set sql -%}
        select md5({{ string_agg_ordered(
            "cast(x.wave as varchar) || ':' || x.item_code || ':' || coalesce(x.question_id, '') || ':' || coalesce(q.scale_type, '')",
            'x.wave, x.item_code') }})
        from {{ ref('question_crosswalk') }} x
        left join {{ ref('question_catalog') }} q on q.question_id = x.question_id
    {%- endset -%}
    {{ return(run_query(sql).columns[0].values()[0]) }}
{%- endmacro %}
