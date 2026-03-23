"""
Dashboard — ターミナルダッシュボード（richライブラリ使用）
"""

from __future__ import annotations

import logging
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich import box

import config

log = logging.getLogger("arb.dashboard")
console = Console()


def print_banner():
    """Print startup banner."""
    banner = """
╔═══════════════════════════════════════════════════╗
║     CEX Arbitrage Scanner v1.0                    ║
║     6取引所対応（MEXC/Bitget/LBank/KuCoin/       ║
║                  BingX/Gate.io）                   ║
╚═══════════════════════════════════════════════════╝
"""
    console.print(banner, style="bold cyan")
    console.print(f"  Mode: [bold {'green' if config.TRADE_MODE == 'dry_run' else 'red'}]"
                  f"{config.TRADE_MODE.upper()}[/]")
    console.print(f"  Min Profit: [bold]{config.MIN_PROFIT_PCT}%[/]")
    console.print(f"  Max Trade: [bold]${config.MAX_TRADE_USDT}[/]")
    console.print(f"  Market Type: [bold]{config.MARKET_TYPE}[/]")
    console.print()


def print_balances(balances: dict[str, dict]):
    """Print balance table for all exchanges."""
    table = Table(
        title="💰 取引所残高",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("取引所", style="bold")
    table.add_column("Free (USDT)", justify="right")
    table.add_column("Used (USDT)", justify="right")
    table.add_column("Total (USDT)", justify="right", style="bold green")
    table.add_column("Status")

    total_all = 0.0
    for name, bal in balances.items():
        error = bal.get("error", "")
        free = bal["free"]
        used = bal["used"]
        total = bal["total"]
        total_all += total

        status = "[red]❌ " + error[:30] if error else "[green]✅"
        table.add_row(
            name.upper(),
            f"{free:,.2f}",
            f"{used:,.2f}",
            f"{total:,.2f}",
            status,
        )

    table.add_row(
        "[bold]TOTAL[/]", "", "",
        f"[bold yellow]{total_all:,.2f}[/]", "",
        style="on grey15",
    )
    console.print(table)
    console.print()


def print_connections(results: dict[str, bool]):
    """Print connection test results."""
    table = Table(
        title="🔌 接続テスト",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("取引所", style="bold")
    table.add_column("Status", justify="center")

    for name, ok in results.items():
        status = "[green]✅ OK[/]" if ok else "[red]❌ FAIL[/]"
        table.add_row(name.upper(), status)

    console.print(table)
    console.print()


def print_opportunities(opps: list, max_show: int = 10):
    """Print opportunity table."""
    if not opps:
        console.print("[dim]  機会なし[/dim]")
        return

    table = Table(
        title=f"💹 アービトラージ機会 TOP {min(len(opps), max_show)}",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("ペア", style="bold")
    table.add_column("BUY", style="green")
    table.add_column("Buy価格", justify="right")
    table.add_column("SELL", style="red")
    table.add_column("Sell価格", justify="right")
    table.add_column("Spread%", justify="right")
    table.add_column("Net%", justify="right", style="bold yellow")
    table.add_column("利益($)", justify="right", style="bold green")

    for opp in opps[:max_show]:
        spread_color = "green" if opp.net_profit_pct >= 0.5 else "yellow"
        table.add_row(
            opp.symbol,
            f"{opp.buy_exchange.upper()}\n({opp.buy_market_type})",
            f"{opp.buy_price:.6g}",
            f"{opp.sell_exchange.upper()}\n({opp.sell_market_type})",
            f"{opp.sell_price:.6g}",
            f"{opp.spread_pct:.3f}%",
            f"[{spread_color}]{opp.net_profit_pct:.3f}%[/{spread_color}]",
            f"${opp.net_profit_usdt:.2f}",
        )

    console.print(table)
    console.print()


def print_scan_stats(scanner_stats: dict, executor_stats: dict):
    """Print scan statistics."""
    now = datetime.now().strftime("%H:%M:%S")
    stats_text = (
        f"[bold]📊 スキャン統計[/bold] ({now})\n"
        f"  Scans: {scanner_stats.get('scans', 0)} | "
        f"Opps found: {scanner_stats.get('opportunities', 0)} | "
        f"Best spread: {scanner_stats.get('best_spread', 0):.3f}%\n"
        f"  Trades: {executor_stats.get('trades', 0)} | "
        f"Win rate: {executor_stats.get('win_rate', 0):.1f}% | "
        f"Total P&L: ${executor_stats.get('total_profit', 0):.2f}"
    )
    console.print(Panel(stats_text, border_style="cyan"))
