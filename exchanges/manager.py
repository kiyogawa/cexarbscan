"""
Exchange Manager — 6取引所のCCXTインスタンスを統一管理
MEXC, Bitget, LBank, KuCoin, BingX, Gate.io
"""

from __future__ import annotations

import logging
from typing import Optional

import ccxt

import config

log = logging.getLogger("arb.exchanges")


# CCXT exchange class mapping
EXCHANGE_CLASSES = {
    "mexc": ccxt.mexc,
    "bitget": ccxt.bitget,
    "lbank": ccxt.lbank,
    "kucoin": ccxt.kucoin,
    "bingx": ccxt.bingx,
    "gateio": ccxt.gateio,
    "coinw": ccxt.coinw,
}


class ExchangeManager:
    """Manages connections to all 6 exchanges."""

    def __init__(self):
        self.exchanges: dict[str, ccxt.Exchange] = {}
        self._init_exchanges()

    def _init_exchanges(self):
        """Initialize CCXT instances for all configured exchanges."""
        for name, creds in config.EXCHANGES.items():
            if not creds.get("apiKey"):
                log.warning("⚠️  %s: APIキー未設定（読み取り専用モード）", name.upper())

            cls = EXCHANGE_CLASSES.get(name)
            if cls is None:
                log.error("❌ %s: 未対応の取引所", name)
                continue

            opts = {
                "enableRateLimit": True,
                "timeout": 15000,
            }

            # Add credentials if available
            if creds.get("apiKey"):
                opts["apiKey"] = creds["apiKey"]
            if creds.get("secret"):
                opts["secret"] = creds["secret"]
            if creds.get("password"):
                opts["password"] = creds["password"]

            try:
                exchange = cls(opts)
                self.exchanges[name] = exchange
                log.info("✅ %s: 接続準備完了", name.upper())
            except Exception as e:
                log.error("❌ %s: 初期化失敗 — %s", name.upper(), e)

    def get_active_exchanges(self) -> list[str]:
        """Return list of active exchange names."""
        return list(self.exchanges.keys())

    # ──────────────────────────────────────────
    # Market data
    # ──────────────────────────────────────────

    def load_all_markets(self):
        """Load markets for all exchanges (call once at startup)."""
        for name, ex in self.exchanges.items():
            try:
                ex.load_markets()
                log.info("📊 %s: %d マーケット読込完了", name.upper(), len(ex.markets))
            except Exception as e:
                log.error("❌ %s: マーケット読み込み失敗 — %s", name.upper(), e)

    def get_common_symbols(self, market_type: str = "both") -> list[str]:
        """
        Find symbols listed on 2+ exchanges.
        If WATCHLIST is configured, filter it to available symbols.
        market_type: 'spot', 'futures', 'both'
        Returns normalized symbol list (e.g., 'BTC/USDT').
        """
        exchange_symbols: dict[str, set[str]] = {}

        for name, ex in self.exchanges.items():
            if not ex.markets:
                log.debug("Skipping %s (no markets loaded)", name)
                continue
            symbols = set()
            for sym, market in ex.markets.items():
                # Filter by USDT pairs only
                if "/USDT" not in sym:
                    continue

                # Filter by market type
                is_spot = market.get("spot", False)
                is_swap = market.get("swap", False)

                if market_type == "spot" and not is_spot:
                    continue
                if market_type == "futures" and not is_swap:
                    continue
                if market_type == "both" and not (is_spot or is_swap):
                    continue

                # Normalize: strip :USDT suffix for swaps
                base = sym.split("/")[0]
                if base in config.BLACKLIST:
                    continue

                normalized = f"{base}/USDT"
                symbols.add(normalized)

            exchange_symbols[name] = symbols

        # Find symbols on 2+ exchanges
        all_symbols: dict[str, int] = {}
        for symbols in exchange_symbols.values():
            for sym in symbols:
                all_symbols[sym] = all_symbols.get(sym, 0) + 1

        common = sorted([s for s, count in all_symbols.items() if count >= 2])

        # Filter by WATCHLIST if configured
        if config.WATCHLIST:
            common = [s for s in config.WATCHLIST if s in common]
            log.info("🔍 ウォッチリスト: %d / %d ペアが利用可能",
                     len(common), len(config.WATCHLIST))
        else:
            log.info("🔍 共通ペア: %d 個（2取引所以上に上場）", len(common))

        return common

    def fetch_all_prices(self, symbol: str) -> dict[str, dict]:
        """
        Fetch price for a symbol across all exchanges.
        Returns {exchange_name: {bid, ask, last, volume, market_type}}.
        """
        results = {}
        base = symbol.split("/")[0]

        for name, ex in self.exchanges.items():
            if not ex.markets:
                continue
            # Try spot
            spot_sym = f"{base}/USDT"
            swap_sym = f"{base}/USDT:USDT"

            for mtype, sym in [("spot", spot_sym), ("futures", swap_sym)]:
                if sym not in ex.markets:
                    continue
                try:
                    ticker = ex.fetch_ticker(sym)
                    bid = float(ticker.get("bid") or 0)
                    ask = float(ticker.get("ask") or 0)
                    last = float(ticker.get("last") or 0)
                    vol = float(ticker.get("quoteVolume") or 0)

                    if bid > 0 and ask > 0:
                        key = f"{name}_{mtype}"
                        results[key] = {
                            "exchange": name,
                            "market_type": mtype,
                            "symbol": sym,
                            "bid": bid,
                            "ask": ask,
                            "last": last,
                            "volume_24h": vol,
                        }
                except Exception as e:
                    log.debug("%s %s %s: %s", name, mtype, sym, e)

        return results

    def fetch_orderbook(self, exchange: str, symbol: str,
                        limit: int = 10) -> dict:
        """Fetch orderbook for a specific exchange/symbol."""
        ex = self.exchanges.get(exchange)
        if not ex:
            return {"bids": [], "asks": []}
        try:
            return ex.fetch_order_book(symbol, limit=limit)
        except Exception as e:
            log.debug("Orderbook %s %s: %s", exchange, symbol, e)
            return {"bids": [], "asks": []}

    # ──────────────────────────────────────────
    # Balances
    # ──────────────────────────────────────────

    def get_all_balances(self) -> dict[str, dict]:
        """Get USDT balances for all exchanges."""
        balances = {}
        for name, ex in self.exchanges.items():
            if not ex.apiKey:
                balances[name] = {"free": 0, "used": 0, "total": 0, "error": "APIキー未設定"}
                continue
            try:
                bal = ex.fetch_balance()
                usdt = bal.get("USDT", {})
                balances[name] = {
                    "free": float(usdt.get("free") or 0),
                    "used": float(usdt.get("used") or 0),
                    "total": float(usdt.get("total") or 0),
                }
            except Exception as e:
                balances[name] = {"free": 0, "used": 0, "total": 0, "error": str(e)}
                log.error("%s 残高取得失敗: %s", name.upper(), e)
        return balances

    # ──────────────────────────────────────────
    # Order execution
    # ──────────────────────────────────────────

    def place_market_buy(self, exchange: str, symbol: str,
                         amount_usdt: float) -> Optional[dict]:
        """Place a market buy order by USDT amount."""
        ex = self.exchanges.get(exchange)
        if not ex:
            return None

        if config.TRADE_MODE == "dry_run":
            log.info("[DRY RUN] BUY %s on %s — $%.2f",
                     symbol, exchange.upper(), amount_usdt)
            return {"id": "dry_run", "status": "simulated", "side": "buy",
                    "amount_usdt": amount_usdt}

        try:
            # Fetch current price to calculate amount
            ticker = ex.fetch_ticker(symbol)
            price = float(ticker["ask"])
            amount = amount_usdt / price

            # Round to exchange precision
            amount = float(ex.amount_to_precision(symbol, amount))

            order = ex.create_order(
                symbol=symbol,
                type="market",
                side="buy",
                amount=amount,
            )
            log.info("✅ BUY %s on %s — qty=%.6g id=%s",
                     symbol, exchange.upper(), amount, order.get("id"))
            return order
        except Exception as e:
            log.error("❌ BUY失敗 %s on %s: %s", symbol, exchange.upper(), e)
            return None

    def place_market_sell(self, exchange: str, symbol: str,
                          amount_usdt: float) -> Optional[dict]:
        """Place a market sell order by USDT amount."""
        ex = self.exchanges.get(exchange)
        if not ex:
            return None

        if config.TRADE_MODE == "dry_run":
            log.info("[DRY RUN] SELL %s on %s — $%.2f",
                     symbol, exchange.upper(), amount_usdt)
            return {"id": "dry_run", "status": "simulated", "side": "sell",
                    "amount_usdt": amount_usdt}

        try:
            ticker = ex.fetch_ticker(symbol)
            price = float(ticker["bid"])
            amount = amount_usdt / price

            amount = float(ex.amount_to_precision(symbol, amount))

            order = ex.create_order(
                symbol=symbol,
                type="market",
                side="sell",
                amount=amount,
            )
            log.info("✅ SELL %s on %s — qty=%.6g id=%s",
                     symbol, exchange.upper(), amount, order.get("id"))
            return order
        except Exception as e:
            log.error("❌ SELL失敗 %s on %s: %s", symbol, exchange.upper(), e)
            return None

    def test_connections(self) -> dict[str, bool]:
        """Test connectivity to all exchanges."""
        results = {}
        for name, ex in self.exchanges.items():
            try:
                ex.fetch_time()
                results[name] = True
                log.info("✅ %s: 接続OK", name.upper())
            except Exception as e:
                results[name] = False
                log.error("❌ %s: 接続失敗 — %s", name.upper(), e)
        return results
