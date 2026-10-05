select
    id_produto,
    categoria_loja,
    preco_sugerido,
    banda_min_pct,
    banda_max_pct,
    vigencia_inicio
from {{ ref('preco_sugerido') }}
