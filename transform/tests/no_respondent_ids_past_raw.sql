{#- Published respondent IDs (USERID, RandomID) never reach bronze, silver or gold. -#}
select table_schema, table_name, column_name
from information_schema.columns
where lower(table_schema) in ('bronze', 'silver', 'gold')
  and upper(column_name) in ('USERID', 'RANDOMID')
