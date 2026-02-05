#!/usr/bin/env python3
"""
Ollama Portfolio Selection - AI-driven asset selection per sector.
V2: Two-phase strategy integrated (quick selection + embedding refinement)
"""

import json
import urllib.request
import os
import re
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"

# Two-phase config
ENABLE_PHASE2 = True  # Toggle for Phase 2 refinement
MAX_EMBEDDINGS_PER_RUN = 3  # Limit embedding fetches per run


def load_prompts():
    path = os.path.join(BASE_DIR, "portfolio_prompts.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"prompts": {}, "base_system_prompt": ""}


def load_assets():
    path = os.path.join(BASE_DIR, "sector_assets.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"sectors": {}}


def get_portfolio_prompt(sector):
    data = load_prompts()
    base = data.get("base_system_prompt", "")
    if sector in data.get("prompts", {}):
        sd = data["prompts"][sector]
        return base.format(
            sector_name=sd.get("sector_name", sector),
            sector_specific_prompt=sd.get("current_prompt", "")
        )
    return base.format(sector_name=sector, sector_specific_prompt="Select assets based on sentiment.")


def get_stocks(sector):
    assets = load_assets()
    if sector in assets.get("sectors", {}):
        return assets["sectors"][sector].get("stocks", [])
    return []


def select_assets(sector, sentiment, scenario="benchmark", budget=10000, timeout=60):
    """Phase 1: Quick sentiment-based asset selection."""
    system_prompt = get_portfolio_prompt(sector)
    stocks = get_stocks(sector)
    if not stocks:
        return None
    
    stock_list = "\n".join([f"- {s['ticker']}: {s['name']} ({s.get('focus', 'general')})" for s in stocks])
    sentiment_desc = "BULLISH" if sentiment > 0.3 else ("BEARISH" if sentiment < -0.3 else "NEUTRAL")
    
    user_prompt = f"""Conditions:
- Sector: {sector}
- Sentiment: {sentiment:+.2f} ({sentiment_desc})
- Scenario: {scenario}
- Budget: ${budget:,.0f}

Available assets:
{stock_list}

Select best assets. Return valid JSON only."""

    payload = json.dumps({
        "model": MODEL,
        "prompt": user_prompt,
        "system": system_prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 500}
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            response = result.get("response", "")
            
            # Parse JSON from response
            match = re.search(r"\{[\s\S]*\}", response)
            if match:
                try:
                    data = json.loads(match.group())
                    selected = data.get("selected_assets", [])
                    total_w = sum(a.get("weight", 0) for a in selected)
                    if total_w > 0:
                        for a in selected:
                            a["weight"] = a.get("weight", 0) / total_w
                            a["amount"] = round(a["weight"] * budget, 2)
                    valid_tickers = {s["ticker"] for s in stocks}
                    selected = [a for a in selected if a.get("ticker") in valid_tickers]
                    return {
                        "sector": sector,
                        "sentiment": sentiment,
                        "selected_assets": selected,
                        "rationale": data.get("rationale", "N/A"),
                        "risk_level": data.get("risk_level", "medium"),
                        "phase": 1
                    }
                except:
                    pass
            
            # Fallback: extract mentioned tickers
            valid_tickers = {s["ticker"] for s in stocks}
            mentioned = [t for t in valid_tickers if t in response.upper()]
            if mentioned:
                w = 1.0 / len(mentioned)
                return {
                    "sector": sector,
                    "sentiment": sentiment,
                    "selected_assets": [{"ticker": t, "weight": w, "amount": round(w*budget, 2)} for t in mentioned[:5]],
                    "rationale": "Extracted from response",
                    "risk_level": "medium",
                    "phase": 1
                }
    except Exception as e:
        print(f"Phase 1 Error: {e}")
    return None


def select_assets_for_sector(sector, sentiment, scenario="benchmark"):
    """Wrapper for compatibility with two_phase_strategy.py"""
    result = select_assets(sector, sentiment, scenario)
    if result:
        # Convert to allocation dict format
        allocation = {}
        for asset in result.get("selected_assets", []):
            ticker = asset.get("ticker")
            weight = asset.get("weight", 0)
            if ticker:
                allocation[ticker] = round(weight * 100, 1)
        return {
            "allocation": allocation,
            "reasoning": result.get("rationale", ""),
            "risk_level": result.get("risk_level", "medium")
        }
    return None


def run_phase2_refinement(phase1_result, sector, sentiment, scenario="benchmark"):
    """
    Phase 2: Refine allocation using company embeddings.
    Only runs if ENABLE_PHASE2 is True.
    Now includes feedback loop for learning from decisions.
    """
    if not ENABLE_PHASE2:
        return phase1_result
    
    try:
        # Import Phase 2 modules (lazy import to avoid startup cost)
        from embedding_manager import get_missing_embeddings, fetch_missing_embeddings
        from refined_strategy import refine_allocation
        
        # Try to import feedback system (optional)
        try:
            from phase2_feedback import log_decision, should_apply_adjustment
            feedback_enabled = True
        except ImportError:
            feedback_enabled = False
        
        # Get tickers from Phase 1
        tickers = [a.get("ticker") for a in phase1_result.get("selected_assets", [])]
        if not tickers:
            return phase1_result
        
        # Check and fetch missing embeddings
        missing, _ = get_missing_embeddings(tickers)
        if missing:
            print(f"  Phase 2: Fetching {min(len(missing), MAX_EMBEDDINGS_PER_RUN)} embeddings...")
            fetch_missing_embeddings(tickers, max_fetch=MAX_EMBEDDINGS_PER_RUN)
        
        # Convert Phase 1 result to allocation dict
        current_allocation = {}
        for asset in phase1_result.get("selected_assets", []):
            ticker = asset.get("ticker")
            weight = asset.get("weight", 0)
            if ticker:
                current_allocation[ticker] = round(weight * 100, 1)
        
        # Run refinement
        print(f"  Phase 2: Refining {sector} allocation...")
        refinement = refine_allocation(sector, sentiment, current_allocation, scenario)
        
        action = refinement.get("action", "keep")
        confidence = refinement.get("confidence", 0)
        new_allocation = refinement.get("new_allocation", current_allocation)
        
        # Check if we should apply the adjustment (based on learned thresholds)
        apply_adjustment = action == "adjust"
        if apply_adjustment and feedback_enabled:
            if not should_apply_adjustment(confidence):
                print(f"  Phase 2: Confidence {confidence:.0%} below threshold, keeping Phase 1")
                apply_adjustment = False
                action = "keep_low_conf"
        
        if apply_adjustment:
            # Update Phase 1 result with refined allocation
            budget = sum(a.get("amount", 0) for a in phase1_result.get("selected_assets", []))
            
            refined_assets = []
            for ticker, pct in new_allocation.items():
                weight = pct / 100.0
                refined_assets.append({
                    "ticker": ticker,
                    "weight": weight,
                    "amount": round(weight * budget, 2)
                })
            
            phase1_result["selected_assets"] = refined_assets
            phase1_result["rationale"] = f"[Refined] {refinement.get('reasoning', '')}"
            phase1_result["phase"] = 2
            phase1_result["refinement_confidence"] = confidence
            print(f"  Phase 2: Allocation adjusted (confidence: {confidence:.0%})")
            
            final_allocation = new_allocation
        else:
            print(f"  Phase 2: Keeping Phase 1 allocation")
            phase1_result["phase"] = "1+2"
            final_allocation = current_allocation
        
        # Log decision for feedback learning
        if feedback_enabled:
            log_decision(
                sector=sector,
                sentiment=sentiment,
                action=action,
                confidence=confidence,
                original_allocation=current_allocation,
                final_allocation=final_allocation,
                reasoning=refinement.get("reasoning", "")
            )
            phase1_result["phase"] = "1+2"
        
        return phase1_result
        
    except ImportError as e:
        print(f"  Phase 2 skipped (modules not available): {e}")
        return phase1_result
    except Exception as e:
        print(f"  Phase 2 Error: {e}")
        return phase1_result


def select_assets_two_phase(sector, sentiment, scenario="benchmark", budget=10000, timeout=60):
    """
    Two-phase asset selection:
    1. Quick sentiment-based selection (llama3.2:3b)
    2. Refinement with company embeddings (llama3.1:8b)
    """
    print(f"Phase 1: {sector} | Sentiment: {sentiment:+.2f} | {scenario}")
    
    # Phase 1: Quick selection
    result = select_assets(sector, sentiment, scenario, budget, timeout)
    
    if not result:
        print(f"  Phase 1: No result")
        return None
    
    print(f"  Phase 1: Selected {len(result.get('selected_assets', []))} assets")
    
    # Phase 2: Refinement
    result = run_phase2_refinement(result, sector, sentiment, scenario)
    
    return result


# CLI
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--no-phase2":
        ENABLE_PHASE2 = False
        print("Phase 2 disabled")
    
    print("Testing two-phase portfolio selection...\n")
    tests = [
        ("XLK", 0.6, "aggressive"),
        ("XLF", -0.3, "defensive"),
    ]
    
    for sector, sentiment, scenario in tests:
        print(f"\n{'='*50}")
        result = select_assets_two_phase(sector, sentiment, scenario)
        if result:
            print(f"\nResult (Phase {result.get('phase', '?')}):")
            for a in result.get("selected_assets", []):
                print(f"  {a['ticker']}: {a['weight']*100:.0f}% (${a['amount']:,.0f})")
            print(f"  Rationale: {result.get('rationale', 'N/A')[:80]}...")
        else:
            print("  Failed")
