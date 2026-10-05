select
    id_categoria,
    categoria_produto
from {{ ref('categorias') }}
