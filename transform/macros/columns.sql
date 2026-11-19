{# Helpers that read a raw wave's columns at run time, so one model handles every wave's layout. #}

{% macro item_columns(relation) -%}
    {#- The survey item columns of a wave (Q1, Q16_1, V17_01, ...), as the database names them. -#}
    {%- set items = [] -%}
    {%- for col in adapter.get_columns_in_relation(relation) -%}
        {%- if modules.re.match('^[QV][0-9]+[A-Z]?(_[0-9]+)?$', col.name, modules.re.IGNORECASE) -%}
            {%- do items.append(col.name) -%}
        {%- endif -%}
    {%- endfor -%}
    {{- return(items) -}}
{%- endmacro %}

{% macro present_column(relation, candidates) -%}
    {#- The first of a field's historical names that this wave has (e.g. LEVEL1, PLEVEL1 or SUBELEM for
        the sub-agency), as the database spells it, or none. Matching ignores case. -#}
    {%- set present = {} -%}
    {%- for col in adapter.get_columns_in_relation(relation) -%}
        {%- do present.update({col.name | upper: col.name}) -%}
    {%- endfor -%}
    {%- for name in candidates -%}
        {%- if name | upper in present -%}
            {{- return(present[name | upper]) -}}
        {%- endif -%}
    {%- endfor -%}
    {{- return(none) -}}
{%- endmacro %}

{% macro first_column(relation, candidates, alias) -%}
    {#- Select the field under its wave-specific name, or NULL when the wave did not collect it. -#}
    {%- set name = present_column(relation, candidates) -%}
    {%- if name -%}
        {{ adapter.quote(name) }} as {{ alias }}
    {%- else -%}
        cast(null as varchar) as {{ alias }}
    {%- endif -%}
{%- endmacro %}

{% macro respondent_key(wave, row_number) -%}
    {#- A respondent key that is unique across waves and carries no published respondent ID. -#}
    cast({{ wave }} as bigint) * 10000000 + {{ row_number }}
{%- endmacro %}
