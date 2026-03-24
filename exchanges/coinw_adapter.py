"""
CoinW Custom Exchange Adapter
CCXTに非対応のため、CoinW REST APIを直接ラップ
"""

import requests
import time
import hashlib
import hmac
import logging

logger = logging.getLogger("arb.coinw")

BASE_URL = "https://api.coinw.com"


class CoinWExchange:
    """CoinW adapter that mimics CCXT interface for seamless integration."""

    def __init__(self, config=None):
        config = config or {}
        self.apiKey = config.get("apiKey", "")
        self.secret = config.get("secret", "")
        self.markets = None
        self.name = "CoinW"
        self.id = "coinw"
        self._ticker_cache = {}
        self._cache_time = 0
        self._cache_ttl = 3  # seconds

    def load_markets(self):
        """Load all markets from CoinW ticker endpoint."""
        try:
            resp = requests.get(
                f"{BASE_URL}/api/v1/public?command=returnTicker",
                timeout=10
            )
            data = resp.json()

            if data.get("code") != "200" or not data.get("data"):
                logger.error(f"CoinW load_markets failed: {data.get('msg')}")
                return None

            self.markets = {}
            self._ticker_cache = data["data"]
            self._cache_time = time.time()

            for symbol_raw, ticker_data in data["data"].items():
                # CoinW format: "BTC_USDT" -> "BTC/USDT"
                parts = symbol_raw.rsplit("_", 1)
                if len(parts) != 2:
                    continue

                base, quote = parts[0], parts[1]
                symbol = f"{base}/{quote}"

                self.markets[symbol] = {
                    "id": symbol_raw,
                    "symbol": symbol,
                    "base": base,
                    "quote": quote,
                    "active": ticker_data.get("isFrozen", 0) == 0,
                    "type": "spot",
                    "spot": True,
                    "info": ticker_data,
                }

            logger.info(f"📊 COINW: {len(self.markets)} マーケット読込完了")
            return self.markets

        except Exception as e:
            logger.error(f"CoinW load_markets error: {e}")
            return None

    def fetch_tickers(self, symbols=None):
        """Fetch all tickers (cached for _cache_ttl seconds)."""
        now = time.time()
        if now - self._cache_time > self._cache_ttl:
            try:
                resp = requests.get(
                    f"{BASE_URL}/api/v1/public?command=returnTicker",
                    timeout=10
                )
                data = resp.json()
                if data.get("code") == "200" and data.get("data"):
                    self._ticker_cache = data["data"]
                    self._cache_time = now
            except Exception as e:
                logger.error(f"CoinW fetch_tickers error: {e}")

        result = {}
        for symbol_raw, t in self._ticker_cache.items():
            parts = symbol_raw.rsplit("_", 1)
            if len(parts) != 2:
                continue
            symbol = f"{parts[0]}/{parts[1]}"

            if symbols and symbol not in symbols:
                continue

            last = float(t.get("last", 0))
            if last <= 0:
                continue

            result[symbol] = {
                "symbol": symbol,
                "last": last,
                "bid": float(t.get("highestBid", 0)),
                "ask": float(t.get("lowestAsk", 0)),
                "high": float(t.get("high24hr", 0)),
                "low": float(t.get("low24hr", 0)),
                "baseVolume": float(t.get("baseVolume", 0)),
                "info": t,
            }

        return result

    def fetch_ticker(self, symbol):
        """Fetch a single ticker."""
        tickers = self.fetch_tickers([symbol])
        return tickers.get(symbol)

    def fetch_balance(self):
        """Fetch account balance (requires API key)."""
        if not self.apiKey or not self.secret:
            return {"total": {}, "free": {}, "used": {}}

        # CoinW balance API would go here
        # For now, return empty (read-only mode still works for scanning)
        logger.warning("CoinW balance API not implemented yet")
        return {"total": {}, "free": {}, "used": {}}

    def create_order(self, symbol, type, side, amount, price=None, params=None):
        """Create order (placeholder for future implementation)."""
        raise NotImplementedError("CoinW order execution not yet implemented")

    def describe(self):
        """Return exchange description."""
        return {
            "id": "coinw",
            "name": "CoinW",
            "has": {
                "fetchTickers": True,
                "fetchTicker": True,
                "fetchBalance": True,
                "createOrder": False,
            }
        }
