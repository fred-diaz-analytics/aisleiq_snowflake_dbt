-- The incremental dedupe runs one day at a time, selected by source_date (the file
-- date). That is only correct while every answer's survey date is its file date.
-- Returns the answers where the two differ; an unparseable date is the not_null
-- test's business, not this one's.
select
    id_pesquisa_resposta,
    dt_pesquisa,
    source_date
from {{ ref('stg_execucao_pdv_dedup') }}
where dt_pesquisa <> source_date
