{% test unique_combination(model, columns) %}
{#- No two rows share these columns: the model's grain. #}
select {{ columns | join(', ') }}, count(*) as n
from {{ model }}
group by {{ columns | join(', ') }}
having count(*) > 1
{% endtest %}

{% test share_between_0_and_1(model, column_name) %}
select * from {{ model }} where {{ column_name }} < 0 or {{ column_name }} > 1
{% endtest %}

{% test positive(model, column_name) %}
select * from {{ model }} where {{ column_name }} is null or {{ column_name }} <= 0
{% endtest %}

{% test suppressed_below_rule_of_ten(model, count_column, value_columns) %}
{#- A group under min_cell_respondents shows no result at all, and a group at or above it is not hidden. #}
select * from {{ model }}
where ({{ count_column }} < {{ var('min_cell_respondents') }}
       and ({% for c in value_columns %}{{ c }} is not null{% if not loop.last %} or {% endif %}{% endfor %}))
   or ({{ count_column }} < {{ var('min_cell_respondents') }}) <> is_suppressed
{% endtest %}
