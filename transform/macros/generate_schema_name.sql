{# Use the layer's schema name as written (bronze, silver, gold, reference), not target_schema + "_" + name. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name | trim if custom_schema_name else target.schema }}
{%- endmacro %}
