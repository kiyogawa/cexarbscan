"""
Calculator — 手数料・スリッページ込みのネット利益計算
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import config

log = logging.getLogger("arb.calc")


@dataclass
class Opportunity:
    """Represents an arbitrage opportunity."""
    symbol: str
    buy_exchange: str
    buy_market_type: str
    buy_symbol: str
    buy_price: float       # ask price (we buy at ask)
    sell_exchange: str
    sell_market_type: str
    sell_symbol: str
    sell_price: float      # bid price (we sell at bid)
    spread_pct: float      # raw spread %
    buy_fee_pct: float
    sell_fee_pct: float
    net_profit_pct: float  # after fees
    trade_amount_usdt: float
    net_profit_usdt: float
    buy_volume_24h: float
    sell_volume_24h: float

    def summary(self) -> str:
        return (
            f"💰 {self.symbol} | "
            f"BUY {self.buy_exchange.upper()}({self.buy_market_type}) "
            f"@ {self.buy_price:.6g} → "
            f"SELL {self.sell_exchange.upper()}({self.sell_market_type}) "
            f"@ {self.sell_price:.6g}\n"
            f"   Spread: {self.spread_pct:.3f}% | "
            f"Net: {self.net_profit_pct:.3f}% | "
            f"Profit: ${self.net_profit_usdt:.2f} "
            f"(on ${self.trade_amount_usdt:.0f})"
        )


def calculate_opportunity(
    symbol: str,
    buy_data: dict,
    sell_data: dict,
    trade_amount: float | None = None,
) -> Opportunity | None:
    """
    Calculate net profit for buying on one exchange and selling on another.
    
    buy_data/sell_data format:
        {exchange, market_type, symbol, bid, ask, last, volume_24h}
    """
    buy_price = buy_data["ask"]    # We buy at ask
    sell_price = sell_data["bid"]  # We sell at bid

    if buy_price <= 0 or sell_price <= 0:
        return None

    # Raw spread
    spread_pct = ((sell_price - buy_price) / buy_price) * 100

    if spread_pct <= 0:
        return None

    # Fees
    buy_fee = config.TAKER_FEES.get(buy_data["exchange"], 0.001)
    sell_fee = config.TAKER_FEES.get(sell_data["exchange"], 0.001)

    # Net profit after fees (both sides)
    net_pct = spread_pct - (buy_fee * 100) - (sell_fee * 100)

    if net_pct < config.MIN_PROFIT_PCT:
        return None

    # Trade amount
    amount = trade_amount or config.MAX_TRADE_USDT

    # Check if volume supports the trade
    min_vol = min(buy_data["volume_24h"], sell_data["volume_24h"])
    if min_vol > 0 and amount > min_vol * 0.01:
        # Don't trade more than 1% of 24h volume
        amount = min(amount, min_vol * 0.01)

    if amount < config.MIN_TRADE_USDT:
        return None

    net_profit_usdt = amount * (net_pct / 100)

    return Opportunity(
        symbol=symbol,
        buy_exchange=buy_data["exchange"],
        buy_market_type=buy_data["market_type"],
        buy_symbol=buy_data["symbol"],
        buy_price=buy_price,
        sell_exchange=sell_data["exchange"],
        sell_market_type=sell_data["market_type"],
        sell_symbol=sell_data["symbol"],
        sell_price=sell_price,
        spread_pct=spread_pct,
        buy_fee_pct=buy_fee * 100,
        sell_fee_pct=sell_fee * 100,
        net_profit_pct=net_pct,
        trade_amount_usdt=amount,
        net_profit_usdt=net_profit_usdt,
        buy_volume_24h=buy_data["volume_24h"],
        sell_volume_24h=sell_data["volume_24h"],
    )


def find_opportunities(all_prices: dict[str, dict],
                       symbol: str) -> list[Opportunity]:
    """
    Find all profitable pairs from price data.
    all_prices: {exchange_mtype: price_data} from ExchangeManager.fetch_all_prices()
    """
    opportunities = []
    keys = list(all_prices.keys())

    for i in range(len(keys)):
        for j in range(len(keys)):
            if i == j:
                continue

            buy_key = keys[i]
            sell_key = keys[j]
            buy_data = all_prices[buy_key]
            sell_data = all_prices[sell_key]

            # Skip same exchange (spot vs futures on same exchange is fine)
            if (buy_data["exchange"] == sell_data["exchange"] and
                    buy_data["market_type"] == sell_data["market_type"]):
                continue

            opp = calculate_opportunity(symbol, buy_data, sell_data)
            if opp:
                opportunities.append(opp)

    # Sort by net profit descending
    opportunities.sort(key=lambda x: x.net_profit_pct, reverse=True)
    return opportunities
