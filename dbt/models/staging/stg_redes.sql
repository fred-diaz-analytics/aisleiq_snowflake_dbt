select
    id_rede,
    nome_rede
from {{ ref('redes') }}
