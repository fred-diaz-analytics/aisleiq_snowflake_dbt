"""
Exports the planted-truth answer key (`build_verdade_plantada()` in
lib_geracao.py): per store, which effects the generator planted (poor
replenishment chain, price war chain, excellence chain, critical store,
visit cadence) and the expected severity in score points.

The key is not business data. It is the answer sheet that the dbt singular
test `verdade_plantada` uses to check that the KPIs recover what was planted.
It lives as the seed `dbt/seeds/verdade_plantada.csv`, built only outside prod.

Usage:
  python generator/export_verdade_plantada.py
  python generator/export_verdade_plantada.py --n-lojas 500 --out dbt/seeds/verdade_plantada.csv
"""
import argparse

from lib_geracao import build_dim_lojas, build_verdade_plantada


def export(n_lojas: int, out_path: str) -> None:
    # same store dimension (and seed) as backfill_2026.py, so the key matches the loaded data
    dim_lojas = build_dim_lojas(n_lojas=n_lojas, seed=7)
    df = build_verdade_plantada(dim_lojas)
    df.to_csv(out_path, index=False)
    print(f"{out_path}: {len(df)} stores | critical={int(df['critica'].sum())}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-lojas", type=int, default=500)
    parser.add_argument("--out", default="dbt/seeds/verdade_plantada.csv", help="output CSV path")
    args = parser.parse_args()
    export(args.n_lojas, args.out)
