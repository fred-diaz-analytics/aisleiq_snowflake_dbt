-- Pillar 2 of 5, price, weight 20%.
-- Target: suggested price per SKU x channel (meta_preco), with the tolerance band from the
-- target itself. Asymmetric curve:
--   inside the band (default -3% to +5%): 100
--   below the band: steep (quadratic) drop, about 0 at the red line of -18%
--   above the band: soft drop, reaching a low floor near +35%
-- Grain (store, day, product category): simple average over brands and sizes.
-- Joins visitas_completas: an absent product has no price (its failure is counted in availability).
with preco_base as (

    select
        p.id_loja,
        p.id_produto,
        dp.categoria_produto,
        p.dt_pesquisa,
        (p.preco_observado - mp.preco_sugerido) / mp.preco_sugerido as desvio_pct,
        mp.banda_min_pct / 100 as banda_min,
        mp.banda_max_pct / 100 as banda_max
    from {{ ref('fct_preco') }} as p
    inner join {{ ref('visitas_completas') }} as vc
        on p.id_loja = vc.id_loja and p.id_produto = vc.id_produto and p.dt_pesquisa = vc.dt_pesquisa
    inner join {{ ref('dim_produto') }} as dp on p.id_produto = dp.id_produto
    inner join {{ ref('dim_loja') }} as dl on p.id_loja = dl.id_loja
    inner join {{ ref('meta_preco') }} as mp
        on p.id_produto = mp.id_produto and dl.categoria_loja = mp.categoria_loja

),

preco_score as (

    select
        id_loja,
        id_produto,
        categoria_produto,
        dt_pesquisa,
        desvio_pct,
        round(
            greatest(
                0.01,
                case
                    when desvio_pct <= -0.18 then 0.01
                    when desvio_pct < banda_min
                        then
                            1 - power((abs(desvio_pct) - abs(banda_min)) / (0.18 - abs(banda_min)), 2)
                    when desvio_pct <= banda_max then 1
                    else 1 - 10 * power(desvio_pct - banda_max, 2)
                end
            ) * 100,
            2
        ) as nota_preco
    from preco_base

)

select
    id_loja,
    dt_pesquisa,
    categoria_produto,
    round(avg(nota_preco), 2) as avg_nota_preco,
    round(100 * avg(desvio_pct), 2) as avg_desvio_preco_pct
from preco_score
group by id_loja, dt_pesquisa, categoria_produto
