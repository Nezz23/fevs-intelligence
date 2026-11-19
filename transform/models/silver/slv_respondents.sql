{#- One row per respondent per wave, typed, with leave intent decoded through the reviewed code table.
    Leave-intent codes changed meaning in 2020 (B and D swapped), so the raw letter is never read directly. -#}
select
    r.wave,
    r.respondent_key,
    cast(r.weight_text as double) as weight,
    {#- OPM masks small units as XX / XXZZ in the public file; keep the mask visible rather than guess. #}
    r.agency_code,
    nullif(r.level1_code, '') as level1_code,
    r.leave_code,
    r.leave_source_column,
    coalesce(c.leave_intent, case when r.leave_code is null then 'no_answer' end) as leave_intent,
    coalesce(c.verified, false) as leave_intent_verified,
    {#- "Intention to leave" is a stated intention on a survey, not observed turnover. #}
    case
        when c.verified and c.leave_intent = 'no' then false
        when c.verified and c.leave_intent like 'yes_%' then true
    end as considering_leaving,
    r._file_sha256,
    r._contract_version
from {{ ref('brz_respondents') }} r
left join {{ ref('leave_intent_codes') }} c
    on c.wave = r.wave and c.source_column = r.leave_source_column and c.code = r.leave_code
