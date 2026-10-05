select
    id_marca,
    categoria_loja,
    meta_share_pct
from {{ ref('meta_share') }}
