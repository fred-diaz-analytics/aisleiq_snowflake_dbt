-- Pillar 4 of 5, extra display, weight 5%.
-- Linear 0 to 2: 100 from two extra displays per visit, linear below that.
-- Grain (store, day, product category).
-- Joins visitas_completas: extra display is optional (0 is a valid answer) and outside the
-- gate, but it drops out together with an incomplete visit.
select
    pe.id_loja,
    pe.dt_pesquisa,
    dp.categoria_produto,
    round(avg(least(100, 100.0 * pe.ponto_extra_medio / 2.0)), 2) as avg_nota_ponto_extra
from {{ ref('fct_ponto_extra') }} as pe
inner join {{ ref('visitas_completas') }} as vc
    on pe.id_loja = vc.id_loja and pe.id_produto = vc.id_produto and pe.dt_pesquisa = vc.dt_pesquisa
inner join {{ ref('dim_produto') }} as dp on pe.id_produto = dp.id_produto
group by pe.id_loja, pe.dt_pesquisa, dp.categoria_produto
