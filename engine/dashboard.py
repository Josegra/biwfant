"""
Markdown history report, generated from the SQLite store and committed
to the repo so it's browsable directly on GitHub (no external hosting
needed) — renders standings and model accuracy over time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from data import store

REPORT_PATH = Path(__file__).resolve().parent.parent / "data" / "report.md"


def generate_markdown_report() -> str:
    accuracy = store.get_model_accuracy(last_n_jornadas=10)
    standings = store.get_standings()

    lines = [
        "# Biwfant — Historial\n",
        f"_Actualizado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_\n",
        "## Precisión del modelo\n",
    ]
    if accuracy["mae"] is not None:
        lines.append(f"- Error medio absoluto (MAE): **{accuracy['mae']} pts** ({accuracy['n_samples']} muestras)")
        lines.append(f"- Acierto de dirección: **{accuracy['direction_accuracy']:.0%}**\n")
    else:
        lines.append("- Datos insuficientes todavía (necesita más jornadas).\n")

    lines.append("## Clasificación\n")
    if standings:
        lines.append("| Pos | Equipo | Puntos | Valor plantilla |")
        lines.append("|---|---|---|---|")
        for u in standings:
            lines.append(
                f"| {u['position']} | {u['user_name']} | {u['points']} | "
                f"€{u['team_value']/1e6:.1f}M |"
            )
    else:
        lines.append("_Sin datos de clasificación todavía._")

    text = "\n".join(lines) + "\n"
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(text, encoding="utf-8")
    return text
