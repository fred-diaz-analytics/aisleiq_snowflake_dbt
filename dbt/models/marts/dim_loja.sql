select
    l.id_loja,
    l.nome_fantasia,
    l.endereco,
    r.nome_rede as rede,
    cl.categoria_loja,
    c.cidade,
    e.uf,
    e.regiao
from {{ ref('stg_lojas') }} as l
left join {{ ref('stg_redes') }} as r on l.id_rede = r.id_rede
left join {{ ref('stg_categorias_loja') }} as cl on l.id_categoria_loja = cl.id_categoria_loja
left join {{ ref('stg_cidades') }} as c on l.id_cidade = c.id_cidade
left join {{ ref('stg_estados') }} as e on c.uf = e.uf
