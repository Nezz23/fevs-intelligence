{#- The Workplace Happiness Paradox: how many people who are satisfied with their job still say they are
    considering leaving, and how that varies with trust in their supervisor, regard for senior leaders and
    workload. Each person is placed in one of 16 profiles (four yes/no answers, "yes" meaning a 4 or 5).
    Shares are survey-weighted. These are associations in observational survey data, not causes. -#}
with features as (
    select x.wave, x.question_id, p.feature
    from {{ ref('paradox_questions') }} p
    join {{ ref('question_crosswalk') }} x24 on x24.wave = 2024 and x24.item_code = p.item_code_2024
    join {{ ref('question_crosswalk') }} x on x.question_id = x24.question_id
),
person as (
    select i.wave, i.respondent_key,
        max(case when f.feature = 'job_satisfied' then i.favorability end) as job,
        max(case when f.feature = 'trusts_supervisor' then i.favorability end) as supervisor,
        max(case when f.feature = 'respects_senior_leaders' then i.favorability end) as leaders,
        max(case when f.feature = 'workload_reasonable' then i.favorability end) as workload
    from {{ ref('slv_item_responses') }} i
    join features f on f.wave = i.wave and f.question_id = i.question_id
    group by i.wave, i.respondent_key
),
profiled as (
    select p.wave, r.weight, r.considering_leaving,
           p.job = 'positive' as job_satisfied,
           p.supervisor = 'positive' as trusts_supervisor,
           p.leaders = 'positive' as respects_senior_leaders,
           p.workload = 'positive' as workload_reasonable
    from person p
    join {{ ref('slv_respondents') }} r on r.wave = p.wave and r.respondent_key = p.respondent_key
    {#- Only people who rated all four and gave a decodable leave answer are profiled. #}
    where p.job is not null and p.supervisor is not null and p.leaders is not null and p.workload is not null
      and r.considering_leaving is not null
),
grouped as (
    select wave, job_satisfied, trusts_supervisor, respects_senior_leaders, workload_reasonable,
           count(*) as respondents, sum(weight) as weighted_respondents,
           {{ weighted_share('considering_leaving', 'true') }} as pct_considering_leaving
    from profiled
    group by all
)
select g.*,
       g.weighted_respondents / sum(g.weighted_respondents) over (partition by g.wave) as share_of_workforce,
       g.respondents < {{ var('min_cell_respondents') }} as is_suppressed
from grouped g
