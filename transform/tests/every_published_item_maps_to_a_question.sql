{#- Every item column a wave's file holds has a crosswalk row, so silver's join drops nothing unnoticed. -#}
select distinct b.wave, b.item_code
from {{ ref('brz_item_responses') }} b
left join {{ ref('question_crosswalk') }} x on x.wave = b.wave and x.item_code = b.item_code
where x.item_code is null
