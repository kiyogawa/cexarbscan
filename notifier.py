"""
Notifier — Telegram通知
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import config

log = logging.getLogger("arb.notify")

# Lazy import to avoid errors if telegram not installed
_bot = None


def _get_bot():
    global _bot
    if _bot is None:
        if not config.TELEGRAM_BOT_TOKEN:
            return None
        try:
            from telegram import Bot
            _bot = Bot(token=config.TELEGRAM_BOT_TOKEN)
        except ImportError:
            log.warning("python-telegram-bot未インストール。Telegram通知無効。")
            return None
    return _bot


async def _send_async(text: str):
    bot = _get_bot()
    if bot is None or not config.TELEGRAM_CHAT_ID:
        return
    try:
        await bot.send_message(
            chat_id=config.TELEGRAM_CHAT_ID,
            text=text,
            parse_mode="HTML",
        )
    except Exception as e:
        log.error("Telegram送信失敗: %s", e)


def send_message(text: str):
    """Send a message via Telegram (sync wrapper)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(_send_async(text))
        else:
            loop.run_until_complete(_send_async(text))
    except RuntimeError:
        asyncio.run(_send_async(text))


def notify_opportunity(opp) -> None:
    """Send opportunity alert via Telegram."""
    text = (
        f"🔔 <b>アービトラージ機会発見！</b>\n\n"
        f"<b>{opp.symbol}</b>\n"
        f"📈 BUY: <b>{opp.buy_exchange.upper()}</b> ({opp.buy_market_type}) "
        f"@ {opp.buy_price:.6g}\n"
        f"📉 SELL: <b>{opp.sell_exchange.upper()}</b> ({opp.sell_market_type}) "
        f"@ {opp.sell_price:.6g}\n\n"
        f"Spread: {opp.spread_pct:.3f}%\n"
        f"<b>Net Profit: {opp.net_profit_pct:.3f}%</b> "
        f"(${opp.net_profit_usdt:.2f} on ${opp.trade_amount_usdt:.0f})\n\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    send_message(text)
    log.info("📱 Telegram通知送信: %s", opp.symbol)


def notify_trade_result(opp, buy_result: dict, sell_result: dict) -> None:
    """Send trade execution result."""
    status = "✅ 成功" if buy_result and sell_result else "❌ 失敗"
    text = (
        f"📊 <b>取引{status}</b>\n\n"
        f"<b>{opp.symbol}</b>\n"
        f"BUY: {opp.buy_exchange.upper()} → "
        f"ID: {buy_result.get('id', 'N/A') if buy_result else 'FAILED'}\n"
        f"SELL: {opp.sell_exchange.upper()} → "
        f"ID: {sell_result.get('id', 'N/A') if sell_result else 'FAILED'}\n\n"
        f"Est. Profit: ${opp.net_profit_usdt:.2f}\n"
        f"⏰ {datetime.now().strftime('%H:%M:%S')}"
    )
    send_message(text)


def notify_error(msg: str) -> None:
    """Send error notification."""
    text = f"⚠️ <b>エラー</b>\n\n{msg}\n\n⏰ {datetime.now().strftime('%H:%M:%S')}"
    send_message(text)


def notify_daily_summary(stats: dict) -> None:
    """Send daily P&L summary."""
    text = (
        f"📊 <b>日次サマリー</b>\n\n"
        f"検出機会: {stats.get('opportunities', 0)} 件\n"
        f"実行取引: {stats.get('trades', 0)} 件\n"
        f"総利益: ${stats.get('total_profit', 0):.2f}\n"
        f"勝率: {stats.get('win_rate', 0):.1f}%\n\n"
        f"📅 {datetime.now().strftime('%Y-%m-%d')}"
    )
    send_message(text)
