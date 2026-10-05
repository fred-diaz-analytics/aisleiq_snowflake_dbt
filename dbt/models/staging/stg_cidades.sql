select
    id_cidade,
    cidade,
    uf
from {{ ref('cidades') }}
