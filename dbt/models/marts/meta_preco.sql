-- Business target, neither fact nor dimension: suggested price per product x
-- channel (categoria_loja) and its tolerance band. Joins to a store through
-- dim_loja.categoria_loja.
select
    id_produto,
    categoria_loja,
    preco_sugerido,
    banda_min_pct,
    banda_max_pct,
    vigencia_inicio
from {{ ref('stg_preco_sugerido') }}
