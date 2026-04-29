"""CLI du coach mobilité.

Usage:
    coach ask "Comment est l'air à Paris ?"
    coach ask "Compare le RER A et le métro 1 pour aller à La Défense"
    coach chat                          # mode interactif

Le mode chat permet une conversation continue avec une UX agréable
(historique des messages, signaux visuels, sortie propre).
"""
from __future__ import annotations

import logging
import sys

import click
from shared.db import create_database_engine

from coach.config import get_settings
from coach.llm import LLMClient
from coach.orchestrator import Coach, CoachResponse


def _bootstrap() -> Coach:
    """Initialise tous les composants nécessaires au coach."""
    settings = get_settings()
    if not settings.groq_api_key:
        click.echo(
            "❌ GROQ_API_KEY manquante dans .env. "
            "Inscris-toi sur https://console.groq.com/keys.",
            err=True,
        )
        sys.exit(1)
    if not settings.database_url:
        click.echo("❌ DATABASE_URL manquante dans .env.", err=True)
        sys.exit(1)

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    engine = create_database_engine(settings.database_url)
    llm = LLMClient(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    )
    return Coach(engine=engine, llm=llm, small_model=settings.groq_model_small)


def _display_response(response: CoachResponse, *, verbose: bool = False) -> None:
    """Affichage user-friendly d'une réponse."""
    click.echo()
    click.echo(response.answer)
    click.echo()

    if verbose:
        click.secho(
            f"  [intent: {response.intent.value} | langue: {response.language} | "
            f"data temps-réel: {'oui' if response.has_real_data else 'non'}"
            f"{' | tools: ' + ', '.join(response.tools_used) if response.tools_used else ''}]",
            fg="bright_black",
        )
        click.echo()


@click.group()
def main() -> None:
    """ParisMove Coach — assistant mobilité conversationnel."""


@main.command()
@click.argument("question", nargs=-1, required=True)
@click.option(
    "--verbose", "-v", is_flag=True,
    help="Affiche le diagnostic interne (intent détecté, tools appelés)",
)
def ask(question: tuple[str, ...], verbose: bool) -> None:
    """Pose une question unique au coach et reçois une réponse."""
    full_question = " ".join(question)
    coach = _bootstrap()
    try:
        with click.progressbar(
            length=1,
            label="🤔 Réflexion en cours",
            show_eta=False,
            show_percent=False,
        ) as bar:
            response = coach.ask(full_question)
            bar.update(1)
    except Exception as exc:
        click.echo(f"\n❌ Erreur : {exc}", err=True)
        sys.exit(1)
    _display_response(response, verbose=verbose)


@main.command()
@click.option(
    "--verbose", "-v", is_flag=True,
    help="Affiche le diagnostic interne",
)
def chat(verbose: bool) -> None:
    """Démarre une conversation interactive avec le coach."""
    coach = _bootstrap()

    click.clear()
    _print_banner()

    while True:
        try:
            question = click.prompt(
                click.style("\nToi", fg="cyan", bold=True),
                prompt_suffix=" > ",
                default="",
                show_default=False,
            ).strip()
        except (KeyboardInterrupt, EOFError):
            click.echo("\n\nÀ bientôt ! 👋\n")
            break

        if not question:
            continue

        # Commandes spéciales
        if question.lower() in ("exit", "quit", "bye", "/exit", "/quit"):
            click.echo("\nÀ bientôt ! 👋\n")
            break
        if question.lower() in ("help", "/help", "aide"):
            click.echo(_help_text())
            continue
        if question.lower() in ("clear", "/clear"):
            click.clear()
            _print_banner()
            continue

        click.secho("\nCoach", fg="green", bold=True, nl=False)
        click.echo(" >", nl=True)

        try:
            with click.progressbar(
                length=1,
                label="  🤔",
                show_eta=False,
                show_percent=False,
                show_pos=False,
            ) as bar:
                response = coach.ask(question)
                bar.update(1)
        except Exception as exc:
            click.echo(f"\n  ❌ Erreur : {exc}", err=True)
            continue

        _display_response(response, verbose=verbose)


def _print_banner() -> None:
    click.secho("=" * 64, fg="green")
    click.secho("  ParisMove AI Coach", fg="green", bold=True)
    click.secho("  Assistant mobilité Île-de-France", fg="green")
    click.secho("=" * 64, fg="green")
    click.echo()
    click.echo("  Pose-moi des questions sur la qualité de l'air, la météo,")
    click.echo("  le trafic, ou demande-moi de comparer des trajets.")
    click.echo()
    click.secho(
        "  Commandes spéciales : 'help', 'clear', 'exit'",
        fg="bright_black",
    )


def _help_text() -> str:
    return """
Capacités :
  • Qualité de l'air     "Comment est l'air à La Défense ?"
  • Météo                "Quel temps il fait à Paris ?"
  • Trafic               "Retard moyen sur le RER A ?"
  • Score santé trajet   "Score du trajet Châtelet → La Défense"
  • Comparaison          "Compare le RER A et le métro 1"

Le coach répond en français OU en anglais selon ta question.

Commandes :
  help      Affiche cette aide
  clear     Efface l'écran
  exit      Quitter (ou Ctrl+C, Ctrl+D)
"""


if __name__ == "__main__":
    main()
