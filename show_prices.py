"""
Quick price comparison — 全ペアの取引所間価格差を一覧表示
Usage: python3 show_prices.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.table import Table
from rich import box

import config
from exchanges.manager import ExchangeManager

console = Console()

# テスト用：少数ペアに絞る
TEST_SYMBOLS = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "XRP/USDT", "DOGE/USDT",
    "PEPE/USDT", "WIF/USDT", "BONK/USDT", "SHIB/USDT", "FLOKI/USDT",
    "SUI/USDT", "SEI/USDT", "INJ/USDT", "ARB/USDT", "OP/USDT",
]


def main():
    console.print("\n[bold cyan]🔍 CEX Price Comparison — 取引所間価格差チェック[/bold cyan]\n")

    mgr = ExchangeManager()
    console.print("[dim]マーケット読込中...[/dim]")
    mgr.load_all_markets()

    for symbol in TEST_SYMBOLS:
        prices = mgr.fetch_all_prices(symbol)
        if len(prices) < 2:
            continue

        # Build price table
        table = Table(
            title=f"💱 {symbol}",
            box=box.SIMPLE_HEAVY,
            show_header=True,
            header_style="bold",
            title_style="bold yellow",
        )
        table.add_column("取引所", style="cyan")
        table.add_column("Type")
        table.add_column("Bid (売)", justify="right", style="green")
        table.add_column("Ask (買)", justify="right", style="red")
        table.add_column("Spread", justify="right")

        # Collect and sort
        entries = []
        for key, data in prices.items():
            spread = ((data["ask"] - data["bid"]) / data["bid"]) * 100 if data["bid"] > 0 else 0
            entries.append((data, spread))

        entries.sort(key=lambda x: x[0]["ask"])  # Sort by ask price

        min_ask = min(d["ask"] for d, _ in entries)
        max_bid = max(d["bid"] for d, _ in entries)

        for data, spread in entries:
            name = data["exchange"].upper()
            mtype = data["market_type"]
            bid = data["bid"]
            ask = data["ask"]

            # Highlight best buy (lowest ask) and best sell (highest bid)
            ask_str = f"[bold green]{ask:.6g} ⬅ BUY[/bold green]" if ask == min_ask else f"{ask:.6g}"
            bid_str = f"[bold red]{bid:.6g} ⬅ SELL[/bold red]" if bid == max_bid else f"{bid:.6g}"

            table.add_row(name, mtype, bid_str, ask_str, f"{spread:.4f}%")

        # Cross-exchange spread
        if max_bid > min_ask:
            cross_spread = ((max_bid - min_ask) / min_ask) * 100
            buy_fee = 0.001  # worst case
            sell_fee = 0.002  # worst case (gateio)
            net = cross_spread - (buy_fee + sell_fee) * 100
            color = "green" if net > 0 else "red"
            table.add_row(
                "", "", "", "",
                f"[bold {color}]Cross: {cross_spread:.4f}% (Net: {net:.4f}%)[/bold {color}]",
                style="on grey15",
            )
        else:
            reverse_spread = ((min_ask - max_bid) / max_bid) * 100
            table.add_row(
                "", "", "", "",
                f"[dim]No arb (gap: -{reverse_spread:.4f}%)[/dim]",
                style="on grey15",
            )

        console.print(table)
        console.print()


if __name__ == "__main__":
    main()
