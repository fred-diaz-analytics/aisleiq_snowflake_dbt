-- Pillar 3 of 5, shelf share, weight 15%.
-- Target: shelf share goal per brand x channel (meta_share_gondola). 100 when the goal is
-- met or beaten, linear down to 0 below it.
-- Grain (store, day, product category): simple average over brands and sizes.
-- Joins visitas_completas: an absent product has no share.
with share_score as (

    select
        sg.id_loja,
        sg.dt_pesquisa,
        dp.categoria_produto,
        round(least(100, 100.0 * sg.share_medio / ms.meta_share_pct), 2) as nota_share
    from {{ ref('fct_share_gondola') }} as sg
    inner join {{ ref('visitas_completas') }} as vc
        on sg.id_loja = vc.id_loja and sg.id_produto = vc.id_produto and sg.dt_pesquisa = vc.dt_pesquisa
    inner join {{ ref('dim_produto') }} as dp on sg.id_produto = dp.id_produto
    inner join {{ ref('dim_loja') }} as dl on sg.id_loja = dl.id_loja
    inner join {{ ref('meta_share_gondola') }} as ms
        on dp.marca = ms.marca and dl.categoria_loja = ms.categoria_loja

)

select
    id_loja,
    dt_pesquisa,
    categoria_produto,
    round(avg(nota_share), 2) as avg_nota_share
from share_score
group by id_loja, dt_pesquisa, categoria_produto
