"""Lookups des référentiels.

Ce module fournit des fonctions de lecture pour enrichir les line_id bruts
(ex: 'STIF:Line::C01390:') avec les noms commerciaux et autres attributs.

Pattern d'usage typique (dashboard, coach RAG) :

    engine = create_database_engine(database_url)
    lookups = LineLookup.from_database(engine)
    short = lookups.short_name("STIF:Line::C01390:")  # -> "T2"
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple

from sqlalchemy import Engine, text


class LineInfo(NamedTuple):
    """Attributs d'une ligne IDFM utilisables pour l'enrichissement."""

    line_id: str
    short_name: str | None
    long_name: str | None
    transport_mode: str | None
    network_name: str | None
    operator_name: str | None
    color_web_hex: str | None
    text_color_hex: str | None


@dataclass(frozen=True)
class LineLookup:
    """Lookup en mémoire des lignes IDFM.

    On charge tout le référentiel (~2000 lignes, ~200 Ko) en RAM lors de
    l'instanciation. C'est rapide et ça évite N requêtes SQL au moment des
    affichages.
    """

    by_line_id: dict[str, LineInfo]

    @classmethod
    def from_database(cls, engine: Engine) -> LineLookup:
        """Charge le lookup depuis la table idfm_lines."""
        sql = text(
            """
            SELECT
                line_id, short_name, long_name,
                transport_mode, network_name, operator_name,
                color_web_hex, text_color_hex
            FROM idfm_lines
            """
        )
        with engine.connect() as conn:
            rows = conn.execute(sql).fetchall()

        by_line_id = {row.line_id: LineInfo(*row) for row in rows}
        return cls(by_line_id=by_line_id)

    def get(self, line_id: str) -> LineInfo | None:
        """Retourne LineInfo ou None si la ligne n'est pas connue."""
        return self.by_line_id.get(line_id)

    def short_name(self, line_id: str) -> str | None:
        """Raccourci : retourne le nom court ('T2', 'RER A', '258') ou None."""
        info = self.by_line_id.get(line_id)
        return info.short_name if info else None

    def display_name(self, line_id: str) -> str:
        """Retourne le meilleur nom disponible avec fallback intelligent.

        Ordre : short_name -> long_name -> code court extrait du line_id.
        """
        info = self.by_line_id.get(line_id)
        if info is not None:
            if info.short_name:
                return info.short_name
            if info.long_name:
                return info.long_name
        # Fallback : extraire le code court du line_id
        # 'STIF:Line::C01390:' -> 'C01390'
        parts = line_id.strip(":").split(":")
        return parts[-1] if parts else line_id

    def transport_mode(self, line_id: str) -> str | None:
        info = self.by_line_id.get(line_id)
        return info.transport_mode if info else None

    def color(self, line_id: str) -> str | None:
        """Couleur officielle de la ligne au format #RRGGBB."""
        info = self.by_line_id.get(line_id)
        return info.color_web_hex if info else None

    def __len__(self) -> int:
        return len(self.by_line_id)

    def __contains__(self, line_id: str) -> bool:
        return line_id in self.by_line_id
