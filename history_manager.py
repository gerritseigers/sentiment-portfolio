#!/usr/bin/env python3
"""
History Manager - Preserves all trading data over time.

Maintains:
- Daily portfolio snapshots
- Performance history
- Sentiment history per sector
- Decision history
- Learning progress
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
HISTORY_DIR = os.path.join(DATA_DIR, "history")

# History files
PORTFOLIO_HISTORY = os.path.join(HISTORY_DIR, "portfolio_snapshots.jsonl")
PERFORMANCE_HISTORY = os.path.join(HISTORY_DIR, "performance_daily.jsonl")
SENTIMENT_HISTORY = os.path.join(HISTORY_DIR, "sentiment_daily.jsonl")
TRADE_HISTORY = os.path.join(HISTORY_DIR, "trades.jsonl")
LEARNING_HISTORY = os.path.join(HISTORY_DIR, "learning_progress.jsonl")


def ensure_dirs():
    """Create history directories if needed."""
    os.makedirs(HISTORY_DIR, exist_ok=True)


def append_jsonl(path: str, data: dict):
    """Append a record to a JSONL file."""
    ensure_dirs()
    with open(path, 'a') as f:
        f.write(json.dumps(data) + "\n")


def read_jsonl(path: str, days: int = None) -> List[dict]:
    """Read records from JSONL, optionally filtered by days."""
    if not os.path.exists(path):
        return []
    
    records = []
    cutoff = None
    if days:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    with open(path, 'r') as f:
        for line in f:
            if line.strip():
                record = json.loads(line)
                if cutoff and record.get("date", record.get("timestamp", "")) < cutoff:
                    continue
                records.append(record)
    return records


# =============================================================================
# Portfolio Snapshots
# =============================================================================

def save_portfolio_snapshot(scenario: str, holdings: Dict[str, dict], total_value: float, 
                           cash: float = 0, notes: str = ""):
    """
    Save a daily portfolio snapshot.
    
    Args:
        scenario: e.g., "benchmark", "momentum"
        holdings: {ticker: {shares, value, weight, avg_cost}}
        total_value: Total portfolio value
        cash: Cash position
        notes: Any notes
    """
    snapshot = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "scenario": scenario,
        "total_value": total_value,
        "cash": cash,
        "holdings_count": len(holdings),
        "holdings": holdings,
        "notes": notes
    }
    append_jsonl(PORTFOLIO_HISTORY, snapshot)
    return snapshot


def get_portfolio_history(scenario: str = None, days: int = 30) -> List[dict]:
    """Get portfolio snapshots, optionally filtered by scenario."""
    records = read_jsonl(PORTFOLIO_HISTORY, days=days)
    if scenario:
        records = [r for r in records if r.get("scenario") == scenario]
    return records


# =============================================================================
# Performance History
# =============================================================================

def save_daily_performance(scenario: str, date: str, start_value: float, end_value: float,
                          benchmark_return: float = None, sectors_performance: dict = None):
    """
    Save daily performance metrics.
    
    Args:
        scenario: Trading scenario
        date: Date string YYYY-MM-DD
        start_value: Portfolio value at start of day
        end_value: Portfolio value at end of day
        benchmark_return: SPY return for comparison
        sectors_performance: {sector: return_pct}
    """
    daily_return = (end_value - start_value) / start_value * 100 if start_value > 0 else 0
    
    record = {
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "scenario": scenario,
        "start_value": start_value,
        "end_value": end_value,
        "daily_return_pct": round(daily_return, 3),
        "benchmark_return_pct": benchmark_return,
        "alpha": round(daily_return - (benchmark_return or 0), 3) if benchmark_return else None,
        "sectors": sectors_performance
    }
    append_jsonl(PERFORMANCE_HISTORY, record)
    return record


def get_performance_history(scenario: str = None, days: int = 30) -> List[dict]:
    """Get performance history."""
    records = read_jsonl(PERFORMANCE_HISTORY, days=days)
    if scenario:
        records = [r for r in records if r.get("scenario") == scenario]
    return records


def calculate_cumulative_returns(scenario: str = None, days: int = 30) -> dict:
    """Calculate cumulative returns over period."""
    records = get_performance_history(scenario, days)
    if not records:
        return {"total_return": 0, "days": 0, "avg_daily": 0}
    
    total_return = 1.0
    for r in records:
        total_return *= (1 + r.get("daily_return_pct", 0) / 100)
    
    total_return_pct = (total_return - 1) * 100
    
    return {
        "total_return_pct": round(total_return_pct, 2),
        "days": len(records),
        "avg_daily_pct": round(total_return_pct / len(records), 3) if records else 0,
        "best_day": max(r.get("daily_return_pct", 0) for r in records) if records else 0,
        "worst_day": min(r.get("daily_return_pct", 0) for r in records) if records else 0
    }


# =============================================================================
# Sentiment History
# =============================================================================

def save_daily_sentiment(date: str, sector_sentiments: Dict[str, float], 
                        overall_sentiment: float = None, news_count: int = 0):
    """
    Save daily sentiment readings.
    
    Args:
        date: Date string
        sector_sentiments: {sector: sentiment_score}
        overall_sentiment: Weighted average
        news_count: Number of news items analyzed
    """
    if overall_sentiment is None and sector_sentiments:
        overall_sentiment = sum(sector_sentiments.values()) / len(sector_sentiments)
    
    record = {
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "overall": round(overall_sentiment or 0, 3),
        "news_count": news_count,
        "sectors": {k: round(v, 3) for k, v in sector_sentiments.items()}
    }
    append_jsonl(SENTIMENT_HISTORY, record)
    return record


def get_sentiment_history(sector: str = None, days: int = 30) -> List[dict]:
    """Get sentiment history."""
    records = read_jsonl(SENTIMENT_HISTORY, days=days)
    if sector:
        # Filter to just the requested sector's data
        for r in records:
            if "sectors" in r and sector in r["sectors"]:
                r["sentiment"] = r["sectors"][sector]
    return records


def get_sentiment_trend(sector: str, days: int = 7) -> dict:
    """Calculate sentiment trend for a sector."""
    records = get_sentiment_history(sector, days)
    if len(records) < 2:
        return {"trend": "unknown", "change": 0}
    
    sentiments = [r["sectors"].get(sector, 0) for r in records if "sectors" in r]
    if len(sentiments) < 2:
        return {"trend": "unknown", "change": 0}
    
    recent = sum(sentiments[-3:]) / min(3, len(sentiments))
    older = sum(sentiments[:3]) / min(3, len(sentiments))
    change = recent - older
    
    trend = "improving" if change > 0.1 else ("declining" if change < -0.1 else "stable")
    
    return {
        "trend": trend,
        "change": round(change, 3),
        "current": round(sentiments[-1], 3) if sentiments else 0,
        "avg_7d": round(sum(sentiments) / len(sentiments), 3) if sentiments else 0
    }


# =============================================================================
# Trade History
# =============================================================================

def save_trade(scenario: str, action: str, ticker: str, shares: float, price: float,
              reason: str = "", sentiment: float = None):
    """
    Save a trade execution.
    
    Args:
        scenario: Trading scenario
        action: "buy" or "sell"
        ticker: Stock ticker
        shares: Number of shares
        price: Execution price
        reason: Why this trade
        sentiment: Sentiment at time of trade
    """
    trade = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "scenario": scenario,
        "action": action,
        "ticker": ticker,
        "shares": shares,
        "price": price,
        "value": round(shares * price, 2),
        "reason": reason,
        "sentiment_at_trade": sentiment
    }
    append_jsonl(TRADE_HISTORY, trade)
    return trade


def get_trade_history(scenario: str = None, ticker: str = None, days: int = 30) -> List[dict]:
    """Get trade history with optional filters."""
    records = read_jsonl(TRADE_HISTORY, days=days)
    if scenario:
        records = [r for r in records if r.get("scenario") == scenario]
    if ticker:
        records = [r for r in records if r.get("ticker") == ticker]
    return records


# =============================================================================
# Learning Progress
# =============================================================================

def save_learning_progress(embeddings_count: int, knowledge_topics: int, 
                          prompt_accuracy: float = None, decisions_evaluated: int = 0,
                          win_rate: float = None):
    """
    Save learning progress snapshot.
    """
    record = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "embeddings_count": embeddings_count,
        "knowledge_topics": knowledge_topics,
        "prompt_accuracy": prompt_accuracy,
        "decisions_evaluated": decisions_evaluated,
        "win_rate": win_rate
    }
    append_jsonl(LEARNING_HISTORY, record)
    return record


def get_learning_progress(days: int = 30) -> List[dict]:
    """Get learning progress history."""
    return read_jsonl(LEARNING_HISTORY, days=days)


# =============================================================================
# Summary Reports
# =============================================================================

def generate_history_summary(days: int = 7) -> dict:
    """Generate a summary of all history."""
    summary = {
        "period_days": days,
        "generated": datetime.now().isoformat()
    }
    
    # Performance
    perf = get_performance_history(days=days)
    if perf:
        scenarios = set(r.get("scenario") for r in perf)
        summary["performance"] = {
            s: calculate_cumulative_returns(s, days) for s in scenarios
        }
    
    # Sentiment
    sent = get_sentiment_history(days=days)
    if sent:
        summary["sentiment"] = {
            "readings": len(sent),
            "latest": sent[-1] if sent else None
        }
    
    # Trades
    trades = get_trade_history(days=days)
    if trades:
        summary["trades"] = {
            "count": len(trades),
            "buys": len([t for t in trades if t.get("action") == "buy"]),
            "sells": len([t for t in trades if t.get("action") == "sell"]),
            "total_value": sum(t.get("value", 0) for t in trades)
        }
    
    # Learning
    learning = get_learning_progress(days=days)
    if learning:
        latest = learning[-1]
        summary["learning"] = {
            "embeddings": latest.get("embeddings_count", 0),
            "knowledge_topics": latest.get("knowledge_topics", 0),
            "win_rate": latest.get("win_rate")
        }
    
    return summary


def print_history_report(days: int = 7):
    """Print a formatted history report."""
    summary = generate_history_summary(days)
    
    print("=" * 50)
    print(f"HISTORY REPORT - Last {days} days")
    print("=" * 50)
    
    if "performance" in summary:
        print("\n📈 Performance:")
        for scenario, perf in summary["performance"].items():
            print(f"  {scenario}: {perf['total_return_pct']:+.2f}% ({perf['days']} days)")
    
    if "sentiment" in summary:
        print(f"\n📊 Sentiment: {summary['sentiment']['readings']} readings")
        if summary['sentiment']['latest']:
            print(f"  Latest overall: {summary['sentiment']['latest'].get('overall', 'N/A')}")
    
    if "trades" in summary:
        t = summary["trades"]
        print(f"\n💹 Trades: {t['count']} ({t['buys']} buys, {t['sells']} sells)")
        print(f"  Total value: ${t['total_value']:,.0f}")
    
    if "learning" in summary:
        l = summary["learning"]
        print(f"\n🧠 Learning:")
        print(f"  Embeddings: {l['embeddings']}")
        print(f"  Knowledge: {l['knowledge_topics']} topics")
        if l.get("win_rate"):
            print(f"  Win rate: {l['win_rate']:.1%}")


# CLI
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("History Manager")
        print("\nUsage: python3 history_manager.py <command>")
        print("\nCommands:")
        print("  report [days]  - Print history report (default 7 days)")
        print("  export [days]  - Export history as JSON")
        print("  stats          - Show file statistics")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "report":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
        print_history_report(days)
    
    elif cmd == "export":
        days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        summary = generate_history_summary(days)
        print(json.dumps(summary, indent=2))
    
    elif cmd == "stats":
        print("History Files:")
        for name, path in [
            ("Portfolio", PORTFOLIO_HISTORY),
            ("Performance", PERFORMANCE_HISTORY),
            ("Sentiment", SENTIMENT_HISTORY),
            ("Trades", TRADE_HISTORY),
            ("Learning", LEARNING_HISTORY)
        ]:
            if os.path.exists(path):
                records = read_jsonl(path)
                size = os.path.getsize(path)
                print(f"  {name}: {len(records)} records ({size/1024:.1f} KB)")
            else:
                print(f"  {name}: not yet created")
    
    else:
        print(f"Unknown command: {cmd}")
