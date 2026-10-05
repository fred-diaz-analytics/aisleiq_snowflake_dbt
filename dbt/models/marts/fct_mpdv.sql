-- Share of valid answers in which point-of-sale material was activated, per store, product and day.
select
    id_loja,
    id_produto,
    dt_pesquisa,
    count(*) as total_avaliacoes,
    count_if(resposta_bool) as total_material_ativado,
    round(100.0 * count_if(resposta_bool) / count(*), 2) as pct_material_ativado
from {{ ref('stg_execucao_pdv') }}
where indicador = 'MPDV' and resposta_valida
group by id_loja, id_produto, dt_pesquisa
