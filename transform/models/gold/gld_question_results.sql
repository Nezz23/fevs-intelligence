{#- Survey-weighted results for every rating question, per wave, governmentwide and per agency.
    pct_positive follows OPM: the weighted share of 4-5 among 1-5 answers, with "Do Not Know" left out.
    Any group with fewer than min_cell_respondents raters is suppressed (OPM's Rule of Ten). -#}
with answers as (
    select i.wave, i.question_id, r.agency_code, r.weight, i.favorability, i.is_non_rating
    from {{ ref('slv_item_responses') }} i
    join {{ ref('slv_respondents') }} r on r.wave = i.wave and r.respondent_key = i.respondent_key
    where i.scale_type in ('agreement', 'satisfaction', 'quality', 'frequency')
),
grouped as (
    select wave, question_id, 'governmentwide' as org_level, 'ALL' as agency_code,
           count(favorability) as respondents, sum(case when favorability is not null then weight end) as weighted_respondents,
           {{ weighted_share("favorability = 'positive'", 'favorability is not null') }} as pct_positive,
           {{ weighted_share("favorability = 'neutral'", 'favorability is not null') }} as pct_neutral,
           {{ weighted_share("favorability = 'negative'", 'favorability is not null') }} as pct_negative,
           {{ weighted_share('is_non_rating', 'true') }} as pct_do_not_know
    from answers
    group by wave, question_id
    union all
    select wave, question_id, 'agency', agency_code,
           count(favorability), sum(case when favorability is not null then weight end),
           {{ weighted_share("favorability = 'positive'", 'favorability is not null') }},
           {{ weighted_share("favorability = 'neutral'", 'favorability is not null') }},
           {{ weighted_share("favorability = 'negative'", 'favorability is not null') }},
           {{ weighted_share('is_non_rating', 'true') }}
    from answers
    {#- XX is OPM's mask for agencies too small to name; it is not one agency, so it gets no row. #}
    where agency_code is not null and agency_code <> 'XX'
    group by wave, question_id, agency_code
)
select
    g.wave, g.question_id, q.canonical_text, q.scale_type, g.org_level, g.agency_code, g.respondents,
    {{ suppress_small('g.weighted_respondents', 'g.respondents') }} as weighted_respondents,
    {{ suppress_small('g.pct_positive', 'g.respondents') }} as pct_positive,
    {{ suppress_small('g.pct_neutral', 'g.respondents') }} as pct_neutral,
    {{ suppress_small('g.pct_negative', 'g.respondents') }} as pct_negative,
    {{ suppress_small('g.pct_do_not_know', 'g.respondents') }} as pct_do_not_know,
    g.respondents < {{ var('min_cell_respondents') }} as is_suppressed,
    x.wording_status
from grouped g
join {{ ref('question_catalog') }} q on q.question_id = g.question_id
join {{ ref('question_crosswalk') }} x on x.question_id = g.question_id and x.wave = g.wave
