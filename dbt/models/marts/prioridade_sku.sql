-- SKU importance per channel. valor_semanal (expected weekly turnover x suggested
-- price, R$/week) weights the SKU in effective availability and is the base of
-- the value at risk: a flagship out of stock weighs more than a tail SKU.
select
    p.id_produto,
    p.categoria_loja,
    p.giro_semanal_un,
    p.must_have,
    round(p.giro_semanal_un * m.preco_sugerido, 2) as valor_semanal
from {{ ref('stg_sku_prioridade') }} as p
left join {{ ref('stg_preco_sugerido') }} as m
    on
        p.id_produto = m.id_produto
        and p.categoria_loja = m.categoria_loja
