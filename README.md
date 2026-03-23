# CEX Arbitrage Scanner

6取引所（MEXC, Bitget, LBank, KuCoin, BingX, Gate.io）対応のCEXアービトラージBot。

## 機能

- 🔍 6取引所の価格を同時スキャン（5秒間隔）
- 💰 手数料・スリッページ込みのネット利益自動計算
- 📱 Telegram通知（機会発見・取引結果・日次サマリー）
- 🤖 3モード対応（dry_run / manual / auto）
- 📊 現物（Spot）＋先物（Perpetuals）同時監視
- 📈 ターミナルダッシュボード（richベース）

## セットアップ

```bash
pip install -r requirements.txt
cp .env.example .env
# .env にAPIキー・Telegramトークンを設定
```

## 使い方

```bash
python main.py help      # 使い方を見る
python main.py test      # 6取引所 接続テスト
python main.py balance   # 全取引所残高確認
python main.py scan      # スキャン開始（dry_runモード）
python main.py auto      # 全自動トレード（要注意！）
```

## 対応取引所

| 取引所 | Taker手数料 |
|--------|------------|
| MEXC | 0.05% |
| Bitget | 0.10% |
| KuCoin | 0.10% |
| LBank | 0.10% |
| BingX | 0.10% |
| Gate.io | 0.20% |

## ⚠️ 注意事項

- 利益保証なし（市場変動・スリッページで損失の可能性あり）
- 初回はdry_runモード必須
- API権限は読取り+取引のみ（出金権限は絶対につけない）
- 日本居住者は雑所得として確定申告必須
- 全て自己責任
