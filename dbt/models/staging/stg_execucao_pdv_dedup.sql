-- Survey answers (one row per store x product x question), typed per indicator,
-- flagged with resposta_valida_estrutural and deduplicated in two steps. Incremental
-- by microbatch (config in dbt_project.yml): each batch is one day, read from RAW by source_date (the file date,
-- always filled; a test checks that it equals dt_pesquisa) and replaced as a whole,
-- so a late file for an old day rebuilds that day and the dedupe sees all of its rows.
-- Both dedupe steps partition by day, which is why a batch is enough to run them.
-- Anything that spans days (the per-SKU price median) lives in stg_execucao_pdv.
-- produto, marca and categoria_produto are left out: id_produto + dim_produto
-- recover them.

with typed as (

    select
        id_pesquisa_resposta,
        id_usuario,
        nome,
        cargo,
        id_loja,
        id_produto,
        indicador,
        grupo_pesquisa,
        desc_pergunta,
        resposta as resposta_raw,
        checkin_valido,
        source_file,
        source_date,
        ingested_at,
        -- the pattern guard keeps try_to_date from accepting looser shapes than the original RLIKE did
        coalesce(
            case when regexp_like(dt_pesquisa, '[0-9]{4}-[0-9]{2}-[0-9]{2}') then try_to_date(dt_pesquisa, 'YYYY-MM-DD') end,
            case when regexp_like(dt_pesquisa, '[0-9]{2}/[0-9]{2}/[0-9]{4}') then try_to_date(dt_pesquisa, 'DD/MM/YYYY') end,
            case when regexp_like(dt_pesquisa, '[0-9]{8}') then try_to_date(dt_pesquisa, 'YYYYMMDD') end
        ) as dt_pesquisa,
        try_to_timestamp(dt_gravacao, 'DD/MM/YYYY HH24:MI:SS') as dt_gravacao
    from {{ source('raw', 'execucao_pdv') }}

),

clean as (

    select
        id_pesquisa_resposta,
        id_usuario,
        nome,
        cargo,
        id_loja,
        id_produto,
        indicador,
        grupo_pesquisa,
        desc_pergunta,
        resposta_raw,
        checkin_valido,
        dt_pesquisa,
        dt_gravacao,
        source_file,
        source_date,
        ingested_at,
        -- PRESENCA, RUPTURA, MPDV: SIM / NAO to boolean ("N.O" tolerates the accent encoding of NAO)
        case
            when indicador in ('PRESENCA', 'RUPTURA', 'MPDV') then
                case
                    when upper(trim(resposta_raw)) = 'SIM' then true
                    when regexp_like(upper(trim(resposta_raw)), 'N.O') then false
                end
        end as resposta_bool,
        -- PONTO_EXTRA: integer count (the sentinel -1 is flagged as invalid below)
        case
            when indicador = 'PONTO_EXTRA' and regexp_like(trim(resposta_raw), '-?[0-9]+')
                then try_cast(trim(resposta_raw) as integer)
        end as resposta_numero,
        -- PRECO: drop "R$", decimal comma to point (trim again: "R$ 5,90" leaves a space)
        case
            when indicador = 'PRECO'
                then try_cast(trim(replace(replace(trim(resposta_raw), 'R$', ''), ',', '.')) as number(10, 2))
        end as resposta_preco,
        -- SHARE_GONDOLA: drop "%"
        case
            when indicador = 'SHARE_GONDOLA'
                then try_cast(trim(replace(trim(resposta_raw), '%', '')) as number(10, 2))
        end as resposta_percentual
    from typed

),

flagged as (

    -- structural validity only; the statistical price outlier is added further down,
    -- after the dedupe, so that duplicates do not count twice in the per-SKU median.
    select
        id_pesquisa_resposta,
        id_usuario,
        nome,
        cargo,
        id_loja,
        id_produto,
        indicador,
        grupo_pesquisa,
        desc_pergunta,
        resposta_raw,
        checkin_valido,
        dt_pesquisa,
        dt_gravacao,
        source_file,
        source_date,
        ingested_at,
        resposta_bool,
        resposta_numero,
        resposta_preco,
        resposta_percentual,
        case
            when indicador = 'PONTO_EXTRA' and (resposta_numero is null or resposta_numero = -1) then false
            when
                indicador = 'SHARE_GONDOLA'
                and (resposta_percentual is null or resposta_percentual < 0 or resposta_percentual > 100)
                then false
            when indicador = 'PRECO' and (resposta_preco is null or resposta_preco <= 0) then false
            when indicador in ('PRESENCA', 'RUPTURA', 'MPDV') and resposta_bool is null then false
            when dt_pesquisa is null then false
            else true
        end as resposta_valida_estrutural
    from clean

),

dedup_sync as (

    -- ~3% of the answers are synced twice by the app (same content, new
    -- id_pesquisa_resposta, later dt_gravacao). Keep the first sync.
    -- Snowflake sorts nulls last on asc, Databricks first: nulls first keeps the original tie-break.
    select
        id_pesquisa_resposta,
        id_usuario,
        nome,
        cargo,
        id_loja,
        id_produto,
        indicador,
        grupo_pesquisa,
        desc_pergunta,
        resposta_raw,
        checkin_valido,
        dt_pesquisa,
        dt_gravacao,
        source_file,
        source_date,
        ingested_at,
        resposta_bool,
        resposta_numero,
        resposta_preco,
        resposta_percentual,
        resposta_valida_estrutural
    from flagged
    qualify row_number() over (
        partition by id_loja, id_produto, indicador, id_usuario, dt_pesquisa
        order by dt_gravacao asc nulls first, id_pesquisa_resposta asc
    ) = 1

),

winner as (

    -- one promoter per store and day: the one with most answers, ties by lowest id_usuario
    select
        id_loja,
        dt_pesquisa,
        id_usuario
    from dedup_sync
    group by id_loja, dt_pesquisa, id_usuario
    qualify row_number() over (
        partition by id_loja, dt_pesquisa
        order by count(*) desc, id_usuario asc
    ) = 1

)

-- is not distinct from: a row with a null key or date stays (the not_null tests see it) instead of vanishing
select
    d.id_pesquisa_resposta,
    d.id_usuario,
    d.nome,
    d.cargo,
    d.id_loja,
    d.id_produto,
    d.indicador,
    d.grupo_pesquisa,
    d.desc_pergunta,
    d.resposta_raw,
    d.checkin_valido,
    d.dt_pesquisa,
    d.dt_gravacao,
    d.source_file,
    d.source_date,
    d.ingested_at,
    d.resposta_bool,
    d.resposta_numero,
    d.resposta_preco,
    d.resposta_percentual,
    d.resposta_valida_estrutural
from dedup_sync as d
inner join winner as w
    on
        d.id_loja is not distinct from w.id_loja
        and d.dt_pesquisa is not distinct from w.dt_pesquisa
        and d.id_usuario is not distinct from w.id_usuario
