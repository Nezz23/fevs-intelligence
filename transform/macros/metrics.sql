{# Survey-weighted metrics. Every share is weighted by POSTWT, OPM's post-stratification weight. #}

{% macro weighted_share(condition, eligible, weight='weight') -%}
    {#- Weighted share of eligible answers that meet the condition; NULL when nothing is eligible. -#}
    sum(case when {{ eligible }} and {{ condition }} then {{ weight }} else 0 end)
      / nullif(sum(case when {{ eligible }} then {{ weight }} else 0 end), 0)
{%- endmacro %}

{% macro suppress_small(value, respondents) -%}
    {#- OPM's Rule of Ten: hide a result computed from fewer than min_cell_respondents people. -#}
    case when {{ respondents }} >= {{ var('min_cell_respondents') }} then {{ value }} end
{%- endmacro %}
