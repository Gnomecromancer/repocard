"""
repocard CLI.

    repocard generate owner/repo [--output card.svg]
    repocard generate owner/repo --png --output card.png
"""
from __future__ import annotations
import sys
from pathlib import Path

import click

from . import __version__
from .api import fetch
from .render import render_svg


@click.group()
@click.version_option(__version__)
def main():
    """repocard — generate stat cards for GitHub repos."""


@main.command()
@click.argument("repo_slug", metavar="OWNER/REPO")
@click.option(
    "--output", "-o",
    type=click.Path(dir_okay=False, path_type=Path),
    default=None,
    help="Output path. Defaults to <repo>.svg (or .png with --png).",
)
@click.option(
    "--png",
    is_flag=True,
    help="Render to PNG via Pillow+cairosvg (requires cairosvg).",
)
def generate(repo_slug: str, output: Path | None, png: bool):
    """
    Generate a stat card for OWNER/REPO.

    \b
    Examples:
        repocard generate torvalds/linux
        repocard generate psf/requests --output requests_card.svg
        repocard generate Gnomecromancer/tapegif --png
    """
    if "/" not in repo_slug:
        click.echo("Error: OWNER/REPO must contain a slash (e.g. torvalds/linux)", err=True)
        sys.exit(1)

    owner, repo = repo_slug.split("/", 1)
    click.echo(f"fetching {repo_slug} …")

    try:
        data = fetch(owner, repo)
    except Exception as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(1)

    svg = render_svg(data)

    if png:
        try:
            import cairosvg
        except ImportError:
            click.echo(
                "cairosvg is required for PNG output: pip install cairosvg",
                err=True,
            )
            sys.exit(1)
        out = output or Path(f"{repo}.png")
        cairosvg.svg2png(bytestring=svg.encode(), write_to=str(out))
    else:
        out = output or Path(f"{repo}.svg")
        out.write_text(svg, encoding="utf-8")

    click.echo(f"saved {out}")
