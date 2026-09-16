"""CLI de la capa de decision. Por ahora expone la recuperacion de censura.

Uso:
    python -m blindside.decision recover --method hourly_profile
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from blindside import config as cfg
from blindside.data import loaders
from blindside.data import schema as S
from blindside.decision.censoring import RECOVERIES, censoring_report, get_recovery

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)


def _recover(args: argparse.Namespace) -> int:
    panel = loaders.load_hourly_panel(prefer_sample=args.sample)
    recovery = get_recovery(args.method)
    out = recovery.recover(panel)
    out = out.drop(columns=[c for c in S.HOURLY_COLS if c in out.columns])
    out = S.validate_panel(out, required=S.DEMAND_REQUIRED, allow_gaps=True)

    target_dir = args.out or (cfg.DATA_SAMPLE if args.sample else cfg.DATA_PROCESSED)
    path = loaders.save_layer(out, "demand", out_dir=target_dir)

    report = censoring_report(out)
    print("\n=== Recuperacion de demanda censurada ===", file=sys.stderr)
    print(f"metodo: {recovery.name}", file=sys.stderr)
    print(report.to_string(index=False, float_format=lambda v: f"{v:,.4f}"), file=sys.stderr)
    print(f"\ncapa escrita en {path}", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s · %(message)s")
    parser = argparse.ArgumentParser(prog="blindside.decision", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("recover", help="recupera la demanda latente censurada")
    rec.add_argument("--method", default="hourly_profile", choices=sorted(RECOVERIES))
    rec.add_argument("--out", type=Path, default=None)
    rec.add_argument("--sample", action="store_true", help="operar sobre data/sample/")
    rec.set_defaults(func=_recover)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
