-- Does not score: translates availability failure into R$. Per (store, day, category) it sums
-- the weekly value (expected turnover x suggested price, prioridade_sku) of the SKUs that were
-- unavailable in the visit, either absent (delisted) or in stockout. It is the prioritization
-- ruler: where the wrong shelf costs more, not only where the score is lower.
-- Proxy without sell-out: an unavailable SKU is assumed to lose its whole expected turnover
-- until fixed (no shopper substitution).
with sku_visita as (

    select
        vc.id_loja,
        vc.dt_pesquisa,
        dp.categoria_produto,
        sp.must_have,
        sp.valor_semanal,
        vc.presente and coalesce(rp.total_ruptura, 0) = 0 as disponivel
    from {{ ref('visitas_completas') }} as vc
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
    count(*) as skus_avaliados,
    count_if(not disponivel) as skus_indisponiveis,
    count_if(not disponivel and must_have) as must_have_indisponiveis,
    round(sum(case when not disponivel then valor_semanal else 0 end), 2) as valor_em_risco_semanal
from sku_visita
group by id_loja, dt_pesquisa, categoria_produto
