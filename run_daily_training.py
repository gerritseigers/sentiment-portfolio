#!/usr/bin/env python3
"""
Run daily training with real ETF price data from Feb 5, 2026
Data sourced from stockanalysis.com and CoinGecko API
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daily_learning import daily_learn, generate_learning_report

# Real price changes for Feb 5, 2026 (sourced from stockanalysis.com)
price_changes = {
    "XLK":    -1.80,   # Technology
    "XLV":    -0.76,   # Healthcare
    "XLF":    -1.24,   # Financials
    "XLY":    -2.16,   # Consumer Discretionary
    "XLP":    -0.08,   # Consumer Staples
    "XLE":    -1.17,   # Energy
    "ICLN":   -3.36,   # Clean Energy
    "XLI":    -0.60,   # Industrials
    "XLB":    -2.68,   # Materials
    "XLU":    +0.05,   # Utilities
    "XLRE":   -0.55,   # Real Estate
    "XLC":    -0.51,   # Communication Services
    "CRYPTO": -12.59,  # Bitcoin/Crypto (from CoinGecko: BTC at $63,764)
}

print("=" * 70)
print(f"📊 REAL MARKET DATA - {datetime.now().strftime('%Y-%m-%d')}")
print("=" * 70)
print("\nSector ETF Performance:")
for etf, change in sorted(price_changes.items(), key=lambda x: x[1]):
    emoji = "🟢" if change > 0 else ("🔴" if change < -1 else "🟡")
    print(f"  {emoji} {etf:8} {change:+.2f}%")

print(f"\nMarket summary: Broad selloff, only XLU barely green (+0.05%)")
print(f"Biggest losers: CRYPTO (-12.59%), ICLN (-3.36%), XLB (-2.68%)")
print()

# Run the actual learning with real data
learning_result = daily_learn(price_changes=price_changes)

print("\n" + "=" * 70)
print("LEARNING REPORT:")
print("=" * 70)
report = generate_learning_report()
print(report)

# Save the training results
if learning_result:
    training_log = {
        "date": datetime.now().isoformat(),
        "real_price_data": price_changes,
        "data_sources": {
            "etf_prices": "stockanalysis.com (Feb 5, 2026 close)",
            "crypto": "CoinGecko API (BTC $63,764, -12.59% 24h)"
        },
        "market_summary": "Broad selloff across all sectors. Bitcoin crash below $70K. Only Utilities barely positive.",
        "learning_result": learning_result
    }
    
    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', f'training_report_{datetime.now().strftime("%Y-%m-%d")}.json')
    with open(report_path, 'w') as f:
        json.dump(training_log, f, indent=2, default=str)
    print(f"\n✅ Training report saved to: {report_path}")
