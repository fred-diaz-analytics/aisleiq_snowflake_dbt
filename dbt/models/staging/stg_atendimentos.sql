with typed as (

    -- categoria_loja is left out: it can be recovered with id_loja + dim_loja.
    select
        id_pesquisa_resposta,
        id_usuario,
        nome,
        cargo,
        id_loja,
        atendimento,
        hora_checkin,
        hora_checkout,
        raio_ckin,
        distancia_ckin,
        distancia_ckout,
        tempo_loja,
        source_file,
        source_date,
        ingested_at,
        -- the pattern guard keeps try_to_date from accepting looser shapes than the original RLIKE did
        case
            when regexp_like(data_checkin, '[0-9]{2}/[0-9]{2}/[0-9]{4}') then try_to_date(data_checkin, 'DD/MM/YYYY')
        end as data_checkin,
        case
            when regexp_like(data_checkout, '[0-9]{2}/[0-9]{2}/[0-9]{4}') then try_to_date(data_checkout, 'DD/MM/YYYY')
        end as data_checkout
    from {{ source('raw', 'atendimentos') }}

),

composed as (

    select
        id_pesquisa_resposta,
        id_usuario,
        nome,
        cargo,
        id_loja,
        atendimento,
        data_checkin,
        hora_checkin,
        data_checkout,
        hora_checkout,
        raio_ckin,
        distancia_ckin,
        distancia_ckout,
        tempo_loja,
        source_file,
        source_date,
        ingested_at,
        try_to_timestamp(to_char(data_checkin) || ' ' || hora_checkin) as data_hora_checkin,
        try_to_timestamp(to_char(data_checkout) || ' ' || hora_checkout) as data_hora_checkout
    from typed

),

flagged as (

    -- geolocation check: only meaningful for OK visits (a real check-in exists)
    select
        id_pesquisa_resposta,
        id_usuario,
        nome,
        cargo,
        id_loja,
        atendimento,
        data_checkin,
        hora_checkin,
        data_checkout,
        hora_checkout,
        raio_ckin,
        distancia_ckin,
        distancia_ckout,
        tempo_loja,
        source_file,
        source_date,
        ingested_at,
        data_hora_checkin,
        data_hora_checkout,
        case when atendimento = 'OK' then distancia_ckin <= raio_ckin end as checkin_dentro_raio,
        case when atendimento = 'OK' then distancia_ckout <= raio_ckin end as checkout_dentro_raio
    from composed

),

ranked as (

    -- defensive dedupe by (store, promoter, source day, check-in), keeping the
    -- most recently ingested row, in case a file is ever reloaded.
    select
        id_pesquisa_resposta,
        id_usuario,
        nome,
        cargo,
        id_loja,
        atendimento,
        data_checkin,
        hora_checkin,
        data_checkout,
        hora_checkout,
        raio_ckin,
        distancia_ckin,
        distancia_ckout,
        tempo_loja,
        source_file,
        source_date,
        ingested_at,
        data_hora_checkin,
        data_hora_checkout,
        checkin_dentro_raio,
        checkout_dentro_raio,
        row_number() over (
            partition by id_loja, id_usuario, source_date, data_checkin, hora_checkin
            order by ingested_at desc, id_pesquisa_resposta desc
        ) as rn
    from flagged

)

select
    id_pesquisa_resposta,
    id_usuario,
    nome,
    cargo,
    id_loja,
    atendimento,
    data_checkin,
    hora_checkin,
    data_checkout,
    hora_checkout,
    data_hora_checkin,
    data_hora_checkout,
    raio_ckin,
    distancia_ckin,
    distancia_ckout,
    tempo_loja,
    checkin_dentro_raio,
    checkout_dentro_raio,
    source_file,
    source_date,
    ingested_at
from ranked
where rn = 1
