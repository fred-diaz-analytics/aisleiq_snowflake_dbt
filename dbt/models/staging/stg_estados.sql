select
    uf,
    nome_estado,
    regiao
from {{ ref('estados') }}
