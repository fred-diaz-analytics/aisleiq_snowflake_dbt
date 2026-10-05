-- Price charged for a product in a store, per store, product and day. The survey
-- keeps one answer per combination (the dedupe in stg_execucao_pdv), so max() only
-- picks that answer. Price outliers are already out through resposta_valida.
select
    id_loja,
    id_produto,
    dt_pesquisa,
    max(resposta_preco) as preco_observado
from {{ ref('stg_execucao_pdv') }}
where indicador = 'PRECO' and resposta_valida
group by id_loja, id_produto, dt_pesquisa
