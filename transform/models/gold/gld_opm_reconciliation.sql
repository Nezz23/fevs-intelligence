{#- Our governmentwide figures beside every figure OPM published (2024 Governmentwide Management Report).
    status: match (ours rounds to OPM's whole percent), mismatch, or not_scored (a published figure this
    warehouse deliberately does not compute, with the reason). The app shows this table as is. -#}
with ours as (
    select 'index' as measure_type, subindex_name as measure, wave, score as pct
    from {{ ref('gld_index_scores') }} where org_level = 'governmentwide'
    union all
    select 'item', x.item_code, r.wave, r.pct_positive
    from {{ ref('gld_question_results') }} r
    join {{ ref('question_crosswalk') }} x on x.wave = 2024 and x.question_id = r.question_id
    where r.org_level = 'governmentwide'
),
not_scored as (
    select * from (values
        ('index', 'performance_confidence', 2020), ('item', 'Q20', 2020), ('item', 'Q21', 2020),
        ('item', 'Q22', 2020), ('item', 'Q23', 2020)
    ) as t(measure_type, measure, wave)
)
select
    p.measure_type, p.measure, p.wave, p.published_pct_positive,
    o.pct * 100 as our_pct_positive,
    case
        when g.measure is not null then 'not_scored'
        when o.pct is not null and round(o.pct * 100, 0) = p.published_pct_positive then 'match'
        else 'mismatch'
    end as status,
    case when g.measure is not null
         then '2020 items sit in a COVID block whose question stems the public codebook omits; not trended here'
    end as note,
    p.source
from {{ ref('opm_published_results') }} p
left join ours o on o.measure_type = p.measure_type and o.measure = p.measure and o.wave = p.wave
left join not_scored g on g.measure_type = p.measure_type and g.measure = p.measure and g.wave = p.wave
