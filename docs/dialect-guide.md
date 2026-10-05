# Databricks to Snowflake dialect guide

Differences found while migrating the original AisleIQ SQL. Each row is something that either changed the SQL or could have changed the result silently. The guide grows with every ticket; the closing ticket polishes it.

| Topic | Databricks (original) | Snowflake / dbt (here) | Why it matters |
|---|---|---|---|
| Null order on `asc` | Nulls first | Nulls last | A tie-break such as `order by dt_gravacao asc` picks another row when the column has nulls. Use `asc nulls first` to keep the original result |
| Regex match | `RLIKE` matches anywhere, so patterns carry `^...$` | `REGEXP_LIKE` must match the whole string; anchors are implicit | Patterns ported with `^` and `$` still work, but are redundant |
| Date and time formats | `yyyy-MM-dd`, `dd/MM/yyyy HH:mm:ss` | `YYYY-MM-DD`, `DD/MM/YYYY HH24:MI:SS` | Different format tokens; use `HH24` for the 24-hour clock |
| Safe date parse | `to_date(x, fmt)` after an `RLIKE` guard | `try_to_date(x, fmt)` behind a `regexp_like` guard | `try_to_date` alone accepts shapes the original rejected, so the guard stays |
| Safe timestamp parse | `TRY_CAST(to_timestamp(x, fmt) AS TIMESTAMP)` | `try_to_timestamp(x, fmt)` | `to_timestamp` raises on bad input in Snowflake; the `try_` variant returns null |
| `TRY_CAST` | Any type | Text input only | Fine for the raw `VARCHAR` answers; cast numbers with `::` or `cast` |
| Whitespace in numbers | `cast` ignores surrounding spaces | Not relied on: trim explicitly | `R$ 5,90` becomes ` 5.90` after removing `R$`; trim before casting |
| Decimal type | `DECIMAL(10, 2)` | `NUMBER(10, 2)` (`DECIMAL` is an alias) | Same behavior, different spelling in docs and DDL |
| Median | `PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY x)` in a join of aggregates | `median(x) over (partition by k)` | One window per statistic, no self-join. A median of medians cannot be nested in one window: split it in two CTEs (median, then median of absolute deviations) |
| Dedupe | Subquery with `ROW_NUMBER()`, then `SELECT * EXCEPT (rn)` | `qualify row_number() over (...) = 1` | No helper column to drop. `EXCEPT` is `EXCLUDE` in Snowflake |
| Conditional count | `SUM(CASE WHEN b THEN 1 ELSE 0 END)` | `count_if(b)` | Shorter and null-safe |
| Null-safe join | Not needed in the original, which dropped null dates by accident in an inner join | `is not distinct from` | Keeps rows without a date (flagged invalid) instead of silently losing them |
| `EXPECT` constraints | `CONSTRAINT x EXPECT (...)`, optional `ON VIOLATION DROP ROW` | dbt data test; `severity` warn or error | `DROP ROW` becomes an error test so nothing disappears quietly. See `docs/dbt-conventions.md` |
| Same name for a seed and a model | Not applicable | dbt refuses an ambiguous `ref()` | The target seeds `sku_prioridade` and `meta_share` forced the marts to be `prioridade_sku` and `meta_share_gondola` |
| Unquoted identifiers | Case preserved | Upper-cased | Never quote identifiers; reference columns in lower case in SQL |
