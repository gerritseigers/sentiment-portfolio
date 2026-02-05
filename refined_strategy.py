#!/usr/bin/env python3
"""
Refined Strategy - Phase 2 of the two-phase trading approach.

Phase 1: Quick reaction based on sentiment alone (ollama_portfolio.py)
Phase 2: This script - refines positions using company embeddings + news context

Combines:
- Current sector sentiment
- Company profiles/embeddings
- Recent news headlines
- Existing positions

To produce refined allocation recommendations.
"""

import json
import os
import sys
from datetime import datetime
import requests

# Config
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"  # Larger model for complex reasoning

BASE_DIR = os.path.dirname(__file__)
EMBEDDINGS_FILE = os.path.join(BASE_DIR, "company_embeddings.json")
SECTOR_ASSETS_FILE = os.path.join(BASE_DIR, "sector_assets.json")
NEWS_CACHE_FILE = os.path.join(BASE_DIR, "data/news_cache.json")
REFINED_LOG_FILE = os.path.join(BASE_DIR, "data/refined_strategy_log.jsonl")


def load_json(filepath):
    """Load JSON file if exists."""
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return json.load(f)
    return {}


def load_embeddings():
    """Load company embeddings."""
    data = load_json(EMBEDDINGS_FILE)
    return data.get("companies", {})


def load_sector_assets():
    """Load sector to assets mapping."""
    return load_json(SECTOR_ASSETS_FILE)


def get_recent_news(sector, limit=5):
    """Get recent news headlines for a sector."""
    cache = load_json(NEWS_CACHE_FILE)
    sector_news = cache.get(sector, [])
    
    # Sort by date, get most recent
    sorted_news = sorted(sector_news, key=lambda x: x.get("date", ""), reverse=True)
    return sorted_news[:limit]


def build_refinement_prompt(sector, sentiment_score, current_allocation, embeddings, news):
    """Build prompt for refined strategy."""
    
    # Format company profiles
    company_context = ""
    for ticker, alloc in current_allocation.items():
        if ticker in embeddings:
            profile = embeddings[ticker]
            company_context += f"""
**{ticker}** (current allocation: {alloc}%)
- Company: {profile.get('company_name', 'Unknown')}
- Business: {profile.get('summary', 'N/A')}
- Market position: {profile.get('market_position', 'N/A')}
- Volatility: {profile.get('volatility', 'N/A')}
- Key risks: {', '.join(profile.get('risks', [])[:2])}
- Catalysts: {', '.join(profile.get('catalysts', [])[:2])}
"""
        else:
            company_context += f"\n**{ticker}** (current allocation: {alloc}%) - No profile available\n"
    
    # Format news
    news_context = ""
    for item in news[:5]:
        news_context += f"- {item.get('title', 'No title')}\n"
    
    if not news_context:
        news_context = "- No recent news available\n"
    
    prompt = f"""You are a portfolio strategist refining asset allocations based on company fundamentals and news.

## Current Situation
**Sector:** {sector}
**Sentiment Score:** {sentiment_score} (scale: -1 bearish to +1 bullish)

## Recent News
{news_context}

## Current Allocation & Company Profiles
{company_context}

## Your Task
Review the current allocation considering:
1. How each company's business model aligns with current market sentiment
2. Company-specific risks vs current news themes
3. Potential catalysts that could amplify or dampen sector trends
4. Volatility characteristics for risk management

Should the allocation be adjusted? If so, how?

Return ONLY valid JSON (no markdown, no explanation):
{{
    "action": "keep" or "adjust",
    "reasoning": "Brief explanation (1-2 sentences)",
    "new_allocation": {{"TICKER": percentage, ...}},
    "confidence": 0.0 to 1.0,
    "risk_notes": "Any specific risks to watch"
}}

If action is "keep", new_allocation should match current allocation.
Percentages must sum to 100."""

    return prompt


def refine_allocation(sector, sentiment_score, current_allocation, scenario="benchmark"):
    """
    Refine allocation using company embeddings and news context.
    
    Args:
        sector: Sector ETF symbol (e.g., "XLK")
        sentiment_score: Current sentiment (-1 to +1)
        current_allocation: Dict of ticker -> percentage
        scenario: Trading scenario name
    
    Returns:
        Dict with refinement decision
    """
    embeddings = load_embeddings()
    news = get_recent_news(sector)
    
    # Check embedding coverage
    tickers = list(current_allocation.keys())
    have_embeddings = [t for t in tickers if t in embeddings]
    missing_embeddings = [t for t in tickers if t not in embeddings]
    
    result = {
        "sector": sector,
        "sentiment_score": sentiment_score,
        "scenario": scenario,
        "original_allocation": current_allocation,
        "embedding_coverage": f"{len(have_embeddings)}/{len(tickers)}",
        "missing_embeddings": missing_embeddings,
        "timestamp": datetime.now().isoformat()
    }
    
    # If no embeddings at all, can't refine
    if not have_embeddings:
        result["action"] = "keep"
        result["reasoning"] = "No embeddings available for refinement"
        result["new_allocation"] = current_allocation
        result["confidence"] = 0.0
        return result
    
    # Build and send prompt
    prompt = build_refinement_prompt(
        sector, sentiment_score, current_allocation, embeddings, news
    )
    
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3}
            },
            timeout=90
        )
        
        if response.status_code == 200:
            text = response.json().get("response", "").strip()
            
            # Parse JSON from response
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            try:
                decision = json.loads(text)
                result.update(decision)
                
                # Validate allocation sums to ~100
                new_alloc = decision.get("new_allocation", {})
                total = sum(new_alloc.values())
                if abs(total - 100) > 5:  # Allow small rounding errors
                    result["warning"] = f"Allocation sums to {total}%, expected 100%"
                
            except json.JSONDecodeError as e:
                result["action"] = "keep"
                result["reasoning"] = f"JSON parse error: {e}"
                result["new_allocation"] = current_allocation
                result["confidence"] = 0.0
                result["raw_response"] = text[:500]
        else:
            result["action"] = "keep"
            result["reasoning"] = f"Ollama error: {response.status_code}"
            result["new_allocation"] = current_allocation
            result["confidence"] = 0.0
            
    except Exception as e:
        result["action"] = "keep"
        result["reasoning"] = f"Exception: {str(e)}"
        result["new_allocation"] = current_allocation
        result["confidence"] = 0.0
    
    # Log the refinement
    log_refinement(result)
    
    return result


def log_refinement(result):
    """Log refinement decision to JSONL file."""
    os.makedirs(os.path.dirname(REFINED_LOG_FILE), exist_ok=True)
    with open(REFINED_LOG_FILE, 'a') as f:
        f.write(json.dumps(result) + "\n")


def batch_refine(allocations_by_sector, scenario="benchmark"):
    """
    Refine multiple sector allocations.
    
    Args:
        allocations_by_sector: Dict of sector -> {sentiment, allocation}
    
    Returns:
        Dict of sector -> refinement result
    """
    results = {}
    
    for sector, data in allocations_by_sector.items():
        sentiment = data.get("sentiment", 0)
        allocation = data.get("allocation", {})
        
        if allocation:
            print(f"Refining {sector}...")
            results[sector] = refine_allocation(
                sector, sentiment, allocation, scenario
            )
    
    return results


def get_refinement_summary(results):
    """Generate summary of refinement decisions."""
    adjustments = []
    keeps = []
    
    for sector, result in results.items():
        action = result.get("action", "keep")
        if action == "adjust":
            adjustments.append({
                "sector": sector,
                "reasoning": result.get("reasoning", ""),
                "confidence": result.get("confidence", 0),
                "changes": _calc_changes(
                    result.get("original_allocation", {}),
                    result.get("new_allocation", {})
                )
            })
        else:
            keeps.append(sector)
    
    return {
        "total_sectors": len(results),
        "adjustments": len(adjustments),
        "kept_as_is": len(keeps),
        "adjustment_details": adjustments,
        "kept_sectors": keeps
    }


def _calc_changes(original, new):
    """Calculate allocation changes."""
    changes = []
    all_tickers = set(original.keys()) | set(new.keys())
    
    for ticker in all_tickers:
        old_val = original.get(ticker, 0)
        new_val = new.get(ticker, 0)
        diff = new_val - old_val
        if abs(diff) > 1:  # Only report changes > 1%
            changes.append(f"{ticker}: {old_val}% → {new_val}% ({diff:+.0f}%)")
    
    return changes


# CLI interface
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 refined_strategy.py <command> [args]")
        print("\nCommands:")
        print("  test SECTOR SCORE   - Test refinement (e.g., test XLK 0.5)")
        print("  status              - Show recent refinements")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "test":
        if len(sys.argv) < 4:
            print("Usage: test SECTOR SENTIMENT_SCORE")
            print("Example: test XLK 0.5")
            sys.exit(1)
        
        sector = sys.argv[2].upper()
        sentiment = float(sys.argv[3])
        
        # Create test allocation
        sector_assets = load_sector_assets()
        assets = sector_assets.get(sector, [])[:4]  # Top 4 assets
        
        if not assets:
            print(f"No assets found for {sector}")
            sys.exit(1)
        
        # Create equal allocation for test
        test_allocation = {}
        for asset in assets:
            ticker = asset.get("ticker") if isinstance(asset, dict) else asset
            test_allocation[ticker] = round(100 / len(assets), 1)
        
        print(f"Testing refinement for {sector} with sentiment {sentiment}")
        print(f"Test allocation: {test_allocation}")
        print("-" * 50)
        
        result = refine_allocation(sector, sentiment, test_allocation)
        print(json.dumps(result, indent=2))
    
    elif cmd == "status":
        if os.path.exists(REFINED_LOG_FILE):
            print("Recent refinements:")
            with open(REFINED_LOG_FILE, 'r') as f:
                lines = f.readlines()[-10:]  # Last 10
                for line in lines:
                    data = json.loads(line)
                    action = data.get("action", "?")
                    sector = data.get("sector", "?")
                    confidence = data.get("confidence", 0)
                    print(f"  {sector}: {action} (confidence: {confidence:.1%})")
        else:
            print("No refinements logged yet")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
