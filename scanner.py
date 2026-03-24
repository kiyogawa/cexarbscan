"""
Scanner — 6取引所の価格をスキャンしてアービトラージ機会を検出
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

import config
from exchanges.manager import ExchangeManager
from calculator import find_opportunities, Opportunity
import notifier

log = logging.getLogger("arb.scanner")


class Scanner:
    """Main arbitrage scanner — loops across all exchanges & symbols."""

    def __init__(self, manager: ExchangeManager):
        self.manager = manager
        self.common_symbols: list[str] = []
        self.stats = {
            "scans": 0,
            "opportunities": 0,
            "best_spread": 0.0,
            "last_opportunity": None,
        }
        # Cooldown: don't re-alert same opportunity within N seconds
        self._alerted: dict[str, float] = {}
        self._alert_cooldown = 300  # 5 minutes

    def init(self):
        """Load markets and find common symbols."""
        log.info("🔄 マーケット情報を読み込み中...")
        self.manager.load_all_markets()
        self.common_symbols = self.manager.get_common_symbols(
            market_type=config.MARKET_TYPE
        )
        log.info("✅ 初期化完了: %d 共通ペアを監視", len(self.common_symbols))

    def scan_once(self) -> list[Opportunity]:
        """Run one scan cycle across all symbols."""
        all_opportunities: list[Opportunity] = []

        for symbol in self.common_symbols:
            try:
                prices = self.manager.fetch_all_prices(symbol)
                if len(prices) < 2:
                    continue

                opps = find_opportunities(prices, symbol)
                all_opportunities.extend(opps)

            except Exception as e:
                log.debug("スキャン失敗 %s: %s", symbol, e)

        self.stats["scans"] += 1

        if all_opportunities:
            all_opportunities.sort(key=lambda x: x.net_profit_pct, reverse=True)
            self.stats["opportunities"] += len(all_opportunities)
            best = all_opportunities[0]
            self.stats["best_spread"] = max(
                self.stats["best_spread"], best.net_profit_pct
            )
            self.stats["last_opportunity"] = datetime.now().strftime("%H:%M:%S")

        return all_opportunities

    def should_alert(self, opp: Opportunity) -> bool:
        """Check if we should send an alert (cooldown per symbol)."""
        key = opp.symbol  # 同じペアは5分間再通知しない
        now = time.time()
        last = self._alerted.get(key, 0)
        if now - last < self._alert_cooldown:
            return False
        self._alerted[key] = now
        return True

    def run_loop(self, callback=None):
        """
        Main scanning loop.
        callback: optional function called with each opportunity list.
        """
        log.info("🚀 スキャン開始 (interval=%ds, mode=%s)",
                 config.SCAN_INTERVAL, config.TRADE_MODE)

        try:
            while True:
                start = time.time()

                opps = self.scan_once()

                if opps:
                    # Group by symbol → only keep the best per pair
                    best_per_symbol: dict[str, Opportunity] = {}
                    for opp in opps:
                        existing = best_per_symbol.get(opp.symbol)
                        if existing is None or opp.net_profit_pct > existing.net_profit_pct:
                            best_per_symbol[opp.symbol] = opp

                    # Sort best-per-symbol by profit
                    top_opps = sorted(
                        best_per_symbol.values(),
                        key=lambda x: x.net_profit_pct,
                        reverse=True,
                    )

                    for opp in top_opps[:5]:  # Top 5 unique pairs only
                        log.info(opp.summary())

                        if self.should_alert(opp):
                            notifier.notify_opportunity(opp)

                    if callback:
                        callback(opps)

                elapsed = time.time() - start
                sleep_time = max(0, config.SCAN_INTERVAL - elapsed)

                if self.stats["scans"] % 12 == 0:  # Every minute
                    log.info(
                        "📊 Stats: scans=%d, opps=%d, best=%.3f%%",
                        self.stats["scans"],
                        self.stats["opportunities"],
                        self.stats["best_spread"],
                    )

                time.sleep(sleep_time)

        except KeyboardInterrupt:
            log.info("⏹ スキャン停止")
