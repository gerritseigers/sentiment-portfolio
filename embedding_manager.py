#!/usr/bin/env python3
"""
Embedding Manager - Manages company profiles/embeddings for refined strategy.

Checks which companies need embeddings, fetches missing ones via Ollama,
and provides company context for strategy decisions.
"""

import json
import os
import sys
from datetime import datetime, timedelta
import requests

# Config
EMBEDDINGS_FILE = os.path.join(os.path.dirname(__file__), "company_embeddings.json")
SECTOR_ASSETS_FILE = os.path.join(os.path.dirname(__file__), "sector_assets.json")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"  # Larger model for better company analysis
EMBEDDING_MAX_AGE_DAYS = 30  # Refresh embeddings older than this


def load_embeddings():
    """Load existing embeddings from file."""
    if os.path.exists(EMBEDDINGS_FILE):
        with open(EMBEDDINGS_FILE, 'r') as f:
            return json.load(f)
    return {"_meta": {"version": 1}, "companies": {}}


def save_embeddings(data):
    """Save embeddings to file."""
    data["_meta"]["last_updated"] = datetime.now().isoformat()
    with open(EMBEDDINGS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def load_all_tickers():
    """Get all tickers from sector_assets.json."""
    tickers = set()
    if os.path.exists(SECTOR_ASSETS_FILE):
        with open(SECTOR_ASSETS_FILE, 'r') as f:
            sector_assets = json.load(f)
        for sector, assets in sector_assets.items():
            if sector.startswith("_"):
                continue
            for asset in assets:
                if isinstance(asset, dict):
                    tickers.add(asset.get("ticker", ""))
                else:
                    tickers.add(asset)
    return [t for t in tickers if t]


def get_missing_embeddings(tickers=None):
    """Find tickers that need embeddings (missing or outdated)."""
    embeddings = load_embeddings()
    companies = embeddings.get("companies", {})
    
    if tickers is None:
        tickers = load_all_tickers()
    
    missing = []
    outdated = []
    cutoff = datetime.now() - timedelta(days=EMBEDDING_MAX_AGE_DAYS)
    
    for ticker in tickers:
        if ticker not in companies:
            missing.append(ticker)
        else:
            # Check if outdated
            updated = companies[ticker].get("updated")
            if updated:
                try:
                    updated_dt = datetime.fromisoformat(updated)
                    if updated_dt < cutoff:
                        outdated.append(ticker)
                except:
                    outdated.append(ticker)
            else:
                outdated.append(ticker)
    
    return missing, outdated


def fetch_company_profile(ticker):
    """Fetch company profile from Ollama."""
    prompt = f"""Analyze the company with ticker symbol {ticker} and provide a structured profile.

Return ONLY valid JSON (no markdown, no explanation) with this structure:
{{
    "company_name": "Full company name",
    "sector": "Primary sector",
    "industry": "Specific industry",
    "summary": "2-3 sentence description of what the company does",
    "business_model": "How the company makes money",
    "key_products": ["product1", "product2", "product3"],
    "competitors": ["competitor1", "competitor2", "competitor3"],
    "market_position": "leader/challenger/niche",
    "volatility": "high/medium/low",
    "sentiment_factors": ["factor1", "factor2"],
    "risks": ["risk1", "risk2"],
    "catalysts": ["potential positive catalyst 1", "catalyst 2"]
}}

If you don't know the company, still return valid JSON with "unknown" values."""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3}
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "").strip()
            
            # Try to parse JSON from response
            # Handle potential markdown code blocks
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            try:
                profile = json.loads(text)
                profile["ticker"] = ticker
                profile["updated"] = datetime.now().isoformat()
                profile["model_used"] = OLLAMA_MODEL
                return profile
            except json.JSONDecodeError as e:
                print(f"  JSON parse error for {ticker}: {e}")
                return None
        else:
            print(f"  Ollama error for {ticker}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"  Exception fetching {ticker}: {e}")
        return None


def fetch_missing_embeddings(tickers=None, max_fetch=10):
    """Fetch embeddings for missing/outdated tickers."""
    missing, outdated = get_missing_embeddings(tickers)
    to_fetch = (missing + outdated)[:max_fetch]
    
    if not to_fetch:
        print("All embeddings up to date!")
        return []
    
    print(f"Fetching embeddings for {len(to_fetch)} companies...")
    embeddings = load_embeddings()
    fetched = []
    
    for ticker in to_fetch:
        print(f"  Fetching {ticker}...")
        profile = fetch_company_profile(ticker)
        if profile:
            embeddings["companies"][ticker] = profile
            fetched.append(ticker)
            print(f"    ✓ {profile.get('company_name', ticker)}")
        else:
            print(f"    ✗ Failed")
    
    if fetched:
        save_embeddings(embeddings)
        print(f"\nSaved {len(fetched)} embeddings")
    
    return fetched


def get_company_context(tickers):
    """Get company profiles for given tickers."""
    embeddings = load_embeddings()
    companies = embeddings.get("companies", {})
    
    context = {}
    for ticker in tickers:
        if ticker in companies:
            context[ticker] = companies[ticker]
    
    return context


def get_embedding_stats():
    """Get statistics about embeddings."""
    embeddings = load_embeddings()
    companies = embeddings.get("companies", {})
    all_tickers = load_all_tickers()
    
    missing, outdated = get_missing_embeddings()
    
    return {
        "total_tickers": len(all_tickers),
        "have_embeddings": len(companies),
        "missing": len(missing),
        "outdated": len(outdated),
        "coverage_pct": round(len(companies) / len(all_tickers) * 100, 1) if all_tickers else 0
    }


# CLI interface
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 embedding_manager.py <command> [args]")
        print("\nCommands:")
        print("  status              - Show embedding statistics")
        print("  missing             - List missing embeddings")
        print("  fetch [max]         - Fetch missing embeddings (default: 10)")
        print("  fetch-ticker TICKER - Fetch specific ticker")
        print("  get TICKER          - Show embedding for ticker")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        stats = get_embedding_stats()
        print(f"Embedding Status:")
        print(f"  Total tickers:    {stats['total_tickers']}")
        print(f"  Have embeddings:  {stats['have_embeddings']}")
        print(f"  Missing:          {stats['missing']}")
        print(f"  Outdated:         {stats['outdated']}")
        print(f"  Coverage:         {stats['coverage_pct']}%")
    
    elif cmd == "missing":
        missing, outdated = get_missing_embeddings()
        print(f"Missing ({len(missing)}): {', '.join(missing[:20])}")
        if len(missing) > 20:
            print(f"  ... and {len(missing) - 20} more")
        print(f"\nOutdated ({len(outdated)}): {', '.join(outdated[:20])}")
    
    elif cmd == "fetch":
        max_fetch = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        fetch_missing_embeddings(max_fetch=max_fetch)
    
    elif cmd == "fetch-ticker":
        if len(sys.argv) < 3:
            print("Usage: fetch-ticker TICKER")
            sys.exit(1)
        ticker = sys.argv[2].upper()
        profile = fetch_company_profile(ticker)
        if profile:
            embeddings = load_embeddings()
            embeddings["companies"][ticker] = profile
            save_embeddings(embeddings)
            print(json.dumps(profile, indent=2))
    
    elif cmd == "get":
        if len(sys.argv) < 3:
            print("Usage: get TICKER")
            sys.exit(1)
        ticker = sys.argv[2].upper()
        embeddings = load_embeddings()
        if ticker in embeddings.get("companies", {}):
            print(json.dumps(embeddings["companies"][ticker], indent=2))
        else:
            print(f"No embedding found for {ticker}")
    
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
