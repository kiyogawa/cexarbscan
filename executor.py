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
from position_manager import PositionManager
import notifier

log = logging.getLogger("arb.executor")

TRADE_HISTORY_FILE = "trade_history.json"


class Executor:
    """Executes arbitrage trades based on configured mode."""

    def __init__(self, manager: ExchangeManager):
        self.manager = manager
        self.positions = PositionManager(manager)
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
        """Execute arbitrage — allow any trade where SELL side is futures."""

        # ── Gate.io はシグナル通知のみ（自動実行しない） ──
        if opp.buy_exchange == "gateio" or opp.sell_exchange == "gateio":
            log.info("🚧 [SIGNAL ONLY] Gate.io絡みのため自動実行をスキップし、通知のみ行います: %s", opp.symbol)
            return self._manual(opp)

        # ── SELL side must be futures (SHORT = USDT margin only) ──
        # SELL spot requires holding the coin → block
        if opp.sell_market_type != "futures":
            log.info(
                "⏭️  [SKIP] %s: SELL is spot (%s→%s %s) — need coin",
                opp.symbol,
                opp.buy_exchange.upper(), opp.sell_exchange.upper(),
                opp.sell_market_type,
            )
            return self._dry_run(opp)

        log.info(
            "⚡ [AUTO] %s: BUY %s(%s) → SHORT %s(%s)",
            opp.symbol,
            opp.buy_exchange.upper(), opp.buy_market_type,
            opp.sell_exchange.upper(), opp.sell_market_type,
        )

        amount = opp.trade_amount_usdt

        # Step 1: BUY side (spot or futures long)
        if opp.buy_market_type == "spot":
            buy_result = self.manager.place_market_buy(
                opp.buy_exchange, opp.buy_symbol, amount
            )
        else:
            # futures long
            buy_result = self.manager.place_futures_long(
                opp.buy_exchange, opp.buy_symbol, amount
            )

        if buy_result is None:
            log.error("❌ BUY失敗 — 取引中止: %s", opp.symbol)
            notifier.notify_trade_result(opp, {}, {})
            self._record(opp, False, None, None, amount)
            return False

        # Step 2: SHORT futures (SELL side)
        sell_result = self.manager.place_futures_short(
            opp.sell_exchange, opp.sell_symbol, amount
        )

        if sell_result is None:
            # Rollback: reverse the buy
            log.error("❌ SHORT失敗 — BUYをロールバック中...")
            if opp.buy_market_type == "spot":
                rollback = self.manager.place_market_sell(
                    opp.buy_exchange, opp.buy_symbol, amount
                )
            else:
                # Close the futures long
                rollback = self.manager.place_futures_short(
                    opp.buy_exchange, opp.buy_symbol, amount
                )
            if rollback:
                log.info("🔄 ロールバック成功: %s", opp.symbol)
            else:
                log.error("🚨 ロールバック失敗! %s のポジションが残ってます!", opp.symbol)
            notifier.notify_trade_result(opp, buy_result, {})
            self._record(opp, False, buy_result.get("id"), None, amount)
            return False

        # Success!
        self.trade_count += 1
        self.total_profit += opp.net_profit_usdt
        log.info(
            "✅ 取引成功: %s | 推定利益: $%.2f | 累計: $%.2f",
            opp.symbol, opp.net_profit_usdt, self.total_profit,
        )

        notifier.notify_trade_result(opp, buy_result, sell_result)

        # Track position for auto-close
        self.positions.add_position(opp, buy_result, sell_result)

        self._record(
            opp, True,
            buy_result.get("id"), sell_result.get("id"), amount,
        )
        return True

    def _record(self, opp, success, buy_id, sell_id, amount):
        """Record trade to history."""
        record = {
            "time": datetime.now().isoformat(),
            "mode": "auto",
            "symbol": opp.symbol,
            "buy_exchange": opp.buy_exchange,
            "sell_exchange": opp.sell_exchange,
            "buy_market_type": opp.buy_market_type,
            "sell_market_type": opp.sell_market_type,
            "buy_price": opp.buy_price,
            "sell_price": opp.sell_price,
            "spread_pct": opp.spread_pct,
            "net_profit_pct": opp.net_profit_pct,
            "net_profit_usdt": opp.net_profit_usdt,
            "trade_amount_usdt": amount,
            "success": success,
            "buy_order_id": buy_id,
            "sell_order_id": sell_id,
        }
        self.history.append(record)
        self._save_history()

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
