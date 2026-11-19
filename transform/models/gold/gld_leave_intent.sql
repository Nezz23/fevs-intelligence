{#- Stated intention to leave one's organization within a year, survey-weighted, per wave and agency.
    This is what respondents said they were considering, not observed turnover. 2012 is left out: its
    published codes cannot be matched to its answer options (see leave_intent_codes). -#}
with answers as (
    select wave, agency_code, weight, leave_intent, considering_leaving
    from {{ ref('slv_respondents') }}
    where leave_intent_verified
),
grouped as (
    select wave, 'governmentwide' as org_level, 'ALL' as agency_code, count(*) as respondents,
           {{ weighted_share('considering_leaving', 'true') }} as pct_considering_leaving,
           {{ weighted_share("leave_intent = 'yes_federal_job'", 'true') }} as pct_to_another_federal_job,
           {{ weighted_share("leave_intent = 'yes_outside_government'", 'true') }} as pct_to_leave_government,
           {{ weighted_share("leave_intent = 'yes_other'", 'true') }} as pct_other_reason
    from answers group by wave
    union all
    select wave, 'agency', agency_code, count(*),
           {{ weighted_share('considering_leaving', 'true') }},
           {{ weighted_share("leave_intent = 'yes_federal_job'", 'true') }},
           {{ weighted_share("leave_intent = 'yes_outside_government'", 'true') }},
           {{ weighted_share("leave_intent = 'yes_other'", 'true') }}
    from answers where agency_code is not null and agency_code <> 'XX' group by wave, agency_code
)
select wave, org_level, agency_code, respondents,
       {{ suppress_small('pct_considering_leaving', 'respondents') }} as pct_considering_leaving,
       {{ suppress_small('pct_to_another_federal_job', 'respondents') }} as pct_to_another_federal_job,
       {{ suppress_small('pct_to_leave_government', 'respondents') }} as pct_to_leave_government,
       {{ suppress_small('pct_other_reason', 'respondents') }} as pct_other_reason,
       respondents < {{ var('min_cell_respondents') }} as is_suppressed
from grouped
