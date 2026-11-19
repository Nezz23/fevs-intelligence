{{ config(tags=["full_data"]) }}
{#- Every governmentwide figure OPM published equals ours once ours is rounded to a whole percent, as OPM
    rounds, except the figures gld_opm_reconciliation lists as not_scored with their reason. -#}
select * from {{ ref('gld_opm_reconciliation') }} where status = 'mismatch'
