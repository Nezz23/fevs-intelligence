-- One-time Snowflake setup for FEVS Intelligence. Run once, as ACCOUNTADMIN, in a Snowsight worksheet
-- (select all, then Run). Replace <PUBLIC_KEY> with the body of the public key (no BEGIN/END lines).
--
-- Cost guards: one X-Small warehouse that suspends after 60 s idle, and a resource monitor that
-- stops it at 10 credits a month, well inside the trial's free credits.

use role accountadmin;

create resource monitor if not exists fevs_monthly_cap
  with credit_quota = 10 frequency = monthly start_timestamp = immediately
  triggers on 80 percent do notify
           on 100 percent do suspend_immediate;

create warehouse if not exists fevs_xs
  warehouse_size = xsmall auto_suspend = 60 auto_resume = true initially_suspended = true
  comment = 'dbt builds for FEVS Intelligence';
alter warehouse fevs_xs set resource_monitor = fevs_monthly_cap;

create database if not exists fevs comment = 'FEVS Intelligence warehouse';

-- dbt runs as a role that owns only this database and may use only this warehouse.
create role if not exists transformer;
grant usage on warehouse fevs_xs to role transformer;
grant usage, create schema on database fevs to role transformer;
grant role transformer to role sysadmin;

-- A service user: no password, key-pair login only, so no secret is ever typed or sent anywhere.
create user if not exists dbt_svc
  type = service
  default_role = transformer
  default_warehouse = fevs_xs
  default_namespace = fevs.main
  rsa_public_key = '<PUBLIC_KEY>'
  comment = 'dbt for FEVS Intelligence (key-pair auth)';
grant role transformer to user dbt_svc;

-- No grant to your own login is needed: transformer is granted to sysadmin, which accountadmin
-- inherits, so your admin login already sees everything dbt builds.

select current_account() as account_locator, current_region() as region,
       current_organization_name() || '-' || current_account_name() as account_identifier;
