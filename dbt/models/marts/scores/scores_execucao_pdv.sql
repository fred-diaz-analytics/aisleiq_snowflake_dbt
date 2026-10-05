-- Execution score (0-100) per store, day and product category: the five KPI pillars
-- combined with fixed weights 55 / 20 / 15 / 5 / 5 (availability, price, shelf share,
-- extra display, MPDV). A pillar with no data for the (store, category, day) leaves the
-- denominator: the score is re-weighted over the measured pillars, and
-- cobertura_pilares_pct says how much of the total weight was measured. "No data" is not
-- "did not execute": availability is always present and already zeroes absent products.
with pilares as (

    select
        d.id_loja,
        d.dt_pesquisa,
        d.categoria_produto,
        d.disponibilidade_efetiva,
        d.osa_must_have,
        p.avg_nota_preco,
        s.avg_nota_share,
        pe.avg_nota_ponto_extra,
        m.avg_nota_mpdv,
        0.55
        + case when p.avg_nota_preco is not null then 0.20 else 0 end
        + case when s.avg_nota_share is not null then 0.15 else 0 end
        + case when pe.avg_nota_ponto_extra is not null then 0.05 else 0 end
        + case when m.avg_nota_mpdv is not null then 0.05 else 0 end as peso_medido
    from {{ ref('kpi_disponibilidade_efetiva') }} as d
    left join {{ ref('kpi_preco') }} as p
        on d.id_loja = p.id_loja and d.dt_pesquisa = p.dt_pesquisa and d.categoria_produto = p.categoria_produto
    left join {{ ref('kpi_share_gondola') }} as s
        on d.id_loja = s.id_loja and d.dt_pesquisa = s.dt_pesquisa and d.categoria_produto = s.categoria_produto
    left join {{ ref('kpi_ponto_extra') }} as pe
        on d.id_loja = pe.id_loja and d.dt_pesquisa = pe.dt_pesquisa and d.categoria_produto = pe.categoria_produto
    left join {{ ref('kpi_mpdv') }} as m
        on d.id_loja = m.id_loja and d.dt_pesquisa = m.dt_pesquisa and d.categoria_produto = m.categoria_produto

)

select
    id_loja,
    dt_pesquisa,
    categoria_produto,
    disponibilidade_efetiva,
    osa_must_have,
    avg_nota_preco,
    avg_nota_share,
    avg_nota_ponto_extra,
    avg_nota_mpdv,
    round(100 * peso_medido, 2) as cobertura_pilares_pct,
    round(
        (
            0.55 * disponibilidade_efetiva
            + 0.20 * coalesce(avg_nota_preco, 0)
            + 0.15 * coalesce(avg_nota_share, 0)
            + 0.05 * coalesce(avg_nota_ponto_extra, 0)
            + 0.05 * coalesce(avg_nota_mpdv, 0)
        ) / peso_medido,
        2
    ) as score_execucao_pdv
from pilares
