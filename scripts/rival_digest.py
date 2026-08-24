#!/usr/bin/env python3
"""
Daily digest of league activity (transfers, clause buyouts, market sales)
from the league "board" feed — so you can see what your rivals are doing
without checking the app.

Real shape observed from the API (undocumented by Biwenger):
  {
    "type": "transfer" | "clause" | "market",
    "content": [
        {"player": <id>, "from": {...} | absent, "to": {...} | absent,
         "amount": <int>, "bids": [{"user": {...}, "amount": <int>}, ...]},
        ...
    ],
    "date": <unix ts>,
  }
"content" is a LIST of individual operations (an event can bundle several),
and each operation only carries the player's numeric id — not the name —
so names are resolved via BiwengerClient.get_player() with an in-run cache.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

from config import settings
from api.client import BiwengerClient
from engine.rival_intel import build_rival_budget_message
from bot.telegram_bot import send_message

LOOKBACK_HOURS = float(os.environ.get("DIGEST_LOOKBACK_HOURS", "26"))

_player_name_cache: dict[int, str] = {}


def _player_name(client: BiwengerClient, player_id: int | None) -> str:
    if player_id is None:
        return "?"
    if player_id not in _player_name_cache:
        try:
            _player_name_cache[player_id] = client.get_player(player_id).get("name", f"#{player_id}")
        except Exception:
            _player_name_cache[player_id] = f"#{player_id}"
    return _player_name_cache[player_id]


def _event_timestamp(e: dict) -> datetime | None:
    ts = e.get("date") or e.get("createdAt") or e.get("created")
    if not isinstance(ts, (int, float)):
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        return None


def _format_item(client: BiwengerClient, etype: str, item: dict) -> str | None:
    player = _player_name(client, item.get("player"))
    from_u = (item.get("from") or {}).get("name")
    to_u = (item.get("to") or {}).get("name")
    amount = item.get("amount", 0)

    if etype == "clause":
        if from_u and to_u:
            return f"💸 *{to_u}* activó la cláusula de *{player}* (de {from_u}) por €{amount/1e6:.2f}M"
        return f"💸 Cláusula activada por *{player}* — €{amount/1e6:.2f}M"

    if etype == "market":
        if to_u:
            return f"🏷 *{to_u}* ganó a *{player}* en el mercado por €{amount/1e6:.2f}M"
        return None  # unsold lot, not interesting

    # "transfer" (and anything else with from/to/amount)
    if from_u and to_u:
        return f"🔁 *{to_u}* fichó a *{player}* de *{from_u}* por €{amount/1e6:.2f}M"
    if to_u:
        return f"🛒 *{to_u}* fichó a *{player}* por €{amount/1e6:.2f}M (mercado)"
    if from_u:
        return f"📤 *{from_u}* soltó a *{player}* por €{amount/1e6:.2f}M"
    return None


def _format_event(client: BiwengerClient, e: dict) -> list[str]:
    etype = e.get("type", "")
    content = e.get("content")
    items = content if isinstance(content, list) else [content] if isinstance(content, dict) else []
    out: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        desc = _format_item(client, etype, item)
        if desc:
            out.append(desc)
    return out


def main() -> None:
    logger.info("📰 Rival digest starting…")

    client = BiwengerClient()
    client.login()

    try:
        board = client.get_league_board(limit=50)
    except Exception as exc:
        logger.warning(f"Could not fetch league board: {exc}")
        return

    events = board if isinstance(board, list) else (
        board.get("board") or board.get("items") or board.get("data") or []
    )
    if not events:
        logger.info("No league board data returned.")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    lines: list[str] = []
    for e in events:
        try:
            ts = _event_timestamp(e)
            if ts and ts < cutoff:
                continue
            lines.extend(_format_event(client, e))
        except Exception as exc:
            logger.warning(f"Skipping unparseable board event ({exc}): {e}")
            continue
        if len(lines) >= 20:
            lines = lines[:20]
            break

    if lines:
        send_message("📰 *Actividad de la liga (últimas 24h)*\n\n" + "\n".join(f"• {l}" for l in lines))
        logger.info(f"Sent digest with {len(lines)} event(s).")
    else:
        logger.info("No recognised recent activity in the board feed.")

    try:
        standings = client.get_standings()
        send_message(build_rival_budget_message(standings, settings.biwenger_user_id))
    except Exception as exc:
        logger.warning(f"Could not send rival budget estimate: {exc}")


if __name__ == "__main__":
    main()
