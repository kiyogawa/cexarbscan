"""
CEX Arbitrage Bot — Configuration
6取引所対応（MEXC, Bitget, LBank, KuCoin, BingX, Gate.io）
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# Exchange API Keys
# ─────────────────────────────────────────────

EXCHANGES = {
    "mexc": {
        "apiKey": os.getenv("MEXC_API_KEY", ""),
        "secret": os.getenv("MEXC_API_SECRET", ""),
    },
    "bitget": {
        "apiKey": os.getenv("BITGET_API_KEY", ""),
        "secret": os.getenv("BITGET_API_SECRET", ""),
        "password": os.getenv("BITGET_PASSPHRASE", ""),
    },
    "lbank": {
        "apiKey": os.getenv("LBANK_API_KEY", ""),
        "secret": os.getenv("LBANK_API_SECRET", ""),
    },
    "kucoin": {
        "apiKey": os.getenv("KUCOIN_API_KEY", ""),
        "secret": os.getenv("KUCOIN_API_SECRET", ""),
        "password": os.getenv("KUCOIN_PASSPHRASE", ""),
    },
    "bingx": {
        "apiKey": os.getenv("BINGX_API_KEY", ""),
        "secret": os.getenv("BINGX_API_SECRET", ""),
    },
    "gateio": {
        "apiKey": os.getenv("GATEIO_API_KEY", ""),
        "secret": os.getenv("GATEIO_API_SECRET", ""),
    },
}

# ─────────────────────────────────────────────
# Trading Parameters
# ─────────────────────────────────────────────

# トレードモード: dry_run / manual / auto
TRADE_MODE = os.getenv("TRADE_MODE", "dry_run")

# 最小ネット利益率（手数料引き後）— これ以下は無視
MIN_PROFIT_PCT = 0.3

# 1回あたり最大取引額（USDT）
MAX_TRADE_USDT = 200.0

# 最小取引額（USDT）
MIN_TRADE_USDT = 10.0

# スキャン間隔（秒）
SCAN_INTERVAL = 5

# 板の深さ確認: 最低流動性（USDT）
MIN_ORDERBOOK_DEPTH_USDT = 500.0

# スリッページ許容（%）
MAX_SLIPPAGE_PCT = 0.5

# ─────────────────────────────────────────────
# Market Type — spot / futures / both
# ─────────────────────────────────────────────

# スキャン対象: "spot", "futures", "both"
MARKET_TYPE = "both"

# ─────────────────────────────────────────────
# Exchange Fee Rates (Taker)
# ─────────────────────────────────────────────

TAKER_FEES = {
    "mexc": 0.0005,       # 0.05%
    "bitget": 0.001,      # 0.10%
    "lbank": 0.001,       # 0.10%
    "kucoin": 0.001,      # 0.10%
    "bingx": 0.001,       # 0.10%
    "gateio": 0.002,      # 0.20%
}

# ─────────────────────────────────────────────
# Watch / Blacklist
# ─────────────────────────────────────────────

# 監視対象ペア（空ならUSDT建て全ペアを自動検出）
WATCHLIST = []

# 除外ペア（ステーブルコイン等）
BLACKLIST = [
    "USDC", "BUSD", "DAI", "TUSD", "USDP", "FDUSD",
    "USDD", "PYUSD", "EURI",
]

# ─────────────────────────────────────────────
# Telegram
# ─────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ─────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────

LOG_LEVEL = "INFO"
LOG_DIR = "logs"
