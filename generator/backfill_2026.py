"""
Backfill of the synthetic daily files (2026-01-01 to 2026-08-10, a fixed
window, not "until today", so the numbers stay reproducible). All generation
logic lives in lib_geracao.py; this is a thin entrypoint.

Generation is deterministic (seeds tied to the date, fixed seed=7 for stores
and promoters), so running this script on any machine reproduces exactly the
same data.

Usage:
  python generator/backfill_2026.py --dominio todos
  python generator/backfill_2026.py --dominio atendimento --out-dir generator/output
"""
import argparse
import os
from datetime import date, timedelta

import pandas as pd
from lib_geracao import (
    build_baselines_marca,
    build_df_perguntas,
    build_df_produtos,
    build_dim_lojas,
    build_estado_inicial,
    build_estado_inicial_atendimento,
    gerar_atendimento_dia_stateful,
    gerar_bronze_dia_stateful,
)

DATA_INICIO = date(2026, 1, 1)
DATA_FIM = date(2026, 8, 10)
DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def limpar_pasta(pasta: str) -> None:
    os.makedirs(pasta, exist_ok=True)
    for f in os.listdir(pasta):
        os.remove(os.path.join(pasta, f))


def backfill_execucao(dim_lojas: pd.DataFrame, out_dir: str) -> None:
    dias_dir = os.path.join(out_dir, "execucao_pdv")
    limpar_pasta(dias_dir)

    df_produtos = build_df_produtos()
    df_perguntas = build_df_perguntas()
    baselines_marca = build_baselines_marca(df_produtos["marca"].unique().tolist())
    estado = build_estado_inicial(dim_lojas, df_produtos, baselines_marca)

    total_dias = (DATA_FIM - DATA_INICIO).days + 1
    com_dado, proximo_id, d, i = 0, 1, DATA_INICIO, 0
    while d <= DATA_FIM:
        i += 1
        df_dia, estado = gerar_bronze_dia_stateful(dim_lojas, df_produtos, df_perguntas, d, estado, baselines_marca, id_inicial=proximo_id)
        if len(df_dia) > 0:
            df_dia.to_parquet(os.path.join(dias_dir, f"{d.strftime('%Y%m%d')}_execucao_pdv_bronze_synth.parquet"), index=False)
            proximo_id = int(df_dia["id_pesquisa_resposta"].max()) + 1
            com_dado += 1
            print(f"[execucao]    ({i}/{total_dias}) {d.isoformat()}: {len(df_dia)} rows", flush=True)
        else:
            print(f"[execucao]    ({i}/{total_dias}) {d.isoformat()}: no visits", flush=True)
        d += timedelta(days=1)

    print(f"[execucao]    done: {com_dado} days with data | next free id: {proximo_id} | files in {dias_dir}")


def backfill_atendimento(dim_lojas: pd.DataFrame, out_dir: str) -> None:
    dias_dir = os.path.join(out_dir, "atendimento")
    limpar_pasta(dias_dir)

    estado = build_estado_inicial_atendimento(dim_lojas)

    total_dias = (DATA_FIM - DATA_INICIO).days + 1
    com_dado, proximo_id, d, i = 0, 1, DATA_INICIO, 0
    while d <= DATA_FIM:
        i += 1
        df_dia, estado = gerar_atendimento_dia_stateful(dim_lojas, d, estado, id_inicial=proximo_id)
        if len(df_dia) > 0:
            df_dia.to_parquet(os.path.join(dias_dir, f"{d.strftime('%Y%m%d')}_atendimento_synth.parquet"), index=False)
            proximo_id = int(df_dia["id_pesquisa_resposta"].max()) + 1
            com_dado += 1
            print(f"[atendimento] ({i}/{total_dias}) {d.isoformat()}: {len(df_dia)} visits", flush=True)
        else:
            print(f"[atendimento] ({i}/{total_dias}) {d.isoformat()}: no visits", flush=True)
        d += timedelta(days=1)

    print(f"[atendimento] done: {com_dado} days with data | next free id: {proximo_id} | files in {dias_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dominio", choices=["execucao", "atendimento", "todos"], default="todos")
    parser.add_argument("--n-lojas", type=int, default=500)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="output directory; daily files go to <out-dir>/execucao_pdv and <out-dir>/atendimento")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"Generating the store dimension ({args.n_lojas} stores)...", flush=True)
    dim_lojas = build_dim_lojas(n_lojas=args.n_lojas, seed=7)  # generated once, serves both domains

    if args.dominio in ("execucao", "todos"):
        print(f"=== PDV execution backfill: {DATA_INICIO.isoformat()} to {DATA_FIM.isoformat()} ===", flush=True)
        backfill_execucao(dim_lojas, args.out_dir)
    if args.dominio in ("atendimento", "todos"):
        print(f"\n=== Atendimento backfill: {DATA_INICIO.isoformat()} to {DATA_FIM.isoformat()} ===", flush=True)
        backfill_atendimento(dim_lojas, args.out_dir)
