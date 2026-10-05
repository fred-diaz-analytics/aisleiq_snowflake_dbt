-- Time spent in store (average and total, in minutes) per promoter, store and
-- day. Only OK visits have tempo_loja filled.
select
    id_usuario,
    nome,
    id_loja,
    source_date as dt_visita,
    count(*) as qtd_visitas_ok,
    round(avg(tempo_loja), 2) as tempo_loja_medio,
    round(sum(tempo_loja), 2) as tempo_loja_total
from {{ ref('stg_atendimentos') }}
where atendimento = 'OK' and tempo_loja is not null
group by id_usuario, nome, id_loja, source_date
