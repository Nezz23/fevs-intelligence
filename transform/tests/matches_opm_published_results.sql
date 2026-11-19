{#- Every governmentwide figure OPM published must equal ours once ours is rounded to a whole percent, as
    OPM rounds. A row returned here is a mismatch. Where our build does not score a published figure
    (2020 Performance Confidence: OPM trends the 2020 COVID-block items, whose stems the public codebook
    omits), the row is listed in the expected-gaps set below rather than silently skipped. -#}
with ours as (
    select 'index' as measure_type, subindex_name as measure, wave, score as pct
    from {{ ref('gld_index_scores') }} where org_level = 'governmentwide'
    union all
    select 'item', x.item_code, r.wave, r.pct_positive
    from {{ ref('gld_question_results') }} r
    join {{ ref('question_crosswalk') }} x on x.wave = 2024 and x.question_id = r.question_id
    where r.org_level = 'governmentwide'
),
expected_gaps as (
    select * from (values
        ('index', 'performance_confidence', 2020), ('item', 'Q20', 2020), ('item', 'Q21', 2020),
        ('item', 'Q22', 2020), ('item', 'Q23', 2020)
    ) as t(measure_type, measure, wave)
)
select p.measure_type, p.measure, p.wave, p.published_pct_positive, round(o.pct * 100, 2) as ours
from {{ ref('opm_published_results') }} p
left join ours o on o.measure_type = p.measure_type and o.measure = p.measure and o.wave = p.wave
where not exists (select 1 from expected_gaps g
                  where g.measure_type = p.measure_type and g.measure = p.measure and g.wave = p.wave)
  and (o.pct is null or round(o.pct * 100, 0) <> p.published_pct_positive)
