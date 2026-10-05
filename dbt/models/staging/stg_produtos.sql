select
    id_produto,
    produto,
    tamanho,
    id_marca,
    id_categoria
from {{ ref('produtos') }}
