{#- One row per respondent per wave: the weight, where they work, and their leave-intent answer, as published.
    Respondent IDs (USERID, RandomID) are dropped here and never leave the raw layer. -#}
{%- for wave in var('waves') %}
{%- set rel = source('raw', 'fevs_' ~ wave) %}
{#- 2020 asked about leaving twice (before COVID, and "today"); "today" is the question every other wave asks. #}
{%- set leave_col = present_column(rel, ['DLEAVING', 'DLEAVINGB']) %}
select
    {{ wave }} as wave,
    {{ respondent_key(wave, '_row_number') }} as respondent_key,
    {{ first_column(rel, ['POSTWT'], 'weight_text') }},
    {{ first_column(rel, ['AGENCY'], 'agency_code') }},
    {{ first_column(rel, ['LEVEL1', 'PLEVEL1', 'SUBELEM'], 'level1_code') }},
    {{ first_column(rel, ['DLEAVING', 'DLEAVINGB'], 'leave_code') }},
    {{ "'" ~ leave_col ~ "'" if leave_col else 'cast(null as varchar)' }} as leave_source_column,
    {{ first_column(rel, ['DSUPER'], 'supervisory_code') }},
    _file_sha256,
    _contract_version
from {{ rel }}
{% if not loop.last %}union all{% endif %}
{%- endfor %}
