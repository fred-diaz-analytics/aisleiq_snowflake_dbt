-- Share of valid answers in which the product was out of stock, per store, product and day.
select
    id_loja,
    id_produto,
    dt_pesquisa,
    count(*) as total_avaliacoes,
    count_if(resposta_bool) as total_ruptura,
    round(100.0 * count_if(resposta_bool) / count(*), 2) as pct_ruptura
from {{ ref('stg_execucao_pdv') }}
where indicador = 'RUPTURA' and resposta_valida
group by id_loja, id_produto, dt_pesquisa
