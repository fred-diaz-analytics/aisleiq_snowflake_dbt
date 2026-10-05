-- Extra displays won by a product in a store, total and average, per store, product and day.
select
    id_loja,
    id_produto,
    dt_pesquisa,
    count(*) as qtd_amostras_validas,
    sum(resposta_numero) as ponto_extra_total,
    round(avg(resposta_numero), 2) as ponto_extra_medio
from {{ ref('stg_execucao_pdv') }}
where indicador = 'PONTO_EXTRA' and resposta_valida
group by id_loja, id_produto, dt_pesquisa
