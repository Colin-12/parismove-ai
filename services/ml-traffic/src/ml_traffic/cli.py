"""Point d'entrée CLI du service ml-traffic.

Usage :
    python -m ml_traffic.cli train     # Entraîne et sauvegarde le modèle
    python -m ml_traffic.cli evaluate  # Évalue le modèle sauvegardé
"""
from __future__ import annotations

import argparse
import sys


def main() -> int:
    """Entrée CLI principale."""
    parser = argparse.ArgumentParser(prog="ml_traffic")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("train", help="Entraîne et sauvegarde le modèle")
    sub.add_parser("evaluate", help="Évalue le modèle sur le test set")

    args = parser.parse_args()

    if args.command in {"train", "evaluate"}:
        raise NotImplementedError(
            f"Commande '{args.command}' à implémenter dans feat/ml-traffic-baseline"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
