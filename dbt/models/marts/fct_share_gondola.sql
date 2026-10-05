-- Average shelf share of a product in a store, per store, product and day.
select
    id_loja,
    id_produto,
    dt_pesquisa,
    count(*) as qtd_amostras,
    round(avg(resposta_percentual), 2) as share_medio
from {{ ref('stg_execucao_pdv') }}
where indicador = 'SHARE_GONDOLA' and resposta_valida
group by id_loja, id_produto, dt_pesquisa
