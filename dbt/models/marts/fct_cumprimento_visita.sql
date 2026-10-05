-- Visit compliance per promoter, store and day. Uses source_date (always set)
-- as the date, not data_checkin (null when the visit is not OK).
-- atendimento: OK = visit done; NP = promoter tried but could not complete it
-- (store closed, nobody in charge, access denied); X = visit cancelled or not
-- attempted (route reorganized, store left the day's route).
select
    id_usuario,
    nome,
    id_loja,
    source_date as dt_visita,
    count(*) as total_visitas,
    count_if(atendimento = 'OK') as qtd_ok,
    count_if(atendimento = 'NP') as qtd_np,
    count_if(atendimento = 'X') as qtd_x,
    round(100.0 * count_if(atendimento = 'OK') / count(*), 2) as pct_ok
from {{ ref('stg_atendimentos') }}
group by id_usuario, nome, id_loja, source_date
