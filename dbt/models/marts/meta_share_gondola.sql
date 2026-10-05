-- Business target: shelf share goal (%) per brand x channel. The brand name is
-- flattened in, so it joins to dim_produto by marca (star pattern).
select
    s.id_marca,
    m.marca,
    s.categoria_loja,
    s.meta_share_pct
from {{ ref('stg_meta_share') }} as s
left join {{ ref('stg_marcas') }} as m on s.id_marca = m.id_marca
