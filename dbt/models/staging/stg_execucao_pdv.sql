-- Survey answers after the incremental dedupe (stg_execucao_pdv_dedup), plus the
-- price outlier flag and the final resposta_valida. Kept as a table, not a view:
-- the per-SKU median below would otherwise run once per mart.
-- The median and MAD are computed per SKU over all days, so a new day moves them
-- and can flip the flag of an old row. That cannot be done inside a one-day
-- microbatch; the median and MAD scan only the PRECO rows (about a sixth of the data).

with preco_mediana as (

    -- median per SKU over structurally valid prices only
    select
        id_pesquisa_resposta,
        id_produto,
        resposta_preco,
        median(resposta_preco) over (partition by id_produto) as mediana_preco
    from {{ ref('stg_execucao_pdv_dedup') }}
    where indicador = 'PRECO' and resposta_valida_estrutural

),

preco_mad as (

    -- MAD: median absolute deviation from the SKU median. A robust z-score is used instead
    -- of the plain one because median and MAD are not pulled by the outliers being hunted.
    select
        id_pesquisa_resposta,
        resposta_preco,
        mediana_preco,
        median(abs(resposta_preco - mediana_preco)) over (partition by id_produto) as mad_preco
    from preco_mediana

),

preco_outlier as (

    -- no calculable MAD (zero, or a single price): not an outlier, as in the original
    select
        id_pesquisa_resposta,
        mediana_preco,
        mad_preco,
        case
            when mad_preco > 0 then abs(0.6745 * (resposta_preco - mediana_preco) / mad_preco)
        end as robust_z_score,
        coalesce(mad_preco > 0 and abs(0.6745 * (resposta_preco - mediana_preco) / mad_preco) > 3.5, false)
            as flag_outlier_preco
    from preco_mad

)

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
    d.resposta_bool,
    d.resposta_numero,
    d.resposta_preco,
    d.resposta_percentual,
    d.source_file,
    d.source_date,
    d.ingested_at,
    round(o.mediana_preco, 2) as mediana_preco,
    round(o.mad_preco, 2) as mad_preco,
    round(o.robust_z_score, 2) as robust_z_score,
    coalesce(o.flag_outlier_preco, false) as flag_outlier_preco,
    d.resposta_valida_estrutural and not coalesce(o.flag_outlier_preco, false) as resposta_valida
from {{ ref('stg_execucao_pdv_dedup') }} as d
left join preco_outlier as o on d.id_pesquisa_resposta = o.id_pesquisa_resposta
