{#
  Uses the custom schema exactly as declared (STAGING, MARTS), without the
  <target_schema>_ prefix dbt applies by default. Dev and prod are separated
  by database, not by schema name.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema | trim | upper }}
    {%- else -%}
        {{ custom_schema_name | trim | upper }}
    {%- endif -%}
{%- endmacro %}
