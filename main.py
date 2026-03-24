"""
CEX Arbitrage Bot — Main Entry Point
6取引所対応（MEXC, Bitget, LBank, KuCoin, BingX, Gate.io）

Usage:
    python main.py test      # 接続テスト
    python main.py balance   # 全取引所残高確認
    python main.py scan      # スキャン開始（dry_runデフォルト）
    python main.py auto      # 全自動トレード
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime

import config
from exchanges.manager import ExchangeManager
from scanner import Scanner
from executor import Executor
import dashboard
import notifier

# ──────────────────────────────────────────────
# Logging setup
# ──────────────────────────────────────────────

os.makedirs(config.LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(config.LOG_DIR,
                         f"arb_{datetime.now():%Y%m%d}.log"),
            encoding="utf-8",
        ),
    ],
)

log = logging.getLogger("arb.main")


# ──────────────────────────────────────────────
# Commands
# ──────────────────────────────────────────────

def cmd_test():
    """Test connections to all exchanges."""
    dashboard.print_banner()
    log.info("🔌 接続テスト開始...")

    mgr = ExchangeManager()
    results = mgr.test_connections()
    dashboard.print_connections(results)

    ok = sum(1 for v in results.values() if v)
    total = len(results)
    log.info("接続結果: %d/%d 成功", ok, total)

    if ok == 0:
        log.error("❌ すべての取引所に接続できません。APIキーを確認してください。")
        sys.exit(1)


def cmd_balance():
    """Show balances for all exchanges."""
    dashboard.print_banner()
    log.info("💰 残高取得中...")

    mgr = ExchangeManager()
    mgr.load_all_markets()
    balances = mgr.get_all_balances()
    dashboard.print_balances(balances)


def cmd_scan():
    """Run the scanner in current TRADE_MODE (default: dry_run)."""
    dashboard.print_banner()
    log.info("🚀 スキャンモード: %s", config.TRADE_MODE)

    mgr = ExchangeManager()
    scanner = Scanner(mgr)
    executor = Executor(mgr)

    scanner.init()

    log.info("📊 %d 共通ペアを %d 取引所で監視開始",
             len(scanner.common_symbols), len(mgr.get_active_exchanges()))

    def on_opportunities(opps):
        """Callback when opportunities are found."""
        dashboard.print_opportunities(opps)

        # Execute top opportunity
        if opps:
            best = opps[0]
            executor.execute(best)

        # Check open positions for auto-close
        executor.positions.check_and_close()

        # Show stats periodically
        if scanner.stats["scans"] % 12 == 0:
            dashboard.print_scan_stats(scanner.stats, executor.get_stats())
            open_cnt = executor.positions.get_open_count()
            if open_cnt > 0:
                log.info(executor.positions.get_summary())

    scanner.run_loop(callback=on_opportunities)


def cmd_transfer():
    """Transfer 50% of spot USDT to futures account on each exchange."""
    dashboard.print_banner()
    log.info("🔄 現物→先物 USDT振替開始...")

    # Exchanges that support futures
    FUTURES_EXCHANGES = ["mexc", "bitget", "bingx", "gateio", "kucoin"]

    mgr = ExchangeManager()
    mgr.load_all_markets()

    for name in FUTURES_EXCHANGES:
        ex = mgr.exchanges.get(name)
        if not ex:
            continue
        try:
            bal = ex.fetch_balance()
            usdt_free = float(bal.get("USDT", {}).get("free", 0))
            transfer_amount = round(usdt_free * 0.5, 2)

            if transfer_amount < 5:
                log.info("⏭️  %s: USDT残高少ない($%.2f) — スキップ",
                         name.upper(), usdt_free)
                continue

            log.info("🔄 %s: $%.2f → 先物口座へ振替中...", name.upper(), transfer_amount)
            ex.transfer("USDT", transfer_amount, "spot", "swap")
            log.info("✅ %s: $%.2f 振替完了！", name.upper(), transfer_amount)

        except Exception as e:
            log.error("❌ %s: 振替失敗 — %s", name.upper(), e)

    log.info("💰 振替後の残高を確認中...")
    balances = mgr.get_all_balances()
    dashboard.print_balances(balances)


def cmd_auto():
    """Run in auto-execute mode."""
    config.TRADE_MODE = "auto"
    log.warning("⚠️  全自動モードで起動します！実際の取引が実行されます！")
    log.warning("⚠️  5秒後に開始... Ctrl+C でキャンセル")

    import time
    for i in range(5, 0, -1):
        log.warning("  %d...", i)
        time.sleep(1)

    cmd_scan()


def cmd_help():
    """Show help."""
    dashboard.print_banner()
    help_text = """
使い方:
    python main.py test      🔌 接続テスト（全6取引所）
    python main.py balance   💰 全取引所残高確認
    python main.py scan      🔍 スキャン開始（dry_runモード）
    python main.py auto      ⚡ 全自動トレード（要注意！）

設定:
    .env ファイルにAPIキーを設定してください

Telegram Bot作成手順:
    1. @BotFather に話しかける（Telegram内で検索）
    2. /newbot と送信
    3. Bot名を入力（例: MyArbBot）
    4. ユーザー名を入力（例: my_arb_scanner_bot）
    5. 表示されたTokenを .env の TELEGRAM_BOT_TOKEN に貼り付け
    6. @userinfobot に話しかけて自分のChat IDを取得
    7. Chat IDを .env の TELEGRAM_CHAT_ID に貼り付け
"""
    print(help_text)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

COMMANDS = {
    "test": cmd_test,
    "balance": cmd_balance,
    "scan": cmd_scan,
    "auto": cmd_auto,
    "transfer": cmd_transfer,
    "help": cmd_help,
}


def main():
    if len(sys.argv) < 2:
        cmd_help()
        return

    cmd_name = sys.argv[1].lower()
    cmd_func = COMMANDS.get(cmd_name)

    if cmd_func is None:
        log.error("不明なコマンド: %s", cmd_name)
        cmd_help()
        sys.exit(1)

    cmd_func()


if __name__ == "__main__":
    main()
