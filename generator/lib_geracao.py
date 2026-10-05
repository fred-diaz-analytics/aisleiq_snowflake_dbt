"""
Shared synthetic generation library for the "PDV execution" and "atendimento"
domains.

Centerpiece: the store dimension (`dim_lojas`, a.k.a. dclientes) is generated
ONCE and persisted, never recreated per day. What changes day by day is only
WHICH stores are visited (by visit cadence) and the chaotic answers of the
promoter.

All text here is ASCII; accented domain values are written as \\u escapes so the
generated data stays byte-identical to the original project.
"""
import math
import os
import random
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

fake = Faker("pt_BR")

UF_PARA_REGIAO = {
    "AC": "Norte", "AP": "Norte", "AM": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste",
    "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MT": "Centro-Oeste", "MS": "Centro-Oeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
}

MARCAS_POR_CATEGORIA = {
    "Higiene Pessoal": ["Suave", "PureCare", "Bellara"],
    "Limpeza Dom\u00e9stica": ["Brilhare", "CleanMax"],
    "Alimentos": ["Sabor Caseiro", "Gr\u00e3os & Cia"],
    "Snacks": ["CrocanteX", "Delicce"],
}
TAMANHOS = ["P", "M", "G"]

PERGUNTAS = [
    {"indicador": "PRESENCA", "grupo_pesquisa": "PRESENCA", "desc_pergunta": "PRODUTO PRESENTE ?", "tipo_resposta": "sim_nao", "opcional": False},
    {"indicador": "RUPTURA", "grupo_pesquisa": "RUPTURA", "desc_pergunta": "PRODUTO ESTA EM RUPTURA ?", "tipo_resposta": "sim_nao", "opcional": False},
    {"indicador": "PRECO", "grupo_pesquisa": "PRECO", "desc_pergunta": "INFORME O PRE\u00c7O DO PRODUTO", "tipo_resposta": "preco", "opcional": False},
    {"indicador": "MPDV", "grupo_pesquisa": "MPDV", "desc_pergunta": "POSSUI MATERIAL ATIVADO ?", "tipo_resposta": "sim_nao", "opcional": True},
    {"indicador": "PONTO_EXTRA", "grupo_pesquisa": "PONTO_EXTRA", "desc_pergunta": "INFORME O TOTAL DE PONTO EXTRA", "tipo_resposta": "contagem", "opcional": True},
    {"indicador": "SHARE_GONDOLA", "grupo_pesquisa": "SHARE_GONDOLA", "desc_pergunta": "SHARE PROPRIO NA GONDOLA", "tipo_resposta": "percentual", "opcional": False},
]

REDES = [
    "Rede Bom Pre\u00e7o", "Mercado Cia", "Atacad\u00e3o Sul", "Comper Norte", "VarejoMax",
    "Super Economia", "Rede Popular", "Mercadinho Vit\u00f3ria", "Center Compras", "Rede Nordeste Mix",
    "Bazar Central", "Mercado Vale Verde", "Rede Confian\u00e7a", "Atacado Bom Jesus", "Compre Bem Express",
]

# ---------------------------------------------------------------------------
# Config of the stateful evolution process (simplified Ornstein-Uhlenbeck):
# new_value = value + theta*(baseline - value) + noise ; then clip(min, max)
# small theta = "long memory" (changes slowly), sigma = daily wobble.
#
# All 9 brands of the catalog belong to the same group (no external
# competition is surveyed), so each metric has a single group baseline, with a
# deterministic per-brand deviation (_offset_marca) giving each brand its own
# personality.
# ---------------------------------------------------------------------------
THETA = 0.05
VARIACAO_MARCA_PCT = 0.15  # deviation of up to +-15% from the group baseline, per brand (price only)
METRICAS_ESTADO = {
    # metric: (group_baseline, sigma, minimum, maximum) -- the group baseline is
    # only used by preco_medio today; the others come from TIERS_METRICA (below).
    # sigma/minimum/maximum still drive the day-to-day evolution (_passo_ou).
    "prob_mpdv": (0.55, 0.02, 0.0, 0.95),
    "taxa_ruptura": (0.10, 0.02, 0.0, 0.80),
    # sigma is in R$, not %. 0.06 (was 0.20): with THETA=0.05 the stationary
    # deviation of the OU process is sigma/sqrt(1-(1-THETA)^2) ~= 3.2x sigma.
    # 0.20 gave ~R$0.64 (~9% of the price), pushing "normal" stores out of the
    # -3%/+5% band around the suggested price all the time; 0.06 gives ~3%,
    # leaving the planted price war (REDES_GUERRA_PRECO) as the real signal.
    "preco_medio": (6.8, 0.06, 2.0, 18.0),
    "media_ponto_extra": (1.4, 0.12, 0.0, 6.0),
    "media_share_gondola": (0.34, 0.015, 0.02, 0.65),
}
BUMP_RUPTURA_PERSISTENTE = 0.03  # if it was out of stock yesterday, push today's rate up
# Stockout has its own theta (reverts faster than the global THETA of 0.05).
# With the old fixed bump (0.12) plus the global THETA, slow reversion created a
# feedback loop (stockout -> bump -> higher chance of another stockout -> bump)
# that pushed the observed rate far above the per-tier target (e.g. leader
# target 3-8%, observed ~30%). Found by simulation, validated against the
# generated data.
THETA_RUPTURA = 0.12

# Presence is structural (distribution/listing) and should not change at every
# visit. Unlike the other metrics it does not use _passo_ou (continuous
# evolution); it is a persisted binary state (presenca_atual) that rarely
# flips, like a real listing does.
PROB_DELISTAR = 0.02  # chance of losing the listing per visit (rare, structural event)

# "Flagship product": every category has a brand-strength ranking
# (leader / middle / small), consistent across the metrics with an obvious
# business direction (the leader has more presence, fewer stockouts, more
# MPDV / extra display / share). Price is left out: it has no obvious business
# direction (premium vs. competitive), so it keeps only _offset_marca.
TIERS_METRICA = {
    # metric: {tier: (minimum, maximum)}
    "prob_presenca": {"lider": (0.90, 0.97), "meio": (0.80, 0.90), "pequena": (0.65, 0.80)},
    "taxa_ruptura": {"lider": (0.03, 0.08), "meio": (0.08, 0.15), "pequena": (0.15, 0.25)},
    "prob_mpdv": {"lider": (0.55, 0.75), "meio": (0.35, 0.55), "pequena": (0.15, 0.35)},
    "media_ponto_extra": {"lider": (2.0, 3.5), "meio": (1.0, 2.0), "pequena": (0.3, 1.0)},
    "media_share_gondola": {"lider": (0.30, 0.50), "meio": (0.10, 0.25), "pequena": (0.03, 0.09)},
}


def _offset_marca(marca: str, metrica: str, baseline: float, minimo: float, maximo: float) -> float:
    """Deterministic, reproducible per-brand deviation around the group
    baseline. Used only for price today (no obvious business direction to turn
    it into a leader/middle/small tier)."""
    seed = f"{marca}:{metrica}"
    rnd = random.Random(seed)
    fator = 1 + rnd.uniform(-VARIACAO_MARCA_PCT, VARIACAO_MARCA_PCT)
    return float(np.clip(baseline * fator, minimo, maximo))


def ranking_por_categoria() -> dict:
    """Strength order of each brand within its category (leader -> smallest),
    deterministic and reproducible. It is the "flagship product", consistent
    across all metrics, not a leader drawn per metric."""
    return {
        categoria: random.Random(f"rank:{categoria}").sample(marcas, len(marcas))
        for categoria, marcas in MARCAS_POR_CATEGORIA.items()
    }


def _tier_da_posicao(posicao: int, n_marcas: int) -> str:
    if posicao == 0:
        return "lider"
    if posicao == n_marcas - 1:
        return "pequena"
    return "meio"


def _valor_tier(marca: str, metrica: str, tier: str) -> float:
    """Deterministic, reproducible draw inside the target range of the brand's
    tier for this metric. Same reproducibility principle as _offset_marca, but
    drawing inside the tier range."""
    minimo, maximo = TIERS_METRICA[metrica][tier]
    rnd = random.Random(f"{marca}:{metrica}:tier")
    return rnd.uniform(minimo, maximo)


def build_baselines_marca(marcas: list) -> dict:
    """Precompute, once, the effective baseline of each metric for each brand of
    the catalog. Presence/stockout/mpdv/extra display/share come from the
    category's leader/middle/small ranking; price comes from _offset_marca."""
    tier_da_marca = tier_por_marca()

    baselines = {}
    for marca in marcas:
        tier = tier_da_marca[marca]
        valores = {metrica: _valor_tier(marca, metrica, tier) for metrica in TIERS_METRICA}

        cfg_preco = METRICAS_ESTADO["preco_medio"]
        valores["preco_medio"] = _offset_marca(marca, "preco_medio", cfg_preco[0], cfg_preco[2], cfg_preco[3])

        baselines[marca] = valores
    return baselines


def _prob_relistar(prob_alvo: float, prob_delistar: float = PROB_DELISTAR) -> float:
    """Probability of GAINING a listing, calibrated so the stationary state of
    the (delist/relist) Markov chain converges to the desired prob_alvo."""
    return prob_delistar * prob_alvo / (1 - prob_alvo)


def tier_por_marca() -> dict:
    """brand -> leader/middle/small, from the category ranking."""
    return {
        marca: _tier_da_posicao(ordem.index(marca), len(ordem))
        for ordem in ranking_por_categoria().values()
        for marca in ordem
    }


# ---------------------------------------------------------------------------
# Commercial targets (`metas` domain: suggested price, SKU priority, share
# target). Same source of truth the generator uses to anchor the observed
# price, so target and data cannot diverge. Exported as master data (full
# reload on demand).
# ---------------------------------------------------------------------------
CATEGORIAS_LOJA = ["VAREJO", "ATACADO", "ATACAREJO"]
FATOR_PRECO_CANAL = {"VAREJO": 1.00, "ATACAREJO": 0.93, "ATACADO": 0.88}
BANDA_PRECO_PCT = (-3.0, 5.0)  # tolerance band around the suggested price
VIGENCIA_METAS = date(2026, 1, 1)
GIRO_SEMANAL_TIER = {"lider": 24.0, "meio": 12.0, "pequena": 5.0}  # units/week, retail, size M
FATOR_GIRO_TAMANHO = {"P": 1.2, "M": 1.0, "G": 0.7}
FATOR_GIRO_CANAL = {"VAREJO": 1.0, "ATACAREJO": 2.5, "ATACADO": 3.0}
# ~midpoint of the TIERS_METRICA["media_share_gondola"] range: a brand
# performing at its own baseline lands near a score of 100.
META_SHARE_TIER_PCT = {"lider": 40.0, "meio": 18.0, "pequena": 6.0}


def _preco_de_gondola(valor: float) -> float:
    """Round to the R$ x.x9 price-tag pattern (between -1 and +9 cents of the value)."""
    return round(math.floor(valor * 10) / 10 + 0.09, 2)


def build_df_preco_sugerido() -> pd.DataFrame:
    """Suggested price (RRP) per SKU x channel: brand price baseline x channel factor."""
    df_produtos = build_df_produtos()
    baselines = build_baselines_marca(df_produtos["marca"].unique().tolist())
    linhas = []
    for _, p in df_produtos.iterrows():
        for canal in CATEGORIAS_LOJA:
            linhas.append({
                "id_produto": int(p["id_produto"]),
                "categoria_loja": canal,
                "preco_sugerido": _preco_de_gondola(baselines[p["marca"]]["preco_medio"] * FATOR_PRECO_CANAL[canal]),
                "banda_min_pct": BANDA_PRECO_PCT[0],
                "banda_max_pct": BANDA_PRECO_PCT[1],
                "vigencia_inicio": VIGENCIA_METAS.isoformat(),
            })
    return pd.DataFrame(linhas)


def mapa_preco_sugerido() -> dict:
    """(id_produto, categoria_loja) -> preco_sugerido."""
    df = build_df_preco_sugerido()
    return {(int(r.id_produto), r.categoria_loja): float(r.preco_sugerido) for r in df.itertuples()}


def build_df_sku_prioridade() -> pd.DataFrame:
    """Expected weekly turnover and must-have flag per SKU x channel.
    must_have = every SKU of the leader brand + size M of the middle brand."""
    df_produtos = build_df_produtos()
    tiers = tier_por_marca()
    linhas = []
    for _, p in df_produtos.iterrows():
        tier = tiers[p["marca"]]
        must_have = tier == "lider" or (tier == "meio" and p["tamanho"] == "M")
        for canal in CATEGORIAS_LOJA:
            giro = GIRO_SEMANAL_TIER[tier] * FATOR_GIRO_TAMANHO[p["tamanho"]] * FATOR_GIRO_CANAL[canal]
            linhas.append({
                "id_produto": int(p["id_produto"]),
                "categoria_loja": canal,
                "giro_semanal_un": round(giro, 1),
                "must_have": must_have,
            })
    return pd.DataFrame(linhas)


def build_df_meta_share() -> pd.DataFrame:
    """Shelf-share target per brand x channel, by the brand's tier in the category."""
    df_produtos = build_df_produtos()
    tiers = tier_por_marca()
    marcas = df_produtos[["id_marca", "marca"]].drop_duplicates().sort_values("id_marca")
    linhas = [
        {"id_marca": int(m.id_marca), "categoria_loja": canal, "meta_share_pct": META_SHARE_TIER_PCT[tiers[m.marca]]}
        for m in marcas.itertuples()
        for canal in CATEGORIAS_LOJA
    ]
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Planted effects: the "truth" the analytical framework has to rediscover.
# Without them the only variation in the data is per brand (TIERS_METRICA) and
# differences between stores are pure noise. Everything is deterministic and
# derived from columns dclientes already has (id_loja, rede), so the daily job
# keeps working without new state. The promoter has NO effect on purpose
# (negative control: the framework must not find a difference).
# ---------------------------------------------------------------------------
REDES_RUPTURA = ["Super Economia", "Rede Popular", "Mercadinho Vit\u00f3ria"]  # poor replenishment
REDES_GUERRA_PRECO = ["Atacad\u00e3o Sul", "Atacado Bom Jesus"]  # price below the band
REDE_EXCELENCIA = "Rede Confian\u00e7a"
FATOR_RUPTURA_REDE_RUIM = 1.8
FATOR_PRECO_GUERRA = 0.85
FATOR_RUPTURA_EXCELENCIA = 0.5
DELTA_PRESENCA_EXCELENCIA = 0.05
N_LOJAS_CRITICAS = 35
FATOR_PRESENCA_CRITICA = 0.75
FATOR_DELISTAR_CRITICA = 4.0  # without it the stationary state of _prob_relistar does not drop
FATOR_RUPTURA_CRITICA = 1.5
# Decay by cadence: the longer since the last visit, the higher the chance of a
# stockout on the visit day (the promoter is who restocks / pulls orders).
K_DECAY_RUPTURA = 0.10
DIAS_DECAY_MAX = 30
DIAS_SEM_HISTORICO = 7
DIAS_TIPICOS_CADENCIA = {"NUCLEO": 1, "SEMANAL": 7, "QUINZENAL": 14, "MENSAL": 28, "ESPORADICA": 7}


def lojas_criticas(ids) -> set:
    ids = sorted(int(i) for i in ids)
    return set(random.Random("lojas_criticas").sample(ids, min(N_LOJAS_CRITICAS, len(ids))))


def efeitos_loja(dim_lojas: pd.DataFrame) -> dict:
    """id_loja -> planted multipliers (chain + critical store)."""
    criticas = lojas_criticas(dim_lojas["id_loja"])
    efeitos = {}
    for _, loja in dim_lojas.iterrows():
        id_loja = int(loja["id_loja"])
        rede = loja["rede"]
        e = {
            "critica": id_loja in criticas,
            "rede_ruptura": rede in REDES_RUPTURA,
            "rede_guerra_preco": rede in REDES_GUERRA_PRECO,
            "rede_excelencia": rede == REDE_EXCELENCIA,
            "fator_ruptura": 1.0,
            "fator_presenca": 1.0,
            "delta_presenca": 0.0,
            "fator_delistar": 1.0,
            "fator_preco": 1.0,
        }
        if e["rede_ruptura"]:
            e["fator_ruptura"] *= FATOR_RUPTURA_REDE_RUIM
        if e["rede_excelencia"]:
            e["fator_ruptura"] *= FATOR_RUPTURA_EXCELENCIA
            e["delta_presenca"] += DELTA_PRESENCA_EXCELENCIA
        if e["rede_guerra_preco"]:
            e["fator_preco"] = FATOR_PRECO_GUERRA
        if e["critica"]:
            e["fator_ruptura"] *= FATOR_RUPTURA_CRITICA
            e["fator_presenca"] = FATOR_PRESENCA_CRITICA
            e["fator_delistar"] = FATOR_DELISTAR_CRITICA
        efeitos[id_loja] = e
    return efeitos


def fator_decay_ruptura(dias_desde_ultima_visita: int) -> float:
    """Increase in the day's stockout probability, linear up to DIAS_DECAY_MAX."""
    dias = min(max(dias_desde_ultima_visita, 0), DIAS_DECAY_MAX)
    return K_DECAY_RUPTURA * dias / DIAS_DECAY_MAX


def _dias_desde(ultima, data_ref: date) -> int:
    """`ultima` comes from the state (iso string; empty/NaN when the store was never visited)."""
    if isinstance(ultima, str) and ultima:
        return (data_ref - date.fromisoformat(ultima)).days
    return DIAS_SEM_HISTORICO


def baseline_loja_produto(base_marca: dict, efeito: dict, preco_sugerido: float) -> dict:
    """Effective baseline of a (store, product): the brand baseline with the
    store's planted effects applied; price anchored on the suggested price."""
    cfg_ruptura = METRICAS_ESTADO["taxa_ruptura"]
    return {
        "prob_presenca": float(np.clip(base_marca["prob_presenca"] * efeito["fator_presenca"] + efeito["delta_presenca"], 0.05, 0.99)),
        "prob_delistar": PROB_DELISTAR * efeito["fator_delistar"],
        "taxa_ruptura": float(np.clip(base_marca["taxa_ruptura"] * efeito["fator_ruptura"], cfg_ruptura[2], cfg_ruptura[3])),
        "prob_mpdv": base_marca["prob_mpdv"],
        "media_ponto_extra": base_marca["media_ponto_extra"],
        "media_share_gondola": base_marca["media_share_gondola"],
        "preco_medio": preco_sugerido * efeito["fator_preco"],
    }


def nota_preco(desvio_pct: float, banda_min_pct: float = BANDA_PRECO_PCT[0], banda_max_pct: float = BANDA_PRECO_PCT[1]) -> float:
    """Python mirror of the price score curve (0-100)."""
    d, bmin, bmax = desvio_pct, banda_min_pct / 100, banda_max_pct / 100
    if d <= -0.18:
        nota = 0.01
    elif d < bmin:
        nota = 1 - ((abs(d) - abs(bmin)) / (0.18 - abs(bmin))) ** 2
    elif d <= bmax:
        nota = 1.0
    else:
        nota = 1 - 10 * (d - bmax) ** 2
    return max(0.01, nota) * 100


def build_verdade_plantada(dim_lojas: pd.DataFrame) -> pd.DataFrame:
    """Answer key per store: which effects were planted and how many score
    points are expected to be lost because of them (severidade_esperada).
    Never loaded into the warehouse; only used to check that the score
    rediscovers what was planted."""
    baselines = build_baselines_marca(build_df_produtos()["marca"].unique().tolist())
    ruptura_media = float(np.mean([b["taxa_ruptura"] for b in baselines.values()]))
    presenca_media = float(np.mean([b["prob_presenca"] for b in baselines.values()]))

    efeitos = efeitos_loja(dim_lojas)
    linhas = []
    for _, loja in dim_lojas.iterrows():
        e = efeitos[int(loja["id_loja"])]
        dias = DIAS_TIPICOS_CADENCIA.get(loja["periodicidade_visita"], DIAS_SEM_HISTORICO)
        ruptura_extra = ruptura_media * (e["fator_ruptura"] - 1) + fator_decay_ruptura(dias)
        presenca_perdida = presenca_media - float(np.clip(presenca_media * e["fator_presenca"] + e["delta_presenca"], 0.05, 0.99))
        penalidade_preco = (100 - nota_preco(e["fator_preco"] - 1)) / 100
        linhas.append({
            "id_loja": int(loja["id_loja"]),
            "rede": loja["rede"],
            "categoria_loja": loja["categoria_loja"],
            "periodicidade_visita": loja["periodicidade_visita"],
            "id_usuario": int(loja["id_usuario"]),
            **{k: e[k] for k in ["critica", "rede_ruptura", "rede_guerra_preco", "rede_excelencia",
                                 "fator_ruptura", "fator_presenca", "fator_delistar", "fator_preco"]},
            "dias_tipicos_entre_visitas": dias,
            "severidade_esperada": round(100 * (0.55 * (ruptura_extra + presenca_perdida) + 0.20 * penalidade_preco), 2),
        })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# "atendimento" domain (visit routine / time in store): same dclientes, same
# cadence (lojas_do_dia), own state per store (not per product).
# ---------------------------------------------------------------------------
# Baselines calibrated with the median (more robust to GPS / forgotten
# check-out outliers) of a historical sample.
BASELINE_TEMPO_LOJA = {"VAREJO": 67.0, "ATACADO": 119.0, "ATACAREJO": 104.0}   # minutes
BASELINE_DISTANCIA = {"VAREJO": 86.0, "ATACADO": 254.0, "ATACAREJO": 178.0}    # meters
RAIO_TOLERANCIA_CKIN = 500  # fixed app rule, does not vary per store
PROB_OK_BASELINE = 0.691           # real: OK 69.1% / NP 13.4% / X 17.5%
SPLIT_NP_DENTRO_NAO_OK = 0.434     # real NP / (NP+X)


def build_estado_inicial_atendimento(dim_lojas: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for _, loja in dim_lojas.iterrows():
        cat = loja["categoria_loja"]
        linhas.append({
            "id_loja": loja["id_loja"],
            "tempo_medio": BASELINE_TEMPO_LOJA[cat],
            "distancia_media": BASELINE_DISTANCIA[cat],
            "prob_ok": PROB_OK_BASELINE,
            "data_ultima_atualizacao": "",
        })
    return pd.DataFrame(linhas)


def gerar_atendimento_dia_stateful(dim_lojas: pd.DataFrame, data_ref: date, estado: pd.DataFrame, id_inicial: int = 1):
    """One row per visit (not per question). Reuses the SAME cadence of
    lojas_do_dia used by PDV execution: it is the same promoter route."""
    seed_dia = int(data_ref.strftime("%Y%m%d")) + 1  # different seed from PDV execution, same date
    rnd = random.Random(seed_dia)
    np_rng = np.random.default_rng(seed_dia)

    estado_dict = estado.set_index("id_loja").to_dict("index")
    lojas_hoje = lojas_do_dia(dim_lojas, data_ref)
    linhas = []
    id_visita = id_inicial

    for _, loja in lojas_hoje.iterrows():
        cat = loja["categoria_loja"]
        e = estado_dict[loja["id_loja"]]

        novo_prob_ok = _passo_ou(e["prob_ok"], PROB_OK_BASELINE, 0.02, 0.40, 0.95, np_rng)
        status = rnd.choices(
            ["OK", "NP", "X"],
            weights=[novo_prob_ok, (1 - novo_prob_ok) * SPLIT_NP_DENTRO_NAO_OK, (1 - novo_prob_ok) * (1 - SPLIT_NP_DENTRO_NAO_OK)],
        )[0]

        if status == "OK":
            novo_tempo = _passo_ou(e["tempo_medio"], BASELINE_TEMPO_LOJA[cat], 4.0, 8.0, 150.0, np_rng)
            novo_dist = _passo_ou(e["distancia_media"], BASELINE_DISTANCIA[cat], 15.0, 0.0, 400.0, np_rng)

            hora_checkin = datetime.combine(data_ref, datetime.min.time()) + timedelta(
                hours=int(np_rng.integers(8, 17)), minutes=int(np_rng.integers(0, 60))
            )
            tempo_real = max(5.0, novo_tempo + np_rng.normal(0, 3))  # fine capture noise
            hora_checkout = hora_checkin + timedelta(minutes=tempo_real)
            distancia_ckin = max(0.0, novo_dist + np_rng.normal(0, 10))
            distancia_ckout = max(0.0, novo_dist + np_rng.normal(0, 10))

            linha = {
                "id_pesquisa_resposta": id_visita, "id_usuario": loja["id_usuario"], "nome": loja["nome"], "cargo": loja["cargo"],
                "id_loja": loja["id_loja"], "categoria_loja": cat, "atendimento": "OK",
                "data_checkin": hora_checkin.strftime("%d/%m/%Y"), "hora_checkin": hora_checkin.strftime("%H:%M:%S"),
                "data_checkout": hora_checkout.strftime("%d/%m/%Y"), "hora_checkout": hora_checkout.strftime("%H:%M:%S"),
                "raio_ckin": RAIO_TOLERANCIA_CKIN,
                "distancia_ckin": round(distancia_ckin, 1), "distancia_ckout": round(distancia_ckout, 1),
                "tempo_loja": round(tempo_real, 1),
            }
            e["tempo_medio"] = novo_tempo
            e["distancia_media"] = novo_dist
        else:
            linha = {
                "id_pesquisa_resposta": id_visita, "id_usuario": loja["id_usuario"], "nome": loja["nome"], "cargo": loja["cargo"],
                "id_loja": loja["id_loja"], "categoria_loja": cat, "atendimento": status,
                "data_checkin": None, "hora_checkin": None, "data_checkout": None, "hora_checkout": None,
                "raio_ckin": None, "distancia_ckin": None, "distancia_ckout": None, "tempo_loja": None,
            }

        e["prob_ok"] = novo_prob_ok
        e["data_ultima_atualizacao"] = data_ref.isoformat()
        linhas.append(linha)
        id_visita += 1

    estado_final = pd.DataFrame([{"id_loja": k, **v} for k, v in estado_dict.items()])
    return pd.DataFrame(linhas), estado_final


CIDADES_REAIS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cidades_reais.csv")


def build_df_produtos() -> pd.DataFrame:
    """`id_marca`/`id_categoria` follow the same pattern as a real system's
    `id_loja`/`id_rede`/etc: a key of their own, with several products sharing
    the same brand/category id, not just a loose string."""
    categoria_para_id = {categoria: i + 1 for i, categoria in enumerate(MARCAS_POR_CATEGORIA)}
    marca_para_id = {
        marca: i + 1
        for i, marca in enumerate(m for marcas in MARCAS_POR_CATEGORIA.values() for m in marcas)
    }

    produtos, pid = [], 1
    for categoria, marcas in MARCAS_POR_CATEGORIA.items():
        for marca in marcas:
            for tamanho in TAMANHOS:
                produtos.append({
                    "id_produto": pid,
                    "produto": f"{marca} {tamanho}",
                    "tamanho": tamanho,
                    "id_marca": marca_para_id[marca],
                    "marca": marca,
                    "id_categoria": categoria_para_id[categoria],
                    "categoria_produto": categoria,
                })
                pid += 1
    return pd.DataFrame(produtos)


def build_df_perguntas() -> pd.DataFrame:
    return pd.DataFrame(PERGUNTAS)


def build_dim_promotores(n: int = 20, seed: int = 7) -> pd.DataFrame:
    fake.seed_instance(seed)
    return pd.DataFrame([
        {"id_usuario": i + 1, "nome": fake.name(), "cargo": "PROMOTOR DE MERCHANDISING"}
        for i in range(n)
    ])


EPOCA_ESPORADICA = date(2026, 1, 1)  # the project is 100% year 2026 (backfill_2026.py)


def build_dim_lojas(n_lojas: int = 500, seed: int = 7) -> pd.DataFrame:
    """Customer dimension (dclientes): generated once, then only read/persisted.
    Each store gets a fixed visit cadence, which explains why not every store is
    surveyed every day (like a real survey panel).

    Cadence has a long tail (real finding: median of 5 surveys in ~227 business
    days, but 24% of stores with a single survey and a small, almost daily
    core). NUCLEO and ESPORADICA cover those two ends, which
    SEMANAL/QUINZENAL/MENSAL alone do not replicate."""
    rnd = random.Random(seed)
    fake.seed_instance(seed)

    df_cidades = pd.read_csv(CIDADES_REAIS_PATH)
    cidades = df_cidades.sample(n=n_lojas, replace=True, random_state=seed).reset_index(drop=True)

    linhas = []
    for i, row in cidades.iterrows():
        periodicidade = rnd.choices(
            ["NUCLEO", "SEMANAL", "QUINZENAL", "MENSAL", "ESPORADICA"],
            weights=[0.05, 0.25, 0.20, 0.20, 0.30],
        )[0]
        linhas.append({
            "id_loja": i + 1,
            "nome_fantasia": fake.company(),
            "rede": rnd.choice(REDES),
            "endereco": fake.street_address(),
            "regiao": UF_PARA_REGIAO[row["uf"]],
            "uf": row["uf"],
            "cidade": row["cidade"],
            "categoria_loja": rnd.choices(["VAREJO", "ATACADO", "ATACAREJO"], weights=[0.6, 0.25, 0.15])[0],
            "periodicidade_visita": periodicidade,
            "dia_semana_visita": rnd.randint(0, 4),          # 0=mon ... 4=fri
            "semana_par_visita": rnd.choice([True, False]),   # only used if QUINZENAL
            "semana_do_mes_visita": rnd.randint(1, 4),        # only used if MENSAL
            # only used if ESPORADICA: a short, single activity window starting
            # at a random point of the year; outside it the store is never due.
            "esporadica_offset_dias": rnd.randint(0, 300),
            "esporadica_duracao_semanas": rnd.randint(1, 3),
        })
    dim_lojas = pd.DataFrame(linhas)

    dim_promotores = build_dim_promotores(seed=seed)
    rnd2 = random.Random(seed + 1)
    dim_lojas["id_usuario"] = [rnd2.choice(dim_promotores["id_usuario"].tolist()) for _ in range(len(dim_lojas))]
    dim_lojas = dim_lojas.merge(dim_promotores, on="id_usuario", how="left")
    return dim_lojas


def lojas_do_dia(dim_lojas: pd.DataFrame, data_ref: date) -> pd.DataFrame:
    """Applies the visit cadence plus an imperfect route coverage (~90%),
    deterministically per date (reproducible in the backfill)."""
    weekday = data_ref.weekday()
    if weekday > 4:  # no visits on weekends
        return dim_lojas.iloc[0:0]

    iso_week = data_ref.isocalendar()[1]
    week_of_month = (data_ref.day - 1) // 7 + 1

    due = dim_lojas[dim_lojas["dia_semana_visita"] == weekday]
    semanal = due[due["periodicidade_visita"] == "SEMANAL"]
    quinzenal = due[
        (due["periodicidade_visita"] == "QUINZENAL")
        & (((iso_week % 2) == 0) == due["semana_par_visita"])
    ]
    mensal = due[
        (due["periodicidade_visita"] == "MENSAL")
        & (due["semana_do_mes_visita"] == week_of_month)
    ]
    # ESPORADICA: same weekday check as SEMANAL, but only inside a short,
    # single window (1-3 weeks); outside it the store is never due. Real long
    # tail: 24% of stores with a single survey in the period.
    dias_desde_epoca = (data_ref - EPOCA_ESPORADICA).days
    esporadica = due[
        (due["periodicidade_visita"] == "ESPORADICA")
        & (dias_desde_epoca >= due["esporadica_offset_dias"])
        & (dias_desde_epoca < due["esporadica_offset_dias"] + due["esporadica_duracao_semanas"] * 7)
    ]
    # NUCLEO: due every business day (ignores dia_semana_visita), an almost
    # daily core (~185/227 business days for the most visited stores).
    nucleo = dim_lojas[dim_lojas["periodicidade_visita"] == "NUCLEO"]
    candidatas = pd.concat([nucleo, semanal, quinzenal, mensal, esporadica])
    if candidatas.empty:
        return candidatas

    rng = np.random.default_rng(int(data_ref.strftime("%Y%m%d")))
    mask = rng.random(len(candidatas)) < 0.90  # the route does not always cover 100%
    return candidatas[mask]


def _formatar_preco_caotico(v: float, rnd: random.Random) -> str:
    formatos = [
        lambda x: f"{x:.2f}".replace(".", ","),
        lambda x: f"{x:.2f}",
        lambda x: f"R$ {x:.2f}".replace(".", ","),
        lambda x: f"{x:.0f}",
    ]
    return rnd.choice(formatos)(v)


def build_estado_inicial(dim_lojas: pd.DataFrame, df_produtos: pd.DataFrame, baselines_marca: dict) -> pd.DataFrame:
    """State (store, product) -> the "current" value of each metric. Generated
    once; from then on it is only read and updated incrementally by the daily
    job. It is born with the store's planted effects (efeitos_loja) applied."""
    efeitos = efeitos_loja(dim_lojas)
    precos = mapa_preco_sugerido()
    linhas = []
    for _, loja in dim_lojas.iterrows():
        for _, produto in df_produtos.iterrows():
            base = baseline_loja_produto(
                baselines_marca[produto["marca"]],
                efeitos[int(loja["id_loja"])],
                precos[(int(produto["id_produto"]), loja["categoria_loja"])],
            )
            linha = {"id_loja": loja["id_loja"], "id_produto": produto["id_produto"], "ruptura_ontem": False, "presenca_atual": True, "data_ultima_atualizacao": ""}
            for metrica in METRICAS_ESTADO:
                linha[metrica] = base[metrica]
            linhas.append(linha)
    return pd.DataFrame(linhas)


def _passo_ou(valor: float, baseline: float, sigma: float, minimo: float, maximo: float, rng: np.random.Generator, theta: float = THETA) -> float:
    novo = valor + theta * (baseline - valor) + rng.normal(0, sigma)
    return float(np.clip(novo, minimo, maximo))


def gerar_bronze_dia_stateful(dim_lojas: pd.DataFrame, df_produtos: pd.DataFrame, df_perguntas: pd.DataFrame,
                               data_ref: date, estado: pd.DataFrame, baselines_marca: dict, id_inicial: int = 1):
    """Generates one day of PDV execution answers. The day's "central" value
    comes from the state (which carries the memory of previous days) instead of
    an i.i.d. draw. Returns (df_dia, updated_state)."""
    seed_dia = int(data_ref.strftime("%Y%m%d"))
    rnd = random.Random(seed_dia)
    np_rng = np.random.default_rng(seed_dia)

    estado_dict = estado.set_index(["id_loja", "id_produto"]).to_dict("index")
    produtos_marca = df_produtos.set_index("id_produto")["marca"].to_dict()
    efeitos = efeitos_loja(dim_lojas)
    precos = mapa_preco_sugerido()

    lojas_hoje = lojas_do_dia(dim_lojas, data_ref)
    linhas = []
    id_resposta = id_inicial

    for _, loja in lojas_hoje.iterrows():
        efeito = efeitos[int(loja["id_loja"])]
        checkin_valido = rnd.random() < 0.85
        hora_visita = datetime.combine(data_ref, datetime.min.time()) + timedelta(
            hours=int(np_rng.integers(8, 18)), minutes=int(np_rng.integers(0, 60))
        )
        # The whole catalog belongs to the same group (full portfolio audit,
        # not a competition benchmark): every SKU is assessed at every visit,
        # with no sampling.
        produtos_loja = df_produtos

        for _, produto in produtos_loja.iterrows():
            chave = (loja["id_loja"], produto["id_produto"])
            base = baseline_loja_produto(
                baselines_marca[produtos_marca[produto["id_produto"]]],
                efeito,
                precos[(int(produto["id_produto"]), loja["categoria_loja"])],
            )
            e = estado_dict[chave]
            decay_ruptura = fator_decay_ruptura(_dias_desde(e["data_ultima_atualizacao"], data_ref))

            # evolve each metric one step from the previous state (no draw from scratch)
            prob_presenca_alvo = base["prob_presenca"]
            prob_relistar = _prob_relistar(prob_presenca_alvo, base["prob_delistar"])
            novo_prob_mpdv = _passo_ou(e["prob_mpdv"], base["prob_mpdv"], *METRICAS_ESTADO["prob_mpdv"][1:], np_rng)
            taxa_ruptura_base = base["taxa_ruptura"]
            bump = BUMP_RUPTURA_PERSISTENTE if e["ruptura_ontem"] else 0.0
            novo_taxa_ruptura = _passo_ou(e["taxa_ruptura"] + bump, taxa_ruptura_base, *METRICAS_ESTADO["taxa_ruptura"][1:], np_rng, theta=THETA_RUPTURA)
            novo_preco = _passo_ou(e["preco_medio"], base["preco_medio"], *METRICAS_ESTADO["preco_medio"][1:], np_rng)
            novo_ponto_extra = _passo_ou(e["media_ponto_extra"], base["media_ponto_extra"], *METRICAS_ESTADO["media_ponto_extra"][1:], np_rng)
            novo_share = _passo_ou(e["media_share_gondola"], base["media_share_gondola"], *METRICAS_ESTADO["media_share_gondola"][1:], np_rng)

            presenca_hoje = e["presenca_atual"]  # carries yesterday's state by default; rarely changes
            produto_presente = None  # None = presence question not answered yet in this visit
            ruptura_hoje = False
            for _, pergunta in df_perguntas.iterrows():
                prob_pular = 0.15 if pergunta["opcional"] else 0.0
                if not checkin_valido:
                    prob_pular += 0.10
                if rnd.random() < prob_pular:
                    continue

                grupo = pergunta["grupo_pesquisa"]
                if grupo == "PRESENCA":
                    # rare state transition (delist/relist), not a draw from
                    # scratch: presence is structural and should not change
                    # at every visit
                    if presenca_hoje:
                        if rnd.random() < base["prob_delistar"]:
                            presenca_hoje = False
                    else:
                        if rnd.random() < prob_relistar:
                            presenca_hoje = True
                    produto_presente = presenca_hoje
                    resposta = "SIM" if presenca_hoje else "N\u00c3O"
                elif not produto_presente:
                    # Presence is the entry gate: an absent product (or one
                    # whose presence was not answered in this visit) makes no
                    # sense to assess for stockout/price/share/extra
                    # display/MPDV, since the store does not sell it (or we do
                    # not know whether it does).
                    continue
                elif grupo == "RUPTURA":
                    # decay enters only the day's chance, not the state: it is
                    # the effect of the interval since the last visit, not of
                    # the store
                    ruptura_hoje = rnd.random() < min(1.0, novo_taxa_ruptura + decay_ruptura)
                    resposta = "SIM" if ruptura_hoje else "N\u00c3O"
                elif grupo == "PRECO":
                    valor = novo_preco * (1 + np_rng.normal(0, 0.01))  # fine capture noise
                    if rnd.random() < 0.03:
                        valor *= 10  # fat-finger
                    resposta = _formatar_preco_caotico(valor, rnd)
                elif grupo == "MPDV":
                    resposta = "SIM" if rnd.random() < novo_prob_mpdv else "N\u00c3O"
                elif grupo == "PONTO_EXTRA":
                    qtd = np_rng.poisson(novo_ponto_extra)
                    if rnd.random() < 0.02:
                        qtd = -1
                    resposta = str(qtd)
                elif grupo == "SHARE_GONDOLA":
                    pct = novo_share * 100
                    if rnd.random() < 0.02:
                        pct = 500
                    resposta = f"{pct:.2f} %"
                else:
                    resposta = ""

                linha = {
                    "id_pesquisa_resposta": id_resposta,
                    "id_usuario": loja["id_usuario"], "nome": loja["nome"], "cargo": loja["cargo"],
                    "id_loja": loja["id_loja"], "id_produto": produto["id_produto"],
                    "produto": produto["produto"], "marca": produto["marca"], "categoria_produto": produto["categoria_produto"],
                    "indicador": pergunta["indicador"], "grupo_pesquisa": grupo, "desc_pergunta": pergunta["desc_pergunta"],
                    "resposta": resposta, "checkin_valido": checkin_valido,
                    "dt_pesquisa": hora_visita.strftime("%d/%m/%Y"),
                    "dt_gravacao": (hora_visita + timedelta(minutes=int(np_rng.integers(0, 31)))).strftime("%d/%m/%Y %H:%M:%S"),
                }
                linhas.append(linha)
                id_resposta += 1
                if rnd.random() < 0.03:
                    dup = linha.copy()
                    dup["id_pesquisa_resposta"] = id_resposta
                    dup["dt_gravacao"] = (hora_visita + timedelta(minutes=int(np_rng.integers(31, 91)))).strftime("%d/%m/%Y %H:%M:%S")
                    linhas.append(dup)
                    id_resposta += 1

            # persist the new state of this store+product for tomorrow (dict, not .loc)
            e["presenca_atual"] = presenca_hoje
            e["prob_mpdv"] = novo_prob_mpdv
            e["taxa_ruptura"] = novo_taxa_ruptura
            e["preco_medio"] = novo_preco
            e["media_ponto_extra"] = novo_ponto_extra
            e["media_share_gondola"] = novo_share
            e["ruptura_ontem"] = ruptura_hoje
            e["data_ultima_atualizacao"] = data_ref.isoformat()

    estado_final = pd.DataFrame(
        [{"id_loja": k[0], "id_produto": k[1], **v} for k, v in estado_dict.items()]
    )
    return pd.DataFrame(linhas), estado_final
