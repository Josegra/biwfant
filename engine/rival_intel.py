"""
Rival budget estimation.

Biwenger does NOT publish its balance/overdraft formula, and in leagues
where "balance": "hidden" is set (like this one), you can't see rivals'
actual money. This is a community-reverse-engineered approximation: a
manager's spendable "credit line" beyond their visible balance is roughly
a third of their squad value. Treat it as a rough guide, not an exact
number — if you observe real winning bids that contradict it, adjust
CREDIT_LINE_FACTOR below.
"""

from __future__ import annotations

CREDIT_LINE_FACTOR = 1 / 3


def estimate_max_bid(team_value: int, known_balance: int | None = None) -> int:
    """Rough max-bid estimate for a rival. known_balance=None → balance unknown/hidden."""
    credit_line = int(team_value * CREDIT_LINE_FACTOR)
    if known_balance is not None:
        return max(0, known_balance + credit_line)
    return max(0, credit_line)


def build_rival_budget_message(
    standings: list[dict], my_user_id: int, top_n: int = 8
) -> str:
    """Format a Telegram message estimating each rival's max bid."""
    lines = ["💰 *Presupuesto estimado de rivales* (aproximado)\n"]
    shown = 0
    for u in standings:
        uid = u.get("id") or u.get("user_id")
        if uid == my_user_id:
            continue
        name = u.get("name") or u.get("user_name", "?")
        team_value = u.get("teamValue") or u.get("team_value") or 0
        known_balance = u.get("balance")  # usually absent/hidden in this league
        est = estimate_max_bid(team_value, known_balance)
        lines.append(
            f"• *{name}* — valor plantilla €{team_value/1e6:.1f}M "
            f"→ puja máx. estimada ≈ €{est/1e6:.1f}M"
        )
        shown += 1
        if shown >= top_n:
            break

    if shown == 0:
        return "💰 No hay datos de clasificación disponibles todavía."

    lines.append(
        "\n_Estimación no oficial — Biwenger no publica la fórmula real de saldo/crédito. "
        "Úsala como referencia, no como dato exacto._"
    )
    return "\n".join(lines)
