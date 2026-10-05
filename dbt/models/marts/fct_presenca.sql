-- Share of valid answers in which the product was present in the store, per store, product and day.
select
    id_loja,
    id_produto,
    dt_pesquisa,
    count(*) as total_avaliacoes,
    count_if(resposta_bool) as total_presente,
    round(100.0 * count_if(resposta_bool) / count(*), 2) as pct_presenca
from {{ ref('stg_execucao_pdv') }}
where indicador = 'PRESENCA' and resposta_valida
group by id_loja, id_produto, dt_pesquisa
