"""Lineup selection and message formatting."""

from __future__ import annotations

from collections import Counter

from loguru import logger

from api.models import Player
from engine.optimizer import optimize_lineup
from engine.scorer import score_player

_POS_NAME = {1: "porteros", 2: "defensas", 3: "centrocampistas", 4: "delanteros"}
# Minimum needed in each position across all 7 valid formations
_MIN_REQUIRED = {1: 1, 2: 3, 3: 3, 4: 1}


def get_missing_position_ids(available: list[Player]) -> list[int]:
    """Position ids (1=GK..4=FWD) short of the minimum needed by any formation."""
    counts = Counter(p.position for p in available)
    return [pos for pos in _MIN_REQUIRED if counts.get(pos, 0) < _MIN_REQUIRED[pos]]


def _missing_positions_reason(available: list[Player]) -> str:
    counts = Counter(p.position for p in available)
    missing = [
        f"{_MIN_REQUIRED[pos] - counts.get(pos, 0)} {_POS_NAME[pos]}"
        for pos in _MIN_REQUIRED
        if counts.get(pos, 0) < _MIN_REQUIRED[pos]
    ]
    if missing:
        return f"Te faltan al menos: {', '.join(missing)} disponibles."
    return "No hay ninguna combinación de formación válida con la plantilla disponible."


def get_best_lineup(
    players: list[Player],
    current_formation: str = "4-4-2",
    fixture_map: dict[str, float] | None = None,
) -> tuple[list[Player], str, float]:
    """
    Returns (starting_xi, formation, predicted_total_points).
    Uses the optimizer across all valid formations.
    fixture_map: optional dict[team_slug → difficulty] from engine.fixtures.
    """
    available = [p for p in players if p.is_available]
    counts = Counter(p.position for p in available)
    logger.info(
        f"Available by position — GK:{counts.get(1,0)} DEF:{counts.get(2,0)} "
        f"MID:{counts.get(3,0)} FWD:{counts.get(4,0)} (total {len(available)}/{len(players)})"
    )
    if len(available) < 11:
        logger.warning(
            f"Only {len(available)} available players — cannot build XI. "
            f"{_missing_positions_reason(available)}"
        )
        return [], current_formation, 0.0

    starting_xi, formation, score = optimize_lineup(available, None, fixture_map)
    if not starting_xi:
        logger.warning(
            f"Optimizer found no valid formation. {_missing_positions_reason(available)}"
        )
    return starting_xi, formation, score


def build_lineup_message(
    starting_xi: list[Player],
    formation: str,
    predicted_pts: float,
    current_lineup_ids: list[int],
    fixture_map: dict[str, float] | None = None,
    llm_narrative: str | None = None,
) -> str:
    """Format a Telegram-ready markdown message for the proposed lineup."""
    current_set = set(current_lineup_ids)
    changed = [p for p in starting_xi if p.id not in current_set]

    lines = [
        f"⚽ *Alineación óptima — {formation}*",
        f"📊 Puntos esperados: *{predicted_pts:.1f}*\n",
    ]

    pos_labels = {
        1: "🧤 Portero",
        2: "🛡 Defensas",
        3: "⚙️ Centrocampistas",
        4: "🔴 Delanteros",
    }

    for pos in [1, 2, 3, 4]:
        pos_players = [p for p in starting_xi if p.position == pos]
        if not pos_players:
            continue
        lines.append(f"*{pos_labels[pos]}*")
        for p in pos_players:
            diff = fixture_map.get(p.team.slug if p.team else "", 1.0) if fixture_map else 1.0
            pts = score_player(p, diff)
            diff_emoji = "🟢" if diff >= 1.1 else ("🔴" if diff <= 0.8 else "🟡")
            new_flag = " 🔄" if p in changed else ""
            lines.append(
                f"  {p.name} {p.trend_emoji} {diff_emoji} ({pts:.1f} pts){new_flag}"
            )

    if changed:
        lines.append(f"\n🔄 *{len(changed)} cambio(s)* vs alineación actual")
    else:
        lines.append("\n✅ Sin cambios respecto a tu alineación actual")

    if llm_narrative:
        lines.append(f"\n🤖 _{llm_narrative}_")

    return "\n".join(lines)

