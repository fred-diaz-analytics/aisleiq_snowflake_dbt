select
    id_produto,
    categoria_loja,
    giro_semanal_un,
    must_have
from {{ ref('sku_prioridade') }}
