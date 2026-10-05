select
    p.id_produto,
    p.produto,
    p.tamanho,
    m.marca,
    c.categoria_produto
from {{ ref('stg_produtos') }} as p
left join {{ ref('stg_marcas') }} as m on p.id_marca = m.id_marca
left join {{ ref('stg_categorias') }} as c on p.id_categoria = c.id_categoria
