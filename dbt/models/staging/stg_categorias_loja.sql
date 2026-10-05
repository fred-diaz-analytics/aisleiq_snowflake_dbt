select
    id_categoria_loja,
    categoria_loja
from {{ ref('categorias_loja') }}
