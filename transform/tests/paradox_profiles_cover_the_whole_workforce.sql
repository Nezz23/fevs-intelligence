{#- The 16 profiles of each wave partition its profiled respondents: their weighted shares sum to 1. -#}
select wave, sum(share_of_workforce) as total
from {{ ref('gld_workplace_paradox') }}
group by wave
having abs(sum(share_of_workforce) - 1) > 1e-9
