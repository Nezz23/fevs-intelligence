{#- OPM's indices (2024 definitions), scored the way OPM scores them: the mean of each item's unrounded
    percent positive; the Employee Engagement Index is the mean of its three subindex scores.
    The 2024 definition is applied to every earlier wave through the question crosswalk. A wave gets a
    score only if it asked every item; items_asked says how many it did. -#}
with items as (
    select i.index_name, coalesce(nullif(i.subindex_name, ''), i.index_name) as subindex_name, x.question_id
    from {{ ref('opm_index_items') }} i
    join {{ ref('question_crosswalk') }} x on x.wave = 2024 and x.item_code = i.item_code_2024
),
defined as (
    select subindex_name, count(*) as items_defined from items group by subindex_name
),
item_results as (
    select r.wave, r.org_level, r.agency_code, i.index_name, i.subindex_name, r.question_id, r.pct_positive,
           r.wording_status, r.respondents
    from {{ ref('gld_question_results') }} r
    join items i on i.question_id = r.question_id
),
subindex as (
    select ir.wave, ir.org_level, ir.agency_code, ir.index_name, ir.subindex_name,
           count(*) as items_asked,
           max(d.items_defined) as items_defined,
           avg(ir.pct_positive) as score,
           count(ir.pct_positive) as items_reported,
           min(ir.respondents) as min_item_respondents
    from item_results ir
    join defined d on d.subindex_name = ir.subindex_name
    group by ir.wave, ir.org_level, ir.agency_code, ir.index_name, ir.subindex_name
),
scored as (
    select *, items_asked = items_defined and items_reported = items_defined as is_complete from subindex
)
select wave, org_level, agency_code, index_name, subindex_name,
       cast(items_defined as bigint) as items_defined, cast(items_asked as bigint) as items_asked,
       case when is_complete then score end as score, is_complete,
       cast(min_item_respondents as bigint) as min_item_respondents
from scored
union all
select wave, org_level, agency_code, index_name, index_name as subindex_name,
       cast(sum(items_defined) as bigint), cast(sum(items_asked) as bigint),
       case when count(*) = 3 and {{ bool_and_agg("is_complete") }} then avg(score) end,
       count(*) = 3 and {{ bool_and_agg("is_complete") }}, cast(min(min_item_respondents) as bigint)
from scored
where index_name = 'employee_engagement'
group by wave, org_level, agency_code, index_name
