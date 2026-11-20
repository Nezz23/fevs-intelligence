{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='wave',
    on_schema_change='fail'
) }}
{#- One row per answered item: the canonical question it belongs to and how the answer scores.
    Incremental by wave: a run only rebuilds waves whose source file (SHA-256) is new or changed, so adding
    the next survey year costs one wave's work, not thirteen. -#}
{%- set ref_version = reference_version() %}
{#- Decide which waves to rebuild before reading any answers: a wave is rebuilt when its landed file
    (raw._loads) or the reviewed mapping changed since it was built. Filtering bronze on constant wave
    values lets the database skip the other waves' unpivots entirely. -#}
{%- set rebuild = var('waves') %}
{%- if is_incremental() and execute %}
    {%- set loaded = run_query("select wave, sha256 from " ~ source('raw', '_loads')) %}
    {%- set done = run_query("select distinct wave, _file_sha256, _reference_version from " ~ this) %}
    {%- set built = [] %}
    {%- for r in done.rows %}{% do built.append(r[0] | int ~ '|' ~ r[1] ~ '|' ~ r[2]) %}{% endfor %}
    {%- set rebuild = [] %}
    {%- for r in loaded.rows %}
        {%- if (r[0] | int ~ '|' ~ r[1] ~ '|' ~ ref_version) not in built %}{% do rebuild.append(r[0] | int) %}{% endif %}
    {%- endfor %}
{%- endif %}
with responses as (
    select * from {{ ref('brz_item_responses') }}
    where {% if rebuild %}wave in ({{ rebuild | join(', ') }}){% else %}1 = 0{% endif %}
)
select
    r.wave,
    r.respondent_key,
    r.item_code,
    x.question_id,
    q.scale_type,
    r.raw_value,
    try_cast(r.raw_value as integer) as response_code,
    {#- X is "Do Not Know" / "No Basis to Judge": an answer, but not a rating, so it is kept out of
        percent-positive denominators (OPM's method). #}
    r.raw_value = 'X' as is_non_rating,
    case when q.scale_type in ('agreement', 'satisfaction', 'quality', 'frequency') and r.raw_value in ('1','2','3','4','5')
         then case when r.raw_value in ('4','5') then 'positive'
                   when r.raw_value = '3' then 'neutral'
                   else 'negative' end
    end as favorability,
    r._file_sha256,
    '{{ ref_version }}' as _reference_version
from responses r
join {{ ref('question_crosswalk') }} x
    on x.wave = r.wave and x.item_code = r.item_code
left join {{ ref('question_catalog') }} q
    on q.question_id = x.question_id
where x.wording_status <> 'redacted'
