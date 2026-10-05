{{ config(enabled=(target.name != 'prod')) }}

-- Acceptance test of the migration: do the MARTS KPIs recover the effects the generator
-- planted (poor replenishment chains, a price war chain, an excellence chain, 35 critical
-- stores, decay by visit cadence)? Ported from validar_verdade_plantada.py of the original.
-- The answer key is the seed verdade_plantada, one row per store.
-- Returns one row per failed criterion; no rows means every criterion passed.

with params as (

    select
        12 * 7 as janela_dias,
        4 as min_visitas

),

dia as (

    -- daily score per store: the average of its categories, over the last N weeks
    select
        s.id_loja,
        s.dt_pesquisa,
        avg(s.score_execucao_pdv) as score,
        avg(s.avg_nota_preco) as nota_preco
    from {{ ref('scores_execucao_pdv') }} as s
    cross join params as p
    where s.dt_pesquisa > (select dateadd(day, -p.janela_dias, max(dt_pesquisa)) from {{ ref('scores_execucao_pdv') }})
    group by s.id_loja, s.dt_pesquisa

),

base as (

    select
        d.id_loja,
        count(*) as visitas,
        avg(d.score) as score,
        avg(d.nota_preco) as nota_preco,
        g.id_usuario,
        g.periodicidade_visita,
        g.critica,
        g.rede_guerra_preco,
        g.severidade_esperada,
        g.critica or g.rede_ruptura or g.rede_guerra_preco or g.rede_excelencia as tem_efeito
    from dia as d
    inner join {{ ref('verdade_plantada') }} as g on d.id_loja = g.id_loja
    group by
        d.id_loja, g.id_usuario, g.periodicidade_visita, g.critica, g.rede_guerra_preco,
        g.severidade_esperada, g.rede_ruptura, g.rede_excelencia

),

ranking as (

    -- stores with too few visits are noise (a sporadic store with one visit)
    select
        b.id_loja,
        b.score,
        b.critica,
        b.severidade_esperada,
        b.periodicidade_visita,
        b.id_usuario,
        b.tem_efeito
    from base as b
    cross join params as p
    where b.visitas >= p.min_visitas

),

-- 1. the score orders the stores like the planted severity (the more severe, the lower the score).
-- Spearman = Pearson over the ranks; ties take the average rank, as in pandas.
ranks as (

    select
        id_loja,
        rank() over (order by score) + (count(*) over (partition by score) - 1) / 2.0 as rank_score,
        rank() over (order by severidade_esperada desc)
        + (count(*) over (partition by severidade_esperada) - 1) / 2.0 as rank_neg_severidade
    from ranking

),

c1 as (

    select
        'spearman(score, -severidade) >= 0.6' as criterio,
        corr(rank_score, rank_neg_severidade) >= 0.6 as ok,
        'rho = ' || round(corr(rank_score, rank_neg_severidade), 3) as detalhe
    from ranks

),

-- 2. critical stores sit in the bottom quintile of the score
c2 as (

    select
        'critical stores in the bottom quintile >= 70%' as criterio,
        coalesce(
            count_if(r.score <= q.corte_q1) / nullif(count(*), 0) >= 0.7, false
        ) as ok,
        round(100 * count_if(r.score <= q.corte_q1) / nullif(count(*), 0)) || '% of ' || count(*) || ' critical stores' as detalhe
    from ranking as r
    cross join (select percentile_cont(0.2) within group (order by score) as corte_q1 from ranking) as q
    where r.critica

),

-- 3. the price war shows up in the price score
c3 as (

    select
        'price score: price war chain >= 30 points lower' as criterio,
        avg(case when not rede_guerra_preco then nota_preco end) - avg(case when rede_guerra_preco then nota_preco end) >= 30 as ok,
        'guerra=' || round(avg(case when rede_guerra_preco then nota_preco end), 1)
        || ' | demais=' || round(avg(case when not rede_guerra_preco then nota_preco end), 1) as detalhe
    from base

),

-- 4. decay by cadence: observed stockout grows with the interval between visits,
-- over stores with no planted store or chain effect
ruptura_loja as (

    select
        g.periodicidade_visita,
        r.id_loja,
        avg(r.pct_ruptura) as pct_ruptura
    from {{ ref('fct_ruptura') }} as r
    inner join {{ ref('verdade_plantada') }} as g on r.id_loja = g.id_loja
    where not (g.critica or g.rede_ruptura or g.rede_guerra_preco or g.rede_excelencia)
    group by g.periodicidade_visita, r.id_loja

),

ruptura_cadencia as (

    select
        avg(case when periodicidade_visita = 'MENSAL' then pct_ruptura end) as mensal,
        avg(case when periodicidade_visita = 'SEMANAL' then pct_ruptura end) as semanal,
        avg(case when periodicidade_visita = 'NUCLEO' then pct_ruptura end) as nucleo
    from ruptura_loja

),

c4 as (

    select
        'stockout: MENSAL > SEMANAL > NUCLEO' as criterio,
        coalesce(mensal > semanal and semanal > nucleo, false) as ok,
        'MENSAL=' || round(mensal, 2) || ' | SEMANAL=' || round(semanal, 2) || ' | NUCLEO=' || round(nucleo, 2) as detalhe
    from ruptura_cadencia

),

-- 5. an absent product weighs on the score (it used to vanish in the completeness gate)
c5 as (

    select
        'absent SKUs enter the score' as criterio,
        skus_ausentes > 0 as ok,
        skus_ausentes || ' absent SKU visits' as detalhe
    from {{ ref('qualidade_completude_visita') }}

),

-- 6. negative control: the promoter has no planted effect. Permutation test over the stores
-- with no store or chain effect: the variance between promoter means must not be larger than
-- chance produces. The cadence effect (planted) is removed first.
neutras as (

    select
        id_loja,
        id_usuario,
        score - avg(score) over (partition by periodicidade_visita) as residuo
    from ranking
    where not tem_efeito

),

observado as (

    select variance(media) as variancia
    from (select avg(residuo) as media from neutras group by id_usuario)

),

permutacoes as (

    -- a deterministic permutation per k: pair the i-th store (hash order 1) with the
    -- promoter of the i-th store in an independent hash order 2
    select
        k.k,
        n.residuo,
        row_number() over (partition by k.k order by hash(n.id_loja, k.k, 1)) as pos_residuo,
        row_number() over (partition by k.k order by hash(n.id_loja, k.k, 2)) as pos_usuario,
        n.id_usuario
    from neutras as n
    cross join (
        select row_number() over (order by seq4()) as k
        from table(generator(rowcount => 1000))
    ) as k

),

permutado as (

    select
        k,
        variance(media) as variancia
    from (
        select
            x.k,
            u.id_usuario,
            avg(x.residuo) as media
        from permutacoes as x
        inner join permutacoes as u on x.k = u.k and x.pos_residuo = u.pos_usuario
        group by x.k, u.id_usuario
    )
    group by k

),

c6 as (

    select
        'promoter without effect (p >= 0.05)' as criterio,
        avg(case when p.variancia >= o.variancia then 1.0 else 0.0 end) >= 0.05 as ok,
        'p = ' || round(avg(case when p.variancia >= o.variancia then 1.0 else 0.0 end), 3) as detalhe
    from permutado as p
    cross join observado as o

),

criterios as (

    select criterio, ok, detalhe from c1
    union all
    select criterio, ok, detalhe from c2
    union all
    select criterio, ok, detalhe from c3
    union all
    select criterio, ok, detalhe from c4
    union all
    select criterio, ok, detalhe from c5
    union all
    select criterio, ok, detalhe from c6

)

select
    criterio,
    ok,
    detalhe
from criterios
where not coalesce(ok, false)
