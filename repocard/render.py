"""Generate an SVG stat card for a GitHub repo."""

from __future__ import annotations
import textwrap
from .api import RepoData
from .colors import lang_color

# ── palette (dark theme) ────────────────────────────────────────────────────

_BG         = "0d1117"
_BORDER     = "30363d"
_TITLE      = "e6edf3"
_TEXT       = "8b949e"
_ACCENT     = "58a6ff"
_BADGE_BG   = "21262d"

WIDTH = 420
PAD   = 20


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
         .replace('"', "&quot;")
    )


def _wrap(text: str, max_chars: int = 52) -> list[str]:
    if not text:
        return []
    return textwrap.wrap(text, width=max_chars) or [text[:max_chars]]


def _lang_bar(languages: dict[str, int], width: int, x: int, y: int) -> str:
    total = sum(languages.values())
    if not total:
        return ""
    parts = []
    cx = x
    bar_h = 8
    r = bar_h // 2
    remaining = width
    items = sorted(languages.items(), key=lambda kv: -kv[1])
    for i, (lang, byt) in enumerate(items):
        frac = byt / total
        w = max(1, round(frac * width))
        if i == len(items) - 1:
            w = remaining  # absorb rounding
        remaining -= w
        col = lang_color(lang)
        # Rounded caps only on first and last segment
        if len(items) == 1:
            rx = r
        elif i == 0:
            rx = f"{r} 0 0 {r}"
        elif i == len(items) - 1:
            rx = f"0 {r} {r} 0"
        else:
            rx = "0"
        parts.append(
            f'<rect x="{cx}" y="{y}" width="{w}" height="{bar_h}" '
            f'rx="{rx if isinstance(rx, int) else 0}" '
            f'fill="#{col}"/>'
        )
        # Rounded rect for first/last is done with clipPath trick; simpler to just skip for now
        cx += w

    # Redo with simple per-segment rects, rounded corners on leftmost/rightmost only
    parts = []
    cx = x
    remaining = width
    for i, (lang, byt) in enumerate(items):
        frac = byt / total
        w = max(1, round(frac * width))
        if i == len(items) - 1:
            w = remaining
        remaining -= w
        col = lang_color(lang)
        parts.append(
            f'<rect x="{cx}" y="{y}" width="{w}" height="{bar_h}" fill="#{col}"/>'
        )
        cx += w

    # Overlay rounded rect with the full bar border (cuts corners)
    bar_svg = "\n".join(parts)
    clip_id = "langbar"
    return (
        f'<defs><clipPath id="{clip_id}">'
        f'<rect x="{x}" y="{y}" width="{width}" height="{bar_h}" rx="{r}"/>'
        f'</clipPath></defs>'
        f'<g clip-path="url(#{clip_id})">{bar_svg}</g>'
    )


def _lang_legend(languages: dict[str, int], x: int, y: int, max_langs: int = 5) -> tuple[str, int]:
    total = sum(languages.values())
    if not total:
        return "", y
    items = sorted(languages.items(), key=lambda kv: -kv[1])[:max_langs]
    parts = []
    cx = x
    dot_r = 5
    for lang, byt in items:
        pct = f"{byt/total*100:.1f}%"
        col = lang_color(lang)
        label = _esc(f"{lang} {pct}")
        # Estimate text width: ~7px/char
        text_w = len(label) * 7
        entry_w = dot_r * 2 + 4 + text_w + 16
        if cx + entry_w > x + (WIDTH - 2 * PAD):
            # wrap to next row
            y += 22
            cx = x
        parts.append(
            f'<circle cx="{cx + dot_r}" cy="{y + dot_r}" r="{dot_r}" fill="#{col}"/>'
            f'<text x="{cx + dot_r * 2 + 6}" y="{y + dot_r + 4}" '
            f'font-size="12" fill="#{_TEXT}" font-family="monospace">{label}</text>'
        )
        cx += entry_w
    return "\n".join(parts), y + 20


def _stat_badge(icon: str, value: int | str, x: int, y: int) -> str:
    label = f"{icon} {value}"
    w = max(60, len(label) * 8 + 16)
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="24" rx="12" fill="#{_BADGE_BG}"/>'
        f'<text x="{x + w//2}" y="{y + 16}" text-anchor="middle" '
        f'font-size="12" fill="#{_TEXT}" font-family="monospace">{_esc(label)}</text>'
    )


def render_svg(repo: RepoData) -> str:
    lines: list[str] = []
    y = PAD

    # Title
    title = _esc(repo.full_name)
    lines.append(
        f'<text x="{PAD}" y="{y + 18}" font-size="17" font-weight="bold" '
        f'fill="#{_TITLE}" font-family="monospace">{title}</text>'
    )
    y += 32

    # Description
    desc_lines = _wrap(repo.description)
    for dl in desc_lines[:2]:
        lines.append(
            f'<text x="{PAD}" y="{y + 12}" font-size="13" fill="#{_TEXT}" '
            f'font-family="monospace">{_esc(dl)}</text>'
        )
        y += 18
    if desc_lines:
        y += 6

    # Divider
    lines.append(
        f'<line x1="{PAD}" y1="{y}" x2="{WIDTH - PAD}" y2="{y}" '
        f'stroke="#{_BORDER}" stroke-width="1"/>'
    )
    y += 14

    # Stat badges
    badge_x = PAD
    for icon, val in [("★", repo.stars), ("⑂", repo.forks), ("◉", repo.watchers), ("●", repo.open_issues)]:
        badge = _stat_badge(icon, val, badge_x, y)
        lines.append(badge)
        badge_x += 96

    y += 36

    # Language bar + legend
    if repo.languages:
        bar_w = WIDTH - 2 * PAD
        lines.append(_lang_bar(repo.languages, bar_w, PAD, y))
        y += 16
        legend_svg, y = _lang_legend(repo.languages, PAD, y)
        lines.append(legend_svg)
        y += 8

    # Topics
    if repo.topics:
        tx = PAD
        for topic in repo.topics[:8]:
            tw = len(topic) * 7 + 18
            if tx + tw > WIDTH - PAD:
                y += 24
                tx = PAD
            lines.append(
                f'<rect x="{tx}" y="{y}" width="{tw}" height="20" rx="10" fill="#{_BADGE_BG}"/>'
                f'<text x="{tx + tw//2}" y="{y + 14}" text-anchor="middle" '
                f'font-size="11" fill="#{_ACCENT}" font-family="monospace">{_esc(topic)}</text>'
            )
            tx += tw + 6
        y += 28

    # License + fork notice
    meta_parts = []
    if repo.license_name:
        meta_parts.append(f"⚖ {repo.license_name}")
    if repo.is_fork:
        meta_parts.append("⑂ fork")
    if meta_parts:
        lines.append(
            f'<text x="{PAD}" y="{y + 12}" font-size="11" fill="#{_TEXT}" '
            f'font-family="monospace">{_esc("  ·  ".join(meta_parts))}</text>'
        )
        y += 20

    height = y + PAD

    # Assemble
    svg_body = "\n".join(lines)
    return f"""\
<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{height}"
     viewBox="0 0 {WIDTH} {height}">
  <rect width="{WIDTH}" height="{height}" rx="6" fill="#{_BG}" stroke="#{_BORDER}" stroke-width="1"/>
  {svg_body}
</svg>"""
