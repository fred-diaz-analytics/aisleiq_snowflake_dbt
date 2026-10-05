"""
Daily job: generates the synthetic files for every weekday missing since the
last generated one, up to today (catch-up). All generation logic lives in
lib_geracao.py; this is the entrypoint, the equivalent of a Databricks Job task.

It continues from the state written by backfill_2026.py (dclientes.csv,
estado_execucao.csv, estado_atendimento.csv in --out-dir), so run the
backfill first. Generation is deterministic per day, and the state is chained,
so the same backfill plus the same end date always gives the same files.

Usage:
  python generator/job_diario.py                         # catch-up to today
  python generator/job_diario.py --ate 2026-09-30        # catch-up to a fixed date
  python generator/job_diario.py --dominio execucao --data 2026-08-12   # one day only

The next id_pesquisa_resposta is detected from the existing parquet files.
"""
import argparse
import glob
import os
from datetime import date, datetime, timedelta, timezone

import pandas as pd
from lib_geracao import (
    build_baselines_marca,
    build_df_perguntas,
    build_df_produtos,
    gerar_atendimento_dia_stateful,
    gerar_bronze_dia_stateful,
)

DEFAULT_OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


def ultima_data_gerada(dias_dir: str):
    """Date of the newest parquet in dias_dir, or None if there is none yet."""
    arquivos = glob.glob(os.path.join(dias_dir, "*.parquet"))
    if not arquivos:
        return None
    nome = max(os.path.basename(f)[:8] for f in arquivos)
    return date(int(nome[0:4]), int(nome[4:6]), int(nome[6:8]))


def dias_uteis_faltantes(ultima, ate: date) -> list:
    """Weekdays (Mon-Fri) after `ultima` up to `ate`, `ultima` excluded,
    `ate` included. With no history (`ultima=None`) it
    returns only [ate]. There are no visits on weekends, as in lojas_do_dia."""
    if ultima is None:
        return [ate]
    datas = []
    d = ultima + timedelta(days=1)
    while d <= ate:
        if d.weekday() < 5:
            datas.append(d)
        d += timedelta(days=1)
    return datas


def proximo_id_livre(dias_dir: str) -> int:
    """Next free id_pesquisa_resposta, from the parquet files already there."""
    arquivos = glob.glob(os.path.join(dias_dir, "*.parquet"))
    if not arquivos:
        return 1
    maior = max(pd.read_parquet(f, columns=["id_pesquisa_resposta"])["id_pesquisa_resposta"].max() for f in arquivos)
    return int(maior) + 1


def rodar_execucao(dim_lojas: pd.DataFrame, data_ref: date, out_dir: str) -> None:
    estado_path = os.path.join(out_dir, "estado_execucao.csv")
    dias_dir = os.path.join(out_dir, "execucao_pdv")
    estado = pd.read_csv(estado_path)
    df_produtos = build_df_produtos()
    df_perguntas = build_df_perguntas()
    baselines_marca = build_baselines_marca(df_produtos["marca"].unique().tolist())

    df_dia, estado_novo = gerar_bronze_dia_stateful(
        dim_lojas, df_produtos, df_perguntas, data_ref, estado, baselines_marca, id_inicial=proximo_id_livre(dias_dir)
    )

    os.makedirs(dias_dir, exist_ok=True)
    path = os.path.join(dias_dir, f"{data_ref.strftime('%Y%m%d')}_execucao_pdv_bronze_synth.parquet")
    df_dia.to_parquet(path, index=False)
    estado_novo.to_csv(estado_path, index=False, encoding="utf-8-sig")
    print(f"[execucao]    {data_ref}: {len(df_dia)} rows -> {path}", flush=True)


def rodar_atendimento(dim_lojas: pd.DataFrame, data_ref: date, out_dir: str) -> None:
    estado_path = os.path.join(out_dir, "estado_atendimento.csv")
    dias_dir = os.path.join(out_dir, "atendimento")
    estado = pd.read_csv(estado_path)

    df_dia, estado_novo = gerar_atendimento_dia_stateful(dim_lojas, data_ref, estado, id_inicial=proximo_id_livre(dias_dir))

    os.makedirs(dias_dir, exist_ok=True)
    path = os.path.join(dias_dir, f"{data_ref.strftime('%Y%m%d')}_atendimento_synth.parquet")
    df_dia.to_parquet(path, index=False)
    estado_novo.to_csv(estado_path, index=False, encoding="utf-8-sig")
    print(f"[atendimento] {data_ref}: {len(df_dia)} visits -> {path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dominio", choices=["execucao", "atendimento", "todos"], default="todos")
    parser.add_argument("--data", default=None, help="YYYY-MM-DD: generate only this day")
    parser.add_argument("--ate", default=None, help="YYYY-MM-DD: catch-up end date (default: today)")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="directory with dclientes.csv and estado_*.csv; daily files go to <out-dir>/execucao_pdv and <out-dir>/atendimento")
    args = parser.parse_args()

    dim_lojas = pd.read_csv(os.path.join(args.out_dir, "dclientes.csv"))
    ate = date.fromisoformat(args.ate) if args.ate else datetime.now(tz=timezone.utc).date()

    dominios = [
        ("execucao", rodar_execucao, ("execucao", "todos")),
        ("atendimento", rodar_atendimento, ("atendimento", "todos")),
    ]
    for nome, rodar, aceitos in dominios:
        if args.dominio not in aceitos:
            continue
        dias_dir = os.path.join(args.out_dir, "execucao_pdv" if nome == "execucao" else "atendimento")
        datas = [date.fromisoformat(args.data)] if args.data else dias_uteis_faltantes(ultima_data_gerada(dias_dir), ate)
        if args.data is None and len(datas) > 1:
            print(f"[{nome}] catch-up: {len(datas)} day(s) missing ({datas[0]} to {datas[-1]})", flush=True)
        for data_ref in datas:
            rodar(dim_lojas, data_ref, args.out_dir)


if __name__ == "__main__":
    main()
