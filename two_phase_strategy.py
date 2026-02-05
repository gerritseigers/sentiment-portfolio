#!/usr/bin/env python3
"""
Two-Phase Trading Strategy Orchestrator

Phase 1: Quick Reaction
  - Get current sentiment
  - Make immediate trading decisions (ollama_portfolio.py)
  - Execute trades

Phase 2: Refined Strategy  
  - Check for missing embeddings
  - Fetch missing company profiles
  - Refine allocations using embeddings + news context
  - Adjust positions if needed

This script orchestrates both phases in sequence.
"""

import json
import os
import sys
from datetime import datetime

# Import our modules
sys.path.insert(0, os.path.dirname(__file__))

from embedding_manager import (
    get_missing_embeddings, 
    fetch_missing_embeddings,
    get_company_context,
    get_embedding_stats
)
from refined_strategy import refine_allocation, get_refinement_summary

# Config
BASE_DIR = os.path.dirname(__file__)
SECTOR_ASSETS_FILE = os.path.join(BASE_DIR, "sector_assets.json")
SENTIMENT_CACHE = os.path.join(BASE_DIR, "data/sentiment_cache.json")
PORTFOLIO_STATE_FILE = os.path.join(BASE_DIR, "data/portfolio_state.json")
TWO_PHASE_LOG = os.path.join(BASE_DIR, "data/two_phase_log.jsonl")

# Maximum embeddings to fetch per run (to control time/API usage)
MAX_EMBEDDINGS_PER_RUN = 5


def load_json(filepath, default=None):
    """Load JSON file."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return default if default is not None else {}


def save_json(filepath, data):
    """Save JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)


def log_run(phase, data):
    """Log phase execution."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "phase": phase,
        **data
    }
    os.makedirs(os.path.dirname(TWO_PHASE_LOG), exist_ok=True)
    with open(TWO_PHASE_LOG, 'a') as f:
        f.write(json.dumps(entry) + "\n")


def get_current_sentiment():
    """Load current sector sentiment scores."""
    cache = load_json(SENTIMENT_CACHE, {})
    
    # Extract latest sentiment per sector
    sentiments = {}
    for sector, data in cache.items():
        if isinstance(data, dict) and "score" in data:
            sentiments[sector] = data["score"]
        elif isinstance(data, (int, float)):
            sentiments[sector] = data
    
    return sentiments


def get_phase1_allocations(scenario="benchmark"):
    """
    Get allocations from Phase 1 (quick sentiment-based decisions).
    This would typically come from ollama_portfolio.py output.
    """
    # Load portfolio state which should have recent allocations
    state = load_json(PORTFOLIO_STATE_FILE, {})
    scenario_state = state.get(scenario, {})
    
    return scenario_state.get("allocations", {})


def run_phase1(scenario="benchmark", dry_run=False):
    """
    Phase 1: Quick sentiment-based trading.
    Calls ollama_portfolio.py to make immediate decisions.
    """
    print("=" * 60)
    print("PHASE 1: Quick Sentiment-Based Trading")
    print("=" * 60)
    
    sentiments = get_current_sentiment()
    
    if not sentiments:
        print("No sentiment data available!")
        return None
    
    print(f"Loaded sentiment for {len(sentiments)} sectors")
    
    # In a real implementation, this would call ollama_portfolio.py
    # For now, we simulate/log what would happen
    
    from ollama_portfolio import select_assets_for_sector
    
    allocations = {}
    for sector, sentiment in sentiments.items():
        if abs(sentiment) < 0.1:  # Skip neutral sectors
            continue
            
        print(f"\n{sector}: sentiment={sentiment:+.2f}")
        
        # Determine stance
        if sentiment > 0.3:
            stance = "aggressive"
        elif sentiment > 0:
            stance = "moderate"
        elif sentiment > -0.3:
            stance = "defensive"
        else:
            stance = "very_defensive"
        
        # Get AI allocation
        result = select_assets_for_sector(sector, sentiment, stance)
        
        if result and result.get("allocation"):
            allocations[sector] = {
                "sentiment": sentiment,
                "stance": stance,
                "allocation": result["allocation"],
                "reasoning": result.get("reasoning", "")
            }
            print(f"  → {stance}: {result['allocation']}")
    
    log_run("phase1", {
        "scenario": scenario,
        "sectors_processed": len(allocations),
        "dry_run": dry_run
    })
    
    print(f"\nPhase 1 complete: {len(allocations)} sectors allocated")
    return allocations


def run_phase2(phase1_allocations, scenario="benchmark", dry_run=False):
    """
    Phase 2: Refined strategy with embeddings.
    
    1. Identify tickers from Phase 1 allocations
    2. Fetch any missing embeddings
    3. Refine allocations using company context
    """
    print("\n" + "=" * 60)
    print("PHASE 2: Refined Strategy with Embeddings")
    print("=" * 60)
    
    if not phase1_allocations:
        print("No Phase 1 allocations to refine!")
        return None
    
    # Step 1: Identify all tickers needing embeddings
    all_tickers = set()
    for sector_data in phase1_allocations.values():
        allocation = sector_data.get("allocation", {})
        all_tickers.update(allocation.keys())
    
    print(f"Total tickers in allocations: {len(all_tickers)}")
    
    # Step 2: Check and fetch missing embeddings
    missing, outdated = get_missing_embeddings(list(all_tickers))
    
    print(f"Missing embeddings: {len(missing)}")
    print(f"Outdated embeddings: {len(outdated)}")
    
    if missing or outdated:
        print(f"\nFetching up to {MAX_EMBEDDINGS_PER_RUN} embeddings...")
        fetched = fetch_missing_embeddings(
            list(all_tickers), 
            max_fetch=MAX_EMBEDDINGS_PER_RUN
        )
        print(f"Fetched {len(fetched)} new embeddings")
    
    # Step 3: Refine each sector allocation
    print("\nRefining allocations...")
    refinements = {}
    
    for sector, data in phase1_allocations.items():
        sentiment = data.get("sentiment", 0)
        allocation = data.get("allocation", {})
        
        if not allocation:
            continue
        
        print(f"\n{sector}:")
        result = refine_allocation(sector, sentiment, allocation, scenario)
        refinements[sector] = result
        
        action = result.get("action", "keep")
        confidence = result.get("confidence", 0)
        reasoning = result.get("reasoning", "")[:60]
        
        if action == "adjust":
            print(f"  ⚡ ADJUST (confidence: {confidence:.0%})")
            print(f"     {reasoning}...")
            
            # Show changes
            old = result.get("original_allocation", {})
            new = result.get("new_allocation", {})
            for ticker in set(old.keys()) | set(new.keys()):
                old_pct = old.get(ticker, 0)
                new_pct = new.get(ticker, 0)
                if abs(new_pct - old_pct) > 1:
                    print(f"     {ticker}: {old_pct}% → {new_pct}%")
        else:
            print(f"  ✓ KEEP (confidence: {confidence:.0%})")
    
    # Summary
    summary = get_refinement_summary(refinements)
    
    print("\n" + "-" * 40)
    print(f"Refinement Summary:")
    print(f"  Sectors analyzed: {summary['total_sectors']}")
    print(f"  Adjustments made: {summary['adjustments']}")
    print(f"  Kept as-is: {summary['kept_as_is']}")
    
    log_run("phase2", {
        "scenario": scenario,
        "sectors_refined": len(refinements),
        "adjustments": summary['adjustments'],
        "embeddings_fetched": len(missing) if missing else 0,
        "dry_run": dry_run
    })
    
    return refinements


def run_both_phases(scenario="benchmark", dry_run=False):
    """Run complete two-phase strategy."""
    print("\n" + "=" * 60)
    print(f"TWO-PHASE STRATEGY - {scenario.upper()}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Embedding stats before
    stats = get_embedding_stats()
    print(f"\nEmbedding coverage: {stats['have_embeddings']}/{stats['total_tickers']} ({stats['coverage_pct']}%)")
    
    # Phase 1
    phase1_results = run_phase1(scenario, dry_run)
    
    if not phase1_results:
        print("\nPhase 1 produced no allocations. Stopping.")
        return None
    
    # Phase 2
    phase2_results = run_phase2(phase1_results, scenario, dry_run)
    
    # Final summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    
    final_allocations = {}
    for sector in phase1_results:
        p1 = phase1_results[sector]
        p2 = phase2_results.get(sector, {}) if phase2_results else {}
        
        # Use refined allocation if available and adjusted
        if p2.get("action") == "adjust":
            final_alloc = p2.get("new_allocation", p1.get("allocation", {}))
            refined = True
        else:
            final_alloc = p1.get("allocation", {})
            refined = False
        
        final_allocations[sector] = {
            "allocation": final_alloc,
            "sentiment": p1.get("sentiment", 0),
            "refined": refined
        }
        
        marker = "⚡" if refined else "✓"
        print(f"{marker} {sector}: {final_alloc}")
    
    # Stats after
    stats = get_embedding_stats()
    print(f"\nEmbedding coverage now: {stats['have_embeddings']}/{stats['total_tickers']} ({stats['coverage_pct']}%)")
    
    return {
        "phase1": phase1_results,
        "phase2": phase2_results,
        "final": final_allocations
    }


# CLI
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Two-Phase Trading Strategy")
        print("\nUsage: python3 two_phase_strategy.py <command> [args]")
        print("\nCommands:")
        print("  run [scenario]      - Run both phases (default: benchmark)")
        print("  phase1 [scenario]   - Run only Phase 1")
        print("  phase2 [scenario]   - Run only Phase 2 (uses existing Phase 1)")
        print("  status              - Show embedding stats and recent runs")
        sys.exit(1)
    
    cmd = sys.argv[1]
    scenario = sys.argv[2] if len(sys.argv) > 2 else "benchmark"
    
    if cmd == "run":
        run_both_phases(scenario)
    
    elif cmd == "phase1":
        run_phase1(scenario)
    
    elif cmd == "phase2":
        # Load existing Phase 1 allocations
        allocations = get_phase1_allocations(scenario)
        if not allocations:
            print("No Phase 1 allocations found. Run phase1 first.")
            sys.exit(1)
        run_phase2(allocations, scenario)
    
    elif cmd == "status":
        stats = get_embedding_stats()
        print("Embedding Statistics:")
        print(f"  Total tickers:    {stats['total_tickers']}")
        print(f"  Have embeddings:  {stats['have_embeddings']}")
        print(f"  Missing:          {stats['missing']}")
        print(f"  Coverage:         {stats['coverage_pct']}%")
        
        print("\nRecent runs:")
        if os.path.exists(TWO_PHASE_LOG):
            with open(TWO_PHASE_LOG, 'r') as f:
                for line in f.readlines()[-5:]:
                    data = json.loads(line)
                    phase = data.get("phase", "?")
                    ts = data.get("timestamp", "?")[:16]
                    print(f"  {ts} - {phase}")
        else:
            print("  No runs logged yet")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
