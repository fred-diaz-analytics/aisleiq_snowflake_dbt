-- Visit completeness gate (it does not score by itself: the other score models join it).
-- Presence is the gate: the app only asks stockout, price, share and MPDV for a present
-- product. A visit (store, product, day) is complete when:
--   - presence = NO (absent or delisted product): complete with presence alone. It is the
--     worst execution failure and must be in the score;
--   - presence = YES: it also needs valid stockout, price and shelf share answers.
-- MPDV and extra display are optional and outside the gate (0 extra displays is a valid
-- answer), but they drop out together with an incomplete visit.
-- "Valid" is already guaranteed by the indicator marts, which filter on resposta_valida.
select
    pr.id_loja,
    pr.id_produto,
    pr.dt_pesquisa,
    pr.total_presente > 0 as presente
from {{ ref('fct_presenca') }} as pr
left join {{ ref('fct_ruptura') }} as rp
    on pr.id_loja = rp.id_loja and pr.id_produto = rp.id_produto and pr.dt_pesquisa = rp.dt_pesquisa
left join {{ ref('fct_preco') }} as pc
    on pr.id_loja = pc.id_loja and pr.id_produto = pc.id_produto and pr.dt_pesquisa = pc.dt_pesquisa
left join {{ ref('fct_share_gondola') }} as sg
    on pr.id_loja = sg.id_loja and pr.id_produto = sg.id_produto and pr.dt_pesquisa = sg.dt_pesquisa
where
    pr.total_presente = 0
    or (rp.id_loja is not null and pc.id_loja is not null and sg.id_loja is not null)
