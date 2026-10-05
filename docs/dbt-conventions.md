# dbt conventions

Short guide for every model added to the project. Business names stay in Portuguese (domain language, see `GLOSSARY.md`); technical conventions are in English.

## Layers

| Layer | Schema | Folder | Materialization | Content |
|---|---|---|---|---|
| Seeds | `SEEDS` | `dbt/seeds/` | table (seed) | Master data CSVs, copied unchanged from the original project |
| Staging | `STAGING` | `dbt/models/staging/` | view (`table` for `stg_execucao_pdv`, see below) | One model per source entity: column selection, plus typing, dedupe and quality flags when the source needs them. No joins, except the self-join that picks the winning promoter in the survey dedupe. Seed-backed entities need none of these, because seeds are typed on load and keyed uniquely (the tests guard that) |
| Marts | `MARTS` | `dbt/models/marts/` | table | Dimensions, indicators, scores. Joins and business rules live here |

Schema names are clean (no `<target>_` prefix) in both databases; see `dbt/macros/generate_schema_name.sql`.

## Naming

- Staging: `stg_<entity>` (`stg_lojas`, `stg_produtos`). Marts: `dim_<entity>` for dimensions, `fct_<name>` for facts (the six indicators are `fct_presenca`, `fct_ruptura`, `fct_preco`, `fct_mpdv`, `fct_ponto_extra`, `fct_share_gondola`).
- Business targets that are neither facts nor dimensions keep their domain name: `meta_preco`, `meta_share_gondola`, `prioridade_sku`. A mart must not share its name with a seed, because dbt cannot resolve `ref()` then; that is why `prioridade_sku` and `meta_share_gondola` differ from the seeds `sku_prioridade` and `meta_share`.
- Columns keep the domain names in Portuguese and snake_case (`id_loja`, `categoria_loja`, `regiao`). Keys are `id_<entity>`.
- Seed file names match the entity (`lojas.csv`); the seed is referenced with `ref('lojas')` only from its `stg_` model.
- Entities without a source of their own are derived in staging (`stg_marcas` is a `select distinct` over products).

## Model style

- Lowercase SQL keywords, explicit column lists (no `select *`), `left join` from the fact-like side to the lookups.
- Dimensions are flattened: one row per business key, descriptive attributes already resolved, no foreign keys to other marts.
- sqlfluff (Snowflake dialect) must pass; `scripts/check.sh` runs it.

## Tests

- Every model has `unique` + `not_null` on its key.
- Every foreign key has `not_null` + `relationships` to the staging model of the parent entity.
- Closed value sets get `accepted_values`.
- Dimensions test that the attributes resolved by joins are `not_null`, which doubles as a check that no lookup was missed.
- Generic tests use the `arguments:` form (dbt 1.12).
- Flags beat filters in staging: a row that fails a quality rule stays, with `resposta_valida = false`, and the marts filter on the flag. A warn test on the flag records how many rows were flagged.
- A rule that used to be a Databricks `EXPECT` becomes a test; its `severity` says whether it warns or fails. The original `dim_loja` and `dim_produto` had `EXPECT (id_... IS NOT NULL) ON VIOLATION DROP ROW`. Here that is a `not_null` test at the default `error` severity: a null key fails the build instead of silently dropping the row ("record, do not hide"). Use an explicit `where` filter only when dropping rows is the intended behavior. A `EXPECT` without `DROP ROW` (it only recorded the violation) becomes a test with `severity: warn`. The same rule holds for the survey answers (`stg_execucao_pdv`) and for the visits (`stg_atendimentos`), so both domains behave the same way. The original `DROP ROW` rules also dropped, by accident, answers without a date (an inner join on a null date); here those rows stay and are flagged invalid.
- Keys and relationships are tested once, on the staging models. Seeds carry descriptions only. Daily facts in `MARTS` are the exception: their `id_loja` and `id_produto` are also tested against `dim_loja` and `dim_produto`, because the mart-level foreign key is what consumers rely on.
- A grain made of several columns uses the local generic test `unique_combination`; value rules use `non_negative`, `positive` and `value_between` (all in `dbt/tests/generic/`, no external packages).
- Staging models that read `RAW` go through `source('raw', ...)`, declared in `_sources.yml` with a freshness check on `ingested_at`.

## Master data

CSVs in `dbt/seeds/` are copied from the original project without editing, including accents. `dbt seed` reloads them; they are the only files exempt from the English-only text check.

## Materialization exception

`stg_execucao_pdv` is a `table`, not a view: it holds two dedupe steps and a per-SKU median over 1.3M rows, and the six indicator marts would each recompute that on every build. Ticket 06 turns it into an incremental model.

## Typed text dates

Dates that arrive as text are parsed behind a pattern guard (`regexp_like` plus `try_to_date`), because `try_to_date` alone accepts looser shapes than the original `RLIKE`. See `docs/dialect-guide.md` for this and the other dialect differences.

## Scores and the planted-truth test

- The score graph lives in `dbt/models/marts/scores/`. The original numbered files (`00_` to `08_`) become `ref()` dependencies; the models keep the original names (`visitas_completas`, `kpi_disponibilidade_efetiva`, `kpi_preco`, ..., `scores_execucao_pdv`, `qualidade_completude_visita`, `kpi_valor_em_risco`).
- The weights (55/20/15/5/5), the re-weighting and the completeness gate are covered by dbt unit tests in `_scores.yml`, with small hand-computed inputs.
- `dbt/tests/verdade_plantada.sql` is the acceptance test: it ports `validar_verdade_plantada.py` and returns one row per failed criterion. Its answer key is the seed `verdade_plantada`, regenerated by `generator/export_verdade_plantada.py`. The seed and the test are disabled on the `prod` target, because the key is not business data.
- The score models (`marts/scores/`) inherit their keys from the indicator marts, whose `id_loja` and `id_produto` are already tested against the dimensions, so they only carry `not_null` and grain tests plus warn range tests. `qualidade_completude_visita` is a single-row monitor and has no key.
- The seed `verdade_plantada` is the one seed that is generated, not copied from the original project (`generator/export_verdade_plantada.py`), and it is read directly with `ref()` by the singular test `verdade_plantada`, without a `stg_` model. The original kept the answer key out of the lakehouse; here it is a dev-only seed (disabled on `prod`), because a dbt test can only read warehouse tables.
