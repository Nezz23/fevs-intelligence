{#- One row per answered item per respondent per wave, unpivoted from each wave's wide file.
    The item list is read from each raw table at run time, because no two waves share a layout.
    Blank answers are dropped by UNPIVOT; nothing else is reinterpreted here. -#}
{%- for wave in var('waves') %}
{%- set rel = source('raw', 'fevs_' ~ wave) %}
select
    {{ wave }} as wave,
    {{ respondent_key(wave, '_row_number') }} as respondent_key,
    upper(item_code) as item_code,
    raw_value,
    _file_sha256
from {{ rel }}
    unpivot (raw_value for item_code in (
        {%- for col in item_columns(rel) %}{{ adapter.quote(col) }}{% if not loop.last %}, {% endif %}{% endfor -%}
    ))
{% if not loop.last %}union all{% endif %}
{%- endfor %}
