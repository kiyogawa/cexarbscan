"""
Executor — アービトラージ取引の実行エンジン
dry_run / manual / auto の3モード対応
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime

import config
from exchanges.manager import ExchangeManager
from calculator import Opportunity
import notifier

log = logging.getLogger("arb.executor")

TRADE_HISTORY_FILE = "trade_history.json"


class Executor:
    """Executes arbitrage trades based on configured mode."""

    def __init__(self, manager: ExchangeManager):
        self.manager = manager
        self.trade_count = 0
        self.total_profit = 0.0
        self.history: list[dict] = []
        self._load_history()

    def _load_history(self):
        """Load trade history from file."""
        if os.path.exists(TRADE_HISTORY_FILE):
            try:
                with open(TRADE_HISTORY_FILE, "r") as f:
                    self.history = json.load(f)
                    self.trade_count = len(self.history)
                    self.total_profit = sum(
                        t.get("net_profit_usdt", 0) for t in self.history
                    )
            except Exception:
                self.history = []

    def _save_history(self):
        """Save trade history to file."""
        try:
            with open(TRADE_HISTORY_FILE, "w") as f:
                json.dump(self.history, f, indent=2, default=str)
        except Exception as e:
            log.error("履歴保存失敗: %s", e)

    def execute(self, opp: Opportunity) -> bool:
        """
        Execute an arbitrage trade based on TRADE_MODE.
        Returns True if executed (or simulated).
        """
        if config.TRADE_MODE == "dry_run":
            return self._dry_run(opp)
        elif config.TRADE_MODE == "manual":
            return self._manual(opp)
        elif config.TRADE_MODE == "auto":
            return self._auto_execute(opp)
        else:
            log.error("不明なTRADE_MODE: %s", config.TRADE_MODE)
            return False

    def _dry_run(self, opp: Opportunity) -> bool:
        """Log the opportunity without executing."""
        log.info(
            "🔍 [DRY RUN] %s: BUY %s @ %.6g → SELL %s @ %.6g | "
            "Net: %.3f%% ($%.2f)",
            opp.symbol,
            opp.buy_exchange.upper(), opp.buy_price,
            opp.sell_exchange.upper(), opp.sell_price,
            opp.net_profit_pct, opp.net_profit_usdt,
        )

        record = {
            "time": datetime.now().isoformat(),
            "mode": "dry_run",
            "symbol": opp.symbol,
            "buy_exchange": opp.buy_exchange,
            "sell_exchange": opp.sell_exchange,
            "buy_price": opp.buy_price,
            "sell_price": opp.sell_price,
            "spread_pct": opp.spread_pct,
            "net_profit_pct": opp.net_profit_pct,
            "net_profit_usdt": opp.net_profit_usdt,
            "trade_amount_usdt": opp.trade_amount_usdt,
        }
        self.history.append(record)
        self._save_history()
        return True

    def _manual(self, opp: Opportunity) -> bool:
        """Send notification for manual approval."""
        notifier.notify_opportunity(opp)
        log.info(
            "📱 [MANUAL] 通知送信済み: %s (%.3f%%) — 手動実行待ち",
            opp.symbol, opp.net_profit_pct,
        )
        return False  # Not auto-executed

    def _auto_execute(self, opp: Opportunity) -> bool:
        """Execute both sides of the arbitrage simultaneously."""
        log.info(
            "⚡ [AUTO] 実行開始: %s BUY %s → SELL %s",
            opp.symbol, opp.buy_exchange.upper(), opp.sell_exchange.upper(),
        )

        amount = opp.trade_amount_usdt

        # Execute both orders
        buy_result = self.manager.place_market_buy(
            opp.buy_exchange, opp.buy_symbol, amount
        )
        sell_result = self.manager.place_market_sell(
            opp.sell_exchange, opp.sell_symbol, amount
        )

        success = buy_result is not None and sell_result is not None

        if success:
            self.trade_count += 1
            self.total_profit += opp.net_profit_usdt
            log.info(
                "✅ 取引成功: %s | 推定利益: $%.2f | 累計: $%.2f",
                opp.symbol, opp.net_profit_usdt, self.total_profit,
            )
        else:
            log.error("❌ 取引失敗: %s", opp.symbol)

        # Notify
        notifier.notify_trade_result(opp, buy_result or {}, sell_result or {})

        # Record
        record = {
            "time": datetime.now().isoformat(),
            "mode": "auto",
            "symbol": opp.symbol,
            "buy_exchange": opp.buy_exchange,
            "sell_exchange": opp.sell_exchange,
            "buy_price": opp.buy_price,
            "sell_price": opp.sell_price,
            "spread_pct": opp.spread_pct,
            "net_profit_pct": opp.net_profit_pct,
            "net_profit_usdt": opp.net_profit_usdt,
            "trade_amount_usdt": amount,
            "success": success,
            "buy_order_id": buy_result.get("id") if buy_result else None,
            "sell_order_id": sell_result.get("id") if sell_result else None,
        }
        self.history.append(record)
        self._save_history()

        return success

    def get_stats(self) -> dict:
        """Get executor statistics."""
        wins = sum(1 for t in self.history if t.get("success", True))
        total = len(self.history)
        return {
            "trades": total,
            "wins": wins,
            "win_rate": (wins / total * 100) if total > 0 else 0,
            "total_profit": self.total_profit,
        }
