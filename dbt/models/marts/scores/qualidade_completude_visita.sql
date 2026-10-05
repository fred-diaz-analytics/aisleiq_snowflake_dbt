-- Monitoring of the completeness gate (visitas_completas). It does not feed the score: it makes
-- discarded visits visible. It shows which of the three required indicators was missing most.
-- The faltou_* columns are not mutually exclusive (a visit can miss more than one), so they do
-- not add up to visitas_incompletas. An absent product (presence = NO) is complete by
-- definition: it is not counted as a missing indicator, only in skus_ausentes.
with universo as (

    select
        id_loja,
        id_produto,
        dt_pesquisa
    from {{ ref('fct_presenca') }}
    union distinct
    select
        id_loja,
        id_produto,
        dt_pesquisa
    from {{ ref('fct_ruptura') }}
    union distinct
    select
        id_loja,
        id_produto,
        dt_pesquisa
    from {{ ref('fct_preco') }}
    union distinct
    select
        id_loja,
        id_produto,
        dt_pesquisa
    from {{ ref('fct_share_gondola') }}

),

flag as (

    select
        u.id_loja,
        u.id_produto,
        u.dt_pesquisa,
        p.id_loja is not null as tem_presenca,
        r.id_loja is not null as tem_ruptura,
        pc.id_loja is not null as tem_preco,
        s.id_loja is not null as tem_share,
        coalesce(not vc.presente, false) as ausente,
        vc.id_loja is not null as completa
    from universo as u
    left join {{ ref('fct_presenca') }} as p
        on u.id_loja = p.id_loja and u.id_produto = p.id_produto and u.dt_pesquisa = p.dt_pesquisa
    left join {{ ref('fct_ruptura') }} as r
        on u.id_loja = r.id_loja and u.id_produto = r.id_produto and u.dt_pesquisa = r.dt_pesquisa
    left join {{ ref('fct_preco') }} as pc
        on u.id_loja = pc.id_loja and u.id_produto = pc.id_produto and u.dt_pesquisa = pc.dt_pesquisa
    left join {{ ref('fct_share_gondola') }} as s
        on u.id_loja = s.id_loja and u.id_produto = s.id_produto and u.dt_pesquisa = s.dt_pesquisa
    left join {{ ref('visitas_completas') }} as vc
        on u.id_loja = vc.id_loja and u.id_produto = vc.id_produto and u.dt_pesquisa = vc.dt_pesquisa

)

select
    count(*) as total_visitas,
    count_if(completa) as visitas_completas,
    count_if(not completa) as visitas_incompletas,
    round(100.0 * count_if(not completa) / count(*), 2) as pct_incompletas,
    count_if(not completa and not tem_presenca) as faltou_presenca,
    count_if(not completa and not tem_ruptura) as faltou_ruptura,
    count_if(not completa and not tem_preco) as faltou_preco,
    count_if(not completa and not tem_share) as faltou_share,
    count_if(ausente) as skus_ausentes
from flag
