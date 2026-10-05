-- Pillar 1 of 5, effective availability (OSA), weight 55%.
-- Per SKU visit first: OSA = presence x (1 - stockout), 0-100; an absent product enters
-- with OSA = 0. Then aggregated to (store, day, product category) as the average weighted
-- by the SKU's weekly value in the store's channel (turnover x suggested price,
-- prioridade_sku): a flagship stockout weighs more than a tail SKU.
-- osa_must_have: plain OSA over must-have SKUs only, the base of "Perfect Store".
-- categoria_produto comes from dim_produto and categoria_loja from dim_loja.
with osa_sku as (

    select
        vc.id_loja,
        vc.id_produto,
        vc.dt_pesquisa,
        dp.categoria_produto,
        pr.pct_presenca,
        rp.pct_ruptura,
        sp.valor_semanal as peso,
        sp.must_have,
        pr.pct_presenca * (100 - coalesce(rp.pct_ruptura, 0)) / 100 as osa
    from {{ ref('visitas_completas') }} as vc
    inner join {{ ref('fct_presenca') }} as pr
        on vc.id_loja = pr.id_loja and vc.id_produto = pr.id_produto and vc.dt_pesquisa = pr.dt_pesquisa
    inner join {{ ref('dim_produto') }} as dp on vc.id_produto = dp.id_produto
    inner join {{ ref('dim_loja') }} as dl on vc.id_loja = dl.id_loja
    inner join {{ ref('prioridade_sku') }} as sp
        on vc.id_produto = sp.id_produto and dl.categoria_loja = sp.categoria_loja
    left join {{ ref('fct_ruptura') }} as rp
        on vc.id_loja = rp.id_loja and vc.id_produto = rp.id_produto and vc.dt_pesquisa = rp.dt_pesquisa

)

select
    id_loja,
    dt_pesquisa,
    categoria_produto,
    round(avg(pct_presenca), 2) as avg_disp,
    -- over present SKUs only: an absent SKU has no stockout answer
    round(100 - avg(pct_ruptura), 2) as avg_shelf_disp,
    round(sum(osa * peso) / sum(peso), 2) as disponibilidade_efetiva,
    round(avg(case when must_have then osa end), 2) as osa_must_have
from osa_sku
group by id_loja, dt_pesquisa, categoria_produto
