"""
Position Manager — オープンポジションの追跡と自動クローズ
スプレッドが収束したら自動的にポジションをクローズして利益確定
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import config
from exchanges.manager import ExchangeManager
import notifier

log = logging.getLogger("arb.positions")

POSITIONS_FILE = "open_positions.json"

# Close when spread narrows to this % or less
CLOSE_SPREAD_PCT = 0.05  # 0.05% = almost converged
# Force-close after this many seconds (prevent stale positions)
MAX_POSITION_AGE = 3600  # 1 hour


class PositionManager:
    """Tracks open arb positions and auto-closes when spread converges."""

    def __init__(self, manager: ExchangeManager):
        self.manager = manager
        self.positions: list[dict] = []
        self._load()

    def _load(self):
        """Load open positions from file."""
        if os.path.exists(POSITIONS_FILE):
            try:
                with open(POSITIONS_FILE, "r") as f:
                    self.positions = json.load(f)
            except Exception:
                self.positions = []

    def _save(self):
        """Save open positions to file."""
        try:
            with open(POSITIONS_FILE, "w") as f:
                json.dump(self.positions, f, indent=2, default=str)
        except Exception as e:
            log.error("ポジション保存失敗: %s", e)

    def add_position(self, opp, buy_result: dict, sell_result: dict):
        """Record a new open arb position."""
        pos = {
            "id": len(self.positions) + 1,
            "opened_at": datetime.now().isoformat(),
            "opened_ts": time.time(),
            "symbol": opp.symbol,
            # BUY side
            "buy_exchange": opp.buy_exchange,
            "buy_market_type": opp.buy_market_type,
            "buy_symbol": opp.buy_symbol,
            "buy_price": opp.buy_price,
            "buy_order_id": buy_result.get("id"),
            # SELL side (futures short)
            "sell_exchange": opp.sell_exchange,
            "sell_market_type": opp.sell_market_type,
            "sell_symbol": opp.sell_symbol,
            "sell_price": opp.sell_price,
            "sell_order_id": sell_result.get("id"),
            # Trade info
            "amount_usdt": opp.trade_amount_usdt,
            "open_spread_pct": opp.spread_pct,
            "expected_profit": opp.net_profit_usdt,
            "status": "open",
        }
        self.positions.append(pos)
        self._save()
        log.info(
            "📌 ポジション追加: #%d %s | BUY %s(%s) → SHORT %s(%s) | spread=%.3f%%",
            pos["id"], pos["symbol"],
            pos["buy_exchange"].upper(), pos["buy_market_type"],
            pos["sell_exchange"].upper(), pos["sell_market_type"],
            pos["open_spread_pct"],
        )

    def check_and_close(self) -> list[dict]:
        """Check all open positions and close if spread has converged."""
        closed = []

        for pos in self.positions:
            if pos["status"] != "open":
                continue

            try:
                result = self._check_position(pos)
                if result:
                    closed.append(result)
            except Exception as e:
                log.error("ポジションチェック失敗 #%d: %s", pos["id"], e)

        if closed:
            self._save()

        return closed

    def _check_position(self, pos: dict) -> Optional[dict]:
        """Check one position — close if spread converged or timed out."""
        age = time.time() - pos["opened_ts"]
        symbol = pos["symbol"]

        # Get current prices
        buy_ex = self.manager.exchanges.get(pos["buy_exchange"])
        sell_ex = self.manager.exchanges.get(pos["sell_exchange"])
        if not buy_ex or not sell_ex:
            return None

        try:
            buy_ticker = buy_ex.fetch_ticker(pos["buy_symbol"])
            sell_ticker = sell_ex.fetch_ticker(pos["sell_symbol"])

            # Current spread (how much gap remains)
            # We want: buy side price went UP, sell side price went DOWN
            current_buy_price = float(buy_ticker.get("bid") or 0)
            current_sell_price = float(sell_ticker.get("ask") or 0)

            if current_buy_price <= 0 or current_sell_price <= 0:
                return None

            # Current spread: if positive, gap still exists. If near zero, converged.
            current_spread = ((current_sell_price - current_buy_price)
                              / current_buy_price) * 100

        except Exception as e:
            log.debug("価格取得失敗 %s: %s", symbol, e)
            return None

        # Close conditions
        should_close = False
        reason = ""

        if current_spread <= CLOSE_SPREAD_PCT:
            should_close = True
            reason = "スプレッド収束 (%.3f%%)" % current_spread
        elif age > MAX_POSITION_AGE:
            should_close = True
            reason = "タイムアウト (%d分)" % (age / 60)

        if not should_close:
            return None

        log.info("🔄 クローズ開始: #%d %s — %s", pos["id"], symbol, reason)

        return self._close_position(pos, current_buy_price, current_sell_price, reason)

    def _close_position(self, pos: dict,
                        current_buy_price: float,
                        current_sell_price: float,
                        reason: str) -> Optional[dict]:
        """Close both legs of an arb position."""
        amount = pos["amount_usdt"]

        # Close BUY side: if spot → sell spot, if futures long → close long
        if pos["buy_market_type"] == "spot":
            close_buy = self.manager.place_market_sell(
                pos["buy_exchange"], pos["buy_symbol"], amount
            )
        else:
            # Close futures long → open short to offset
            close_buy = self.manager.place_futures_short(
                pos["buy_exchange"], pos["buy_symbol"], amount
            )

        # Close SELL side: close futures short → buy to cover
        close_sell = self.manager.place_futures_long(
            pos["sell_exchange"], pos["sell_symbol"], amount
        )

        success = close_buy is not None and close_sell is not None

        # Calculate actual P&L
        open_spread = pos["open_spread_pct"]
        buy_fee = config.TAKER_FEES.get(pos["buy_exchange"], 0.001) * 100
        sell_fee = config.TAKER_FEES.get(pos["sell_exchange"], 0.001) * 100
        # Profit = open spread - close spread - fees (open + close)
        total_fees = (buy_fee + sell_fee) * 2  # 2x because open + close
        close_spread = ((current_sell_price - current_buy_price)
                        / current_buy_price) * 100
        actual_profit_pct = open_spread - close_spread - total_fees
        actual_profit_usdt = amount * (actual_profit_pct / 100)

        # Update position
        pos["status"] = "closed" if success else "close_failed"
        pos["closed_at"] = datetime.now().isoformat()
        pos["close_reason"] = reason
        pos["close_buy_price"] = current_buy_price
        pos["close_sell_price"] = current_sell_price
        pos["close_spread_pct"] = close_spread
        pos["actual_profit_pct"] = actual_profit_pct
        pos["actual_profit_usdt"] = actual_profit_usdt

        if success:
            log.info(
                "✅ クローズ成功: #%d %s | 実利益: $%.2f (%.3f%%)",
                pos["id"], pos["symbol"],
                actual_profit_usdt, actual_profit_pct,
            )
            # Send Telegram notification
            msg = (
                "📊 ポジションクローズ\n\n"
                f"{pos['symbol']}\n"
                f"Open: spread {open_spread:.3f}%\n"
                f"Close: spread {close_spread:.3f}%\n"
                f"理由: {reason}\n\n"
                f"実利益: ${actual_profit_usdt:.2f} ({actual_profit_pct:.3f}%)\n"
                f"⏱ {datetime.now():%H:%M:%S}"
            )
            notifier.send_message(msg)
        else:
            log.error(
                "❌ クローズ失敗: #%d %s — 手動確認が必要!",
                pos["id"], pos["symbol"],
            )

        return pos if success else None

    def get_open_count(self) -> int:
        """Return count of open positions."""
        return sum(1 for p in self.positions if p["status"] == "open")

    def get_open_positions(self) -> list[dict]:
        """Return all open positions."""
        return [p for p in self.positions if p["status"] == "open"]

    def get_summary(self) -> str:
        """Return summary of all positions."""
        open_pos = self.get_open_positions()
        closed = [p for p in self.positions if p["status"] == "closed"]
        total_profit = sum(p.get("actual_profit_usdt", 0) for p in closed)

        return (
            f"📊 ポジション: {len(open_pos)}件オープン, "
            f"{len(closed)}件クローズ済み, "
            f"累計利益: ${total_profit:.2f}"
        )
