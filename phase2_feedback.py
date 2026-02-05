#!/usr/bin/env python3
"""
Phase 2 Feedback Loop - Learns from refinement decisions.

Tracks:
- Every adjust/keep decision with allocations
- Actual price movements after X days
- Which decisions outperformed

Adjusts:
- Confidence thresholds
- Refinement prompt effectiveness
"""

import json
import os
import sys
from datetime import datetime, timedelta
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DECISIONS_FILE = os.path.join(BASE_DIR, "data/phase2_decisions.jsonl")
EVALUATIONS_FILE = os.path.join(BASE_DIR, "data/phase2_evaluations.jsonl")
FEEDBACK_CONFIG_FILE = os.path.join(BASE_DIR, "data/phase2_feedback_config.json")

# Default config
DEFAULT_CONFIG = {
    "min_confidence_threshold": 0.6,  # Only act on adjust if confidence >= this
    "evaluation_days": 3,  # Days to wait before evaluating
    "learning_rate": 0.05,  # How much to adjust threshold per evaluation
    "min_evaluations_for_learning": 5,  # Need this many evals before adjusting
    "version": 1
}


def load_config():
    """Load feedback configuration."""
    if os.path.exists(FEEDBACK_CONFIG_FILE):
        with open(FEEDBACK_CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Merge with defaults for any missing keys
            return {**DEFAULT_CONFIG, **config}
    return DEFAULT_CONFIG.copy()


def save_config(config):
    """Save feedback configuration."""
    os.makedirs(os.path.dirname(FEEDBACK_CONFIG_FILE), exist_ok=True)
    config["last_updated"] = datetime.now().isoformat()
    with open(FEEDBACK_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def log_decision(sector, sentiment, action, confidence, 
                 original_allocation, final_allocation, reasoning=""):
    """
    Log a Phase 2 decision for later evaluation.
    
    Args:
        sector: e.g., "XLK"
        sentiment: sentiment score (-1 to +1)
        action: "adjust" or "keep"
        confidence: model's confidence (0-1)
        original_allocation: dict of ticker -> weight from Phase 1
        final_allocation: dict of ticker -> weight after Phase 2
        reasoning: model's reasoning
    """
    decision = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "sector": sector,
        "sentiment": sentiment,
        "action": action,
        "confidence": confidence,
        "original_allocation": original_allocation,
        "final_allocation": final_allocation,
        "reasoning": reasoning,
        "evaluated": False
    }
    
    os.makedirs(os.path.dirname(DECISIONS_FILE), exist_ok=True)
    with open(DECISIONS_FILE, 'a') as f:
        f.write(json.dumps(decision) + "\n")
    
    return decision


def get_pending_evaluations(min_days=3):
    """Get decisions that are ready for evaluation."""
    if not os.path.exists(DECISIONS_FILE):
        return []
    
    cutoff = datetime.now() - timedelta(days=min_days)
    pending = []
    
    with open(DECISIONS_FILE, 'r') as f:
        for line in f:
            if line.strip():
                decision = json.loads(line)
                if not decision.get("evaluated", False):
                    decision_date = datetime.fromisoformat(decision["timestamp"])
                    if decision_date < cutoff:
                        pending.append(decision)
    
    return pending


def fetch_price_change(ticker, start_date, end_date):
    """
    Fetch price change for a ticker between two dates.
    Uses yfinance if available, otherwise returns None.
    """
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date)
        if len(hist) >= 2:
            start_price = hist['Close'].iloc[0]
            end_price = hist['Close'].iloc[-1]
            return (end_price - start_price) / start_price
    except ImportError:
        print("yfinance not installed - using mock data")
        # Return mock data for testing
        import random
        return random.uniform(-0.05, 0.05)
    except Exception as e:
        print(f"Error fetching {ticker}: {e}")
    return None


def calculate_portfolio_return(allocation, start_date, end_date):
    """Calculate weighted portfolio return."""
    total_return = 0
    total_weight = 0
    
    for ticker, weight in allocation.items():
        change = fetch_price_change(ticker, start_date, end_date)
        if change is not None:
            total_return += change * weight
            total_weight += weight
    
    if total_weight > 0:
        return total_return / total_weight * 100  # Return as percentage
    return None


def evaluate_decision(decision, days=3):
    """
    Evaluate a single decision by comparing actual performance.
    
    Returns dict with:
    - original_return: what Phase 1 allocation would have made
    - final_return: what Phase 2 allocation actually made
    - outperformed: bool, did Phase 2 beat Phase 1?
    - delta: difference in returns
    """
    start_date = decision["date"]
    end_date = (datetime.strptime(start_date, "%Y-%m-%d") + timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Normalize allocations to weights (0-1)
    def normalize(alloc):
        total = sum(alloc.values())
        if total > 0:
            return {k: v/total for k, v in alloc.items()}
        return alloc
    
    original = normalize(decision["original_allocation"])
    final = normalize(decision["final_allocation"])
    
    original_return = calculate_portfolio_return(original, start_date, end_date)
    final_return = calculate_portfolio_return(final, start_date, end_date)
    
    if original_return is None or final_return is None:
        return None
    
    evaluation = {
        "decision_timestamp": decision["timestamp"],
        "evaluation_timestamp": datetime.now().isoformat(),
        "sector": decision["sector"],
        "action": decision["action"],
        "confidence": decision["confidence"],
        "original_return": round(original_return, 3),
        "final_return": round(final_return, 3),
        "delta": round(final_return - original_return, 3),
        "outperformed": final_return > original_return,
        "days_evaluated": days
    }
    
    # Log evaluation
    os.makedirs(os.path.dirname(EVALUATIONS_FILE), exist_ok=True)
    with open(EVALUATIONS_FILE, 'a') as f:
        f.write(json.dumps(evaluation) + "\n")
    
    return evaluation


def run_evaluations():
    """Evaluate all pending decisions."""
    config = load_config()
    pending = get_pending_evaluations(min_days=config["evaluation_days"])
    
    if not pending:
        print("No pending evaluations")
        return []
    
    print(f"Evaluating {len(pending)} decisions...")
    results = []
    
    for decision in pending:
        print(f"  {decision['sector']} ({decision['action']}, {decision['confidence']:.0%})...")
        result = evaluate_decision(decision, days=config["evaluation_days"])
        if result:
            results.append(result)
            marker = "✓" if result["outperformed"] else "✗"
            print(f"    {marker} Original: {result['original_return']:+.2f}% → Final: {result['final_return']:+.2f}% (Δ{result['delta']:+.2f}%)")
    
    # Mark decisions as evaluated
    mark_decisions_evaluated([d["timestamp"] for d in pending])
    
    return results


def mark_decisions_evaluated(timestamps):
    """Mark decisions as evaluated in the log file."""
    if not os.path.exists(DECISIONS_FILE):
        return
    
    timestamps_set = set(timestamps)
    lines = []
    
    with open(DECISIONS_FILE, 'r') as f:
        for line in f:
            if line.strip():
                decision = json.loads(line)
                if decision["timestamp"] in timestamps_set:
                    decision["evaluated"] = True
                lines.append(json.dumps(decision))
    
    with open(DECISIONS_FILE, 'w') as f:
        f.write("\n".join(lines) + "\n")


def get_performance_stats():
    """Calculate performance statistics for adjust vs keep decisions."""
    if not os.path.exists(EVALUATIONS_FILE):
        return None
    
    stats = {
        "adjust": {"count": 0, "outperformed": 0, "avg_delta": 0, "deltas": []},
        "keep": {"count": 0, "outperformed": 0, "avg_delta": 0, "deltas": []},
        "by_confidence": defaultdict(lambda: {"count": 0, "outperformed": 0, "deltas": []})
    }
    
    with open(EVALUATIONS_FILE, 'r') as f:
        for line in f:
            if line.strip():
                eval_data = json.loads(line)
                action = eval_data["action"]
                confidence = eval_data["confidence"]
                delta = eval_data["delta"]
                outperformed = eval_data["outperformed"]
                
                stats[action]["count"] += 1
                stats[action]["deltas"].append(delta)
                if outperformed:
                    stats[action]["outperformed"] += 1
                
                # Bucket confidence into ranges
                conf_bucket = f"{int(confidence * 10) * 10}%+"
                stats["by_confidence"][conf_bucket]["count"] += 1
                stats["by_confidence"][conf_bucket]["deltas"].append(delta)
                if outperformed:
                    stats["by_confidence"][conf_bucket]["outperformed"] += 1
    
    # Calculate averages
    for action in ["adjust", "keep"]:
        if stats[action]["deltas"]:
            stats[action]["avg_delta"] = sum(stats[action]["deltas"]) / len(stats[action]["deltas"])
            stats[action]["win_rate"] = stats[action]["outperformed"] / stats[action]["count"]
    
    for bucket in stats["by_confidence"]:
        data = stats["by_confidence"][bucket]
        if data["deltas"]:
            data["avg_delta"] = sum(data["deltas"]) / len(data["deltas"])
            data["win_rate"] = data["outperformed"] / data["count"]
    
    return stats


def learn_from_evaluations():
    """
    Analyze evaluations and adjust confidence threshold if needed.
    
    Logic:
    - If high-confidence adjusts consistently outperform → lower threshold (be more aggressive)
    - If high-confidence adjusts underperform → raise threshold (be more conservative)
    """
    config = load_config()
    stats = get_performance_stats()
    
    if not stats:
        print("No evaluation data yet")
        return config
    
    adjust_stats = stats["adjust"]
    
    if adjust_stats["count"] < config["min_evaluations_for_learning"]:
        print(f"Need {config['min_evaluations_for_learning']} evaluations, have {adjust_stats['count']}")
        return config
    
    print(f"\nLearning from {adjust_stats['count']} 'adjust' decisions:")
    print(f"  Win rate: {adjust_stats.get('win_rate', 0):.1%}")
    print(f"  Avg delta: {adjust_stats.get('avg_delta', 0):+.2f}%")
    
    old_threshold = config["min_confidence_threshold"]
    
    # If adjust decisions are working well (>60% win rate, positive delta)
    if adjust_stats.get("win_rate", 0) > 0.6 and adjust_stats.get("avg_delta", 0) > 0:
        # Lower threshold to be more aggressive
        config["min_confidence_threshold"] = max(0.4, old_threshold - config["learning_rate"])
        print(f"  → Lowering threshold: {old_threshold:.0%} → {config['min_confidence_threshold']:.0%}")
    
    # If adjust decisions are not working (<40% win rate or negative delta)
    elif adjust_stats.get("win_rate", 0) < 0.4 or adjust_stats.get("avg_delta", 0) < -0.5:
        # Raise threshold to be more conservative
        config["min_confidence_threshold"] = min(0.9, old_threshold + config["learning_rate"])
        print(f"  → Raising threshold: {old_threshold:.0%} → {config['min_confidence_threshold']:.0%}")
    
    else:
        print(f"  → Keeping threshold at {old_threshold:.0%}")
    
    save_config(config)
    return config


def should_apply_adjustment(confidence):
    """
    Check if a Phase 2 adjustment should be applied based on learned thresholds.
    
    Args:
        confidence: The model's confidence in the adjustment (0-1)
    
    Returns:
        bool: True if adjustment should be applied
    """
    config = load_config()
    return confidence >= config["min_confidence_threshold"]


def print_status():
    """Print current feedback system status."""
    config = load_config()
    stats = get_performance_stats()
    
    print("=" * 50)
    print("PHASE 2 FEEDBACK SYSTEM STATUS")
    print("=" * 50)
    
    print(f"\nConfig:")
    print(f"  Confidence threshold: {config['min_confidence_threshold']:.0%}")
    print(f"  Evaluation period: {config['evaluation_days']} days")
    print(f"  Learning rate: {config['learning_rate']}")
    
    if stats:
        print(f"\nPerformance Stats:")
        for action in ["adjust", "keep"]:
            s = stats[action]
            if s["count"] > 0:
                print(f"\n  {action.upper()} decisions ({s['count']} total):")
                print(f"    Win rate: {s.get('win_rate', 0):.1%}")
                print(f"    Avg delta: {s.get('avg_delta', 0):+.2f}%")
        
        print(f"\n  By Confidence Level:")
        for bucket in sorted(stats["by_confidence"].keys()):
            data = stats["by_confidence"][bucket]
            if data["count"] > 0:
                print(f"    {bucket}: {data['count']} decisions, {data.get('win_rate', 0):.0%} win rate")
    else:
        print("\n  No evaluation data yet")
    
    # Pending evaluations
    pending = get_pending_evaluations(min_days=0)
    evaluated = len([1 for p in pending if p.get("evaluated")])
    print(f"\n  Decisions logged: {len(pending)} ({evaluated} evaluated)")


# CLI
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Phase 2 Feedback System")
        print("\nUsage: python3 phase2_feedback.py <command>")
        print("\nCommands:")
        print("  status    - Show current status and stats")
        print("  evaluate  - Run pending evaluations")
        print("  learn     - Learn from evaluations and adjust thresholds")
        print("  reset     - Reset config to defaults")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        print_status()
    
    elif cmd == "evaluate":
        results = run_evaluations()
        if results:
            wins = sum(1 for r in results if r["outperformed"])
            print(f"\nSummary: {wins}/{len(results)} outperformed")
    
    elif cmd == "learn":
        learn_from_evaluations()
    
    elif cmd == "reset":
        save_config(DEFAULT_CONFIG)
        print("Config reset to defaults")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
