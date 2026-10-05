# Data dictionary: indicators, dimensions and scores

Column-level descriptions live in the dbt YAML files (`dbt/models/**/_*.yml`) and in the generated dbt docs. This page is the map. Terms are defined in `GLOSSARY.md`.

## Dimensions

| Model | Grain | Notes |
|---|---|---|
| `dim_loja` | one row per store | chain, store category, city, UF and region resolved |
| `dim_produto` | one row per product | brand and product category resolved |

## The six indicators (daily, per store and product)

Only valid answers (`resposta_valida`) count. Each answer is typed by its indicator.

| Model | Measures | Type |
|---|---|---|
| `fct_presenca` | share of answers where the product was present | boolean |
| `fct_ruptura` | share of answers where the product was out of stock | boolean |
| `fct_preco` | price charged, without price outliers | decimal |
| `fct_mpdv` | share of answers where point-of-sale material was activated | boolean |
| `fct_ponto_extra` | extra displays, total and average | integer |
| `fct_share_gondola` | average shelf share | percentage |

Visit tables, from the attendance record: `fct_cumprimento_visita` (OK / NP / X per promoter, store, day) and `fct_tempo_loja` (minutes in store).

## Targets

`meta_preco` (suggested price with tolerance band), `meta_share_gondola` (share goal per brand and channel) and `prioridade_sku` (turnover, must-have flag, weekly value).

## Score graph (`dbt/models/marts/scores/`)

| Model | Role | Weight |
|---|---|---|
| `visitas_completas` | completeness gate: incomplete visits do not score | gate |
| `kpi_disponibilidade_efetiva` | effective availability (OSA), weighted by weekly SKU value | 55% |
| `kpi_preco` | price adherence to the suggested price | 20% |
| `kpi_share_gondola` | shelf share against the goal | 15% |
| `kpi_ponto_extra` | extra displays per visit | 5% |
| `kpi_mpdv` | MPDV activated | 5% |
| `scores_execucao_pdv` | execution score 0 to 100 per store, day and category, plus pillar coverage | |
| `kpi_valor_em_risco` | weekly value of absent or out-of-stock SKUs | |
| `qualidade_completude_visita` | one-row monitor of the gate | |

A pillar with no data leaves the denominator, and the pillar coverage says how much weight was measured.

## Quality rules (staging)

An answer is invalid when it has a sentinel value, a percentage out of range, a non-positive price, or a price outlier (robust z-score on median and MAD per SKU). Invalid rows stay in staging with `resposta_valida = false`. Sync duplicates keep the first row; for a store with several promoters on one day, the promoter with the most answers wins.

## Acceptance

`dbt/tests/verdade_plantada.sql` proves that the KPIs recover the effects planted in the synthetic data.
