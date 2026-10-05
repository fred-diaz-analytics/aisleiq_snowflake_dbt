# AisleIQ em Snowflake + dbt

[Read in English](README.md)

Analítica de execução em ponto de venda (trade marketing) sobre dados 100% sintéticos: como os produtos são expostos, precificados e sinalizados nas lojas, e como os promotores cumprem as visitas. Esta é a reconstrução do AisleIQ em Snowflake + dbt, com o mesmo domínio e o mesmo gerador sintético da versão original em Databricks. Sem dados reais nem PII.

Os termos de negócio ficam em português (veja o [`GLOSSARY.md`](GLOSSARY.md)); as convenções técnicas ficam em inglês.

## Como funciona

```
gerador (parquet, arquivos diários)
   -> ingestion/ingest.py (PUT no stage, COPY INTO)   -> RAW
   -> seeds do dbt (dado mestre)                      -> SEEDS
   -> staging do dbt (tipagem, dedupe, qualidade)     -> STAGING
   -> marts do dbt (indicadores, dimensões, scores)   -> MARTS
```

Visão completa, mapa de camadas e lineage: [`docs/architecture.md`](docs/architecture.md) (em inglês).

## Documentação

A documentação detalhada está em inglês, na pasta `docs/`:

| Documento | Conteúdo |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Camadas, mapa bronze/silver/gold para RAW/STAGING/MARTS, lineage |
| [`docs/indicators.md`](docs/indicators.md) | Dicionário de dados: indicadores, dimensões, grafo de scores |
| [`docs/dialect-guide.md`](docs/dialect-guide.md) | Diferenças de SQL Databricks para Snowflake encontradas na migração |
| [`docs/dbt-conventions.md`](docs/dbt-conventions.md) | Nomes, testes, decisões de materialização |
| [`docs/setup.md`](docs/setup.md) | Recriar o ambiente do zero (inclusive após o fim do trial) |
| [`docs/orchestration.md`](docs/orchestration.md) | Comando único, agendamento diário no GitHub Actions, segredos num repo público |

## Início rápido

```bash
python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements-dev.txt   # Windows
bash scripts/setup_snowflake.sh            # provisionamento guiado, uma vez por conta
set -a; source ~/.aisleiq/aisleiq.env; set +a
bash scripts/run_all.sh                    # gera, ingere, dbt seed + build (dev)
```

`bash scripts/run_all.sh --docs` também gera o site de documentação do dbt; para abri-lo, rode `dbt docs serve` dentro de `dbt/`.

## Aceitação

A migração é aceita quando o `dbt build` passa em `AISLEIQ_DEV` e os KPIs em `MARTS` recuperam a verdade plantada (`dbt/tests/verdade_plantada.sql`).

## Verificações

`bash scripts/check.sh` roda ruff, yamllint, sqlfluff (dialeto Snowflake), shellcheck, `dbt parse`, pytest e uma varredura de vazamentos, sem credenciais. O CI roda o mesmo script.

## Ideias de continuação

- Rodar o mesmo projeto no dbt Cloud (plano gratuito) para conhecer o agendador e o CI gerenciados.
- Rodar no dbt Fusion e comparar com o dbt-core.
- Testar Snowflake Tasks como agendador e comparar com o GitHub Actions.
