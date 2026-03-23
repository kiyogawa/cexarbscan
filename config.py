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

# 監視対象ペア — ミームコイン＆新規上場特化（価格差が出やすい）
WATCHLIST = [
    # ── ミームコイン（流動性低め＝価格差大） ──
    "PEPE/USDT", "WIF/USDT", "BONK/USDT", "FLOKI/USDT", "SHIB/USDT",
    "DOGE/USDT", "MEME/USDT", "TURBO/USDT", "BRETT/USDT", "MOG/USDT",
    "POPCAT/USDT", "NEIRO/USDT", "MYRO/USDT", "BOME/USDT", "MEW/USDT",
    "PEOPLE/USDT", "BABYDOGE/USDT", "SATS/USDT", "RATS/USDT", "CAT/USDT",
    "ACT/USDT", "PNUT/USDT", "GOAT/USDT", "FARTCOIN/USDT", "SPX/USDT",
    "TRUMP/USDT", "PENGU/USDT", "AI16Z/USDT", "VIRTUAL/USDT",
    # ── 新興・小型（価格差出やすい） ──
    "SEI/USDT", "TIA/USDT", "JUP/USDT", "PYTH/USDT", "STRK/USDT",
    "W/USDT", "DYM/USDT", "MANTA/USDT", "ALT/USDT", "PIXEL/USDT",
    "PORTAL/USDT", "AEVO/USDT", "ETHFI/USDT", "ENA/USDT", "ONDO/USDT",
    "SAGA/USDT", "OMNI/USDT", "REZ/USDT", "BB/USDT", "ZRO/USDT",
    # ── AI関連（ボラ高い） ──
    "FET/USDT", "RENDER/USDT", "WLD/USDT", "ARKM/USDT", "TAO/USDT",
    "AKT/USDT", "IO/USDT", "TNSR/USDT",
    # ── ゲーム・NFT（板薄い） ──
    "GALA/USDT", "IMX/USDT", "BLUR/USDT", "JASMY/USDT", "CHZ/USDT",
]

# 除外ペア（ステーブルコイン等）
BLACKLIST = [
    "USDC", "BUSD", "DAI", "TUSD", "USDP", "FDUSD",
    "USDD", "PYUSD", "EURI",
    # 取引所間で同名別トークン（偽のアービトラージ）
    "NEIRO",
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
