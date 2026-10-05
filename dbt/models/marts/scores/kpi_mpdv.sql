-- Pillar 5 of 5, MPDV (point-of-sale material), weight 5%.
-- Binary: YES = 100, NO = 0. fct_mpdv already holds the share of YES among valid answers
-- per (store, product, day); here it rolls up to (store, day, product category).
-- Joins visitas_completas: MPDV is optional and outside the gate, but it drops out
-- together with an incomplete visit.
select
    m.id_loja,
    m.dt_pesquisa,
    dp.categoria_produto,
    round(avg(m.pct_material_ativado), 2) as avg_nota_mpdv
from {{ ref('fct_mpdv') }} as m
inner join {{ ref('visitas_completas') }} as vc
    on m.id_loja = vc.id_loja and m.id_produto = vc.id_produto and m.dt_pesquisa = vc.dt_pesquisa
inner join {{ ref('dim_produto') }} as dp on m.id_produto = dp.id_produto
group by m.id_loja, m.dt_pesquisa, dp.categoria_produto
