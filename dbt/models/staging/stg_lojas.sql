select
    id_loja,
    nome_fantasia,
    endereco,
    id_cidade,
    id_categoria_loja,
    id_rede
from {{ ref('lojas') }}
