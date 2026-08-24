#!/usr/bin/env python3
"""
Daily digest of league activity (transfers, market sales) from the
league "board" feed — so you can see what your rivals are doing
without checking the app.

NOTE: the exact shape of the board feed hasn't been observed live yet
(Biwenger doesn't document it). _format_event() is a best-effort parser
for the commonly-seen "transfer"/"market" event shapes; if it doesn't
recognise an event it's skipped rather than crashing the run. Check the
logs after the first real run — if nothing gets formatted despite
activity existing, the raw shape needs a quick look.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger

from config import settings
from api.client import BiwengerClient
from bot.telegram_bot import send_message

LOOKBACK_HOURS = float(os.environ.get("DIGEST_LOOKBACK_HOURS", "26"))


def _event_timestamp(e: dict) -> datetime | None:
    ts = e.get("date") or e.get("createdAt") or e.get("created")
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception:
        pass
    return None


def _format_event(e: dict) -> str | None:
    etype = e.get("type", "")
    c = e.get("content") or e

    if etype == "transfer":
        player = (c.get("player") or {}).get("name", "?")
        to_u = (c.get("to") or {}).get("name", "?")
        from_u = (c.get("from") or {}).get("name")
        amount = c.get("amount", 0)
        if from_u:
            return f"🔁 *{to_u}* fichó a *{player}* de *{from_u}* por €{amount/1e6:.2f}M"
        return f"🛒 *{to_u}* fichó a *{player}* por €{amount/1e6:.2f}M (mercado)"

    if etype == "market":
        player = (c.get("player") or {}).get("name", "?")
        seller = (c.get("user") or {}).get("name", "?")
        price = c.get("price", 0)
        return f"🏷 *{seller}* puso en venta a *{player}* por €{price/1e6:.2f}M"

    return None


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
        ts = _event_timestamp(e)
        if ts and ts < cutoff:
            continue
        desc = _format_event(e)
        if desc:
            lines.append(f"• {desc}")
        if len(lines) >= 20:
            break

    if not lines:
        logger.info("No recognised recent activity in the board feed.")
        if events:
            logger.debug(f"Sample raw event for debugging: {events[0]}")
        return

    send_message("📰 *Actividad de la liga (últimas 24h)*\n\n" + "\n".join(lines))
    logger.info(f"Sent digest with {len(lines)} event(s).")


if __name__ == "__main__":
    main()
