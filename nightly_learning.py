#!/usr/bin/env python3
"""
Nightly Learning Pipeline - Self-improving trading AI
Runs 00:00 - 06:00, makes the model smarter every day.

Phases:
1. News Source Discovery - Find and validate new sources
2. Embedding Expansion - Build company profiles for all assets
3. Sector Expansion - Discover and add new sectors/assets
4. Knowledge Ingestion - Learn from investing resources
5. Prompt Evolution - Improve prompts based on accuracy
6. Self-Evaluation - Report what was learned
"""

import json
import os
import sys
import time
import urllib.request
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OLLAMA_URL = "http://localhost:11434/api/generate"

# Learning log
LEARNING_LOG = os.path.join(DATA_DIR, "nightly_learning_log.jsonl")

# Config files
NEWS_SOURCES_FILE = os.path.join(BASE_DIR, "news_sources.json")
SECTOR_ASSETS_FILE = os.path.join(BASE_DIR, "sector_assets.json")
EMBEDDINGS_FILE = os.path.join(BASE_DIR, "company_embeddings.json")
KNOWLEDGE_FILE = os.path.join(DATA_DIR, "investing_knowledge.json")

# Time budget per phase (seconds)
TIME_BUDGET = {
    "news_discovery": 3600,      # 1 hour
    "embedding_expansion": 5400, # 1.5 hours
    "sector_expansion": 3600,    # 1 hour
    "knowledge_ingestion": 3600, # 1 hour
    "knowledge_harvest": 3600,   # 1 hour (weekly - external articles)
    "prompt_evolution": 3600,    # 1 hour
    "self_evaluation": 1800      # 30 min
}

# Weekly harvest tracking
HARVEST_STATE_FILE = os.path.join(DATA_DIR, "harvest_state.json")


def log_learning(phase: str, action: str, details: dict):
    """Log learning activity."""
    entry = {
        "timestamp": datetime.now().isoformat(),
        "phase": phase,
        "action": action,
        **details
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LEARNING_LOG, 'a') as f:
        f.write(json.dumps(entry) + "\n")
    print(f"  [{phase}] {action}: {details.get('result', 'OK')}")


def load_json(path: str) -> dict:
    if os.path.exists(path):
        with open(path, 'r') as f:
            return json.load(f)
    return {}


def save_json(path: str, data: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def ollama_generate(prompt: str, model: str = "llama3.2:3b", timeout: int = 60) -> Optional[str]:
    """Generate text with Ollama."""
    try:
        payload = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 1000}
        }).encode("utf-8")
        req = urllib.request.Request(OLLAMA_URL, data=payload, 
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")).get("response", "")
    except Exception as e:
        print(f"    Ollama error: {e}")
        return None


# =============================================================================
# PHASE 1: News Source Discovery
# =============================================================================

POTENTIAL_NEWS_SOURCES = [
    # Financial News
    {"url": "https://finance.yahoo.com/news/", "name": "Yahoo Finance", "lang": "en"},
    {"url": "https://www.cnbc.com/world/", "name": "CNBC World", "lang": "en"},
    {"url": "https://www.ft.com/", "name": "Financial Times", "lang": "en"},
    {"url": "https://www.wsj.com/news/markets", "name": "Wall Street Journal", "lang": "en"},
    {"url": "https://www.bloomberg.com/markets", "name": "Bloomberg", "lang": "en"},
    {"url": "https://seekingalpha.com/market-news", "name": "Seeking Alpha", "lang": "en"},
    {"url": "https://www.investing.com/news/", "name": "Investing.com", "lang": "en"},
    {"url": "https://www.zerohedge.com/", "name": "ZeroHedge", "lang": "en"},
    # Dutch
    {"url": "https://fd.nl/", "name": "Financieele Dagblad", "lang": "nl"},
    {"url": "https://www.iex.nl/nieuws/", "name": "IEX", "lang": "nl"},
    {"url": "https://www.belegger.nl/nieuws/", "name": "Belegger.nl", "lang": "nl"},
    # Sector specific
    {"url": "https://techcrunch.com/", "name": "TechCrunch", "lang": "en", "sector": "tech"},
    {"url": "https://www.coindesk.com/", "name": "CoinDesk", "lang": "en", "sector": "crypto"},
    {"url": "https://oilprice.com/", "name": "OilPrice", "lang": "en", "sector": "energy"},
    {"url": "https://www.biopharmadive.com/", "name": "BioPharma Dive", "lang": "en", "sector": "healthcare"},
]


def test_news_source(url: str, timeout: int = 10) -> dict:
    """Test if a news source is accessible and has useful content."""
    result = {"accessible": False, "has_content": False, "headlines": 0}
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            result["accessible"] = True
            # Count potential headlines (h1, h2, h3, article titles)
            headlines = len(re.findall(r'<h[123][^>]*>.*?</h[123]>', html, re.IGNORECASE))
            headlines += len(re.findall(r'<article[^>]*>.*?</article>', html[:50000], re.IGNORECASE | re.DOTALL))
            result["headlines"] = headlines
            result["has_content"] = headlines > 5
    except Exception as e:
        result["error"] = str(e)[:100]
    return result


def discover_news_sources(time_limit: int = 3600) -> dict:
    """Find and test new news sources."""
    print("\n=== PHASE 1: News Source Discovery ===")
    start = time.time()
    
    # Load existing sources
    existing = load_json(NEWS_SOURCES_FILE)
    if "sources" not in existing:
        existing = {"sources": [], "tested": [], "last_discovery": None}
    
    existing_urls = {s.get("url") for s in existing.get("sources", [])}
    tested_urls = set(existing.get("tested", []))
    
    new_sources = []
    tested = 0
    
    for source in POTENTIAL_NEWS_SOURCES:
        if time.time() - start > time_limit:
            print(f"  Time limit reached after {tested} tests")
            break
            
        url = source["url"]
        if url in existing_urls or url in tested_urls:
            continue
            
        print(f"  Testing: {source['name']}...")
        result = test_news_source(url)
        tested += 1
        existing["tested"].append(url)
        
        if result["accessible"] and result["has_content"]:
            source["status"] = "working"
            source["headlines_found"] = result["headlines"]
            source["discovered"] = datetime.now().isoformat()
            new_sources.append(source)
            existing["sources"].append(source)
            log_learning("news_discovery", "source_added", {
                "name": source["name"], "url": url, "headlines": result["headlines"]
            })
        else:
            log_learning("news_discovery", "source_failed", {
                "name": source["name"], "url": url, "error": result.get("error", "no content")
            })
        
        time.sleep(1)  # Be polite
    
    existing["last_discovery"] = datetime.now().isoformat()
    save_json(NEWS_SOURCES_FILE, existing)
    
    return {"tested": tested, "added": len(new_sources), "total": len(existing["sources"])}


# =============================================================================
# PHASE 2: Embedding Expansion
# =============================================================================

def get_all_tickers() -> List[str]:
    """Get all tickers from sector_assets.json."""
    assets = load_json(SECTOR_ASSETS_FILE)
    tickers = []
    for sector, data in assets.get("sectors", {}).items():
        for stock in data.get("stocks", []):
            if "ticker" in stock:
                tickers.append(stock["ticker"])
    return list(set(tickers))


def fetch_company_embedding(ticker: str, model: str = "llama3.1:8b") -> Optional[dict]:
    """Generate company profile embedding using Ollama."""
    prompt = f"""Analyze the company with ticker symbol {ticker}. Provide a concise profile.

Return ONLY valid JSON:
{{
    "ticker": "{ticker}",
    "company_name": "Full company name",
    "summary": "1-2 sentence business description",
    "sector": "Primary sector",
    "market_position": "leader/challenger/niche",
    "volatility": "low/medium/high",
    "dividend": "yes/no/growing",
    "risks": ["risk1", "risk2", "risk3"],
    "catalysts": ["catalyst1", "catalyst2"],
    "competitors": ["comp1", "comp2"],
    "sentiment_keywords": ["keyword1", "keyword2", "keyword3"]
}}"""

    response = ollama_generate(prompt, model=model, timeout=120)
    if not response:
        return None
    
    # Parse JSON from response
    match = re.search(r'\{[\s\S]*\}', response)
    if match:
        try:
            data = json.loads(match.group())
            data["last_updated"] = datetime.now().isoformat()
            return data
        except:
            pass
    return None


def expand_embeddings(time_limit: int = 5400) -> dict:
    """Expand company embeddings for all assets."""
    print("\n=== PHASE 2: Embedding Expansion ===")
    start = time.time()
    
    # Load existing embeddings
    embeddings = load_json(EMBEDDINGS_FILE)
    if "companies" not in embeddings:
        embeddings = {"companies": {}, "last_expansion": None}
    
    tickers = get_all_tickers()
    existing = set(embeddings["companies"].keys())
    missing = [t for t in tickers if t not in existing]
    
    # Also refresh old embeddings (>30 days)
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    stale = [t for t, data in embeddings["companies"].items() 
             if data.get("last_updated", "") < cutoff]
    
    to_process = missing + stale[:10]  # Prioritize missing, refresh some stale
    
    print(f"  Missing: {len(missing)}, Stale: {len(stale)}, Processing: {len(to_process)}")
    
    added = 0
    refreshed = 0
    
    for ticker in to_process:
        if time.time() - start > time_limit:
            print(f"  Time limit reached after processing {added + refreshed} embeddings")
            break
        
        print(f"  Fetching: {ticker}...")
        embedding = fetch_company_embedding(ticker)
        
        if embedding:
            was_new = ticker not in existing
            embeddings["companies"][ticker] = embedding
            if was_new:
                added += 1
            else:
                refreshed += 1
            log_learning("embedding_expansion", "embedding_created" if was_new else "embedding_refreshed", {
                "ticker": ticker, "company": embedding.get("company_name", "Unknown")
            })
        else:
            log_learning("embedding_expansion", "embedding_failed", {"ticker": ticker})
        
        time.sleep(2)  # Don't overload Ollama
    
    embeddings["last_expansion"] = datetime.now().isoformat()
    save_json(EMBEDDINGS_FILE, embeddings)
    
    return {
        "processed": added + refreshed,
        "added": added,
        "refreshed": refreshed,
        "total": len(embeddings["companies"]),
        "coverage": f"{len(embeddings['companies'])}/{len(tickers)}"
    }


# =============================================================================
# PHASE 3: Sector Expansion
# =============================================================================

NEW_SECTOR_CANDIDATES = {
    "aerospace": {
        "name": "Aerospace & Defense",
        "etf": "ITA",
        "stocks": [
            {"ticker": "BA", "name": "Boeing", "focus": "commercial"},
            {"ticker": "LMT", "name": "Lockheed Martin", "focus": "defense"},
            {"ticker": "RTX", "name": "RTX Corporation", "focus": "defense"},
            {"ticker": "NOC", "name": "Northrop Grumman", "focus": "defense"},
            {"ticker": "GD", "name": "General Dynamics", "focus": "defense"},
        ]
    },
    "biotech": {
        "name": "Biotechnology",
        "etf": "XBI",
        "stocks": [
            {"ticker": "MRNA", "name": "Moderna", "focus": "vaccines"},
            {"ticker": "REGN", "name": "Regeneron", "focus": "antibodies"},
            {"ticker": "VRTX", "name": "Vertex Pharma", "focus": "rare diseases"},
            {"ticker": "BIIB", "name": "Biogen", "focus": "neurology"},
            {"ticker": "ILMN", "name": "Illumina", "focus": "genomics"},
        ]
    },
    "semiconductors": {
        "name": "Semiconductors",
        "etf": "SMH",
        "stocks": [
            {"ticker": "NVDA", "name": "NVIDIA", "focus": "GPU/AI"},
            {"ticker": "AMD", "name": "AMD", "focus": "CPU/GPU"},
            {"ticker": "INTC", "name": "Intel", "focus": "CPU"},
            {"ticker": "TSM", "name": "TSMC", "focus": "foundry"},
            {"ticker": "ASML", "name": "ASML", "focus": "lithography"},
            {"ticker": "AVGO", "name": "Broadcom", "focus": "networking"},
            {"ticker": "QCOM", "name": "Qualcomm", "focus": "mobile"},
        ]
    },
    "ev_clean": {
        "name": "EV & Clean Energy",
        "etf": "QCLN",
        "stocks": [
            {"ticker": "TSLA", "name": "Tesla", "focus": "EV"},
            {"ticker": "RIVN", "name": "Rivian", "focus": "EV"},
            {"ticker": "LCID", "name": "Lucid", "focus": "EV"},
            {"ticker": "ENPH", "name": "Enphase", "focus": "solar"},
            {"ticker": "SEDG", "name": "SolarEdge", "focus": "solar"},
            {"ticker": "FSLR", "name": "First Solar", "focus": "solar"},
        ]
    },
    "cybersecurity": {
        "name": "Cybersecurity",
        "etf": "HACK",
        "stocks": [
            {"ticker": "CRWD", "name": "CrowdStrike", "focus": "endpoint"},
            {"ticker": "PANW", "name": "Palo Alto Networks", "focus": "firewall"},
            {"ticker": "ZS", "name": "Zscaler", "focus": "cloud security"},
            {"ticker": "FTNT", "name": "Fortinet", "focus": "firewall"},
            {"ticker": "NET", "name": "Cloudflare", "focus": "CDN/security"},
        ]
    },
    "ai_cloud": {
        "name": "AI & Cloud Computing",
        "etf": "CLOU",
        "stocks": [
            {"ticker": "MSFT", "name": "Microsoft", "focus": "Azure/AI"},
            {"ticker": "GOOGL", "name": "Alphabet", "focus": "Cloud/AI"},
            {"ticker": "AMZN", "name": "Amazon", "focus": "AWS"},
            {"ticker": "PLTR", "name": "Palantir", "focus": "AI analytics"},
            {"ticker": "SNOW", "name": "Snowflake", "focus": "data cloud"},
            {"ticker": "AI", "name": "C3.ai", "focus": "enterprise AI"},
        ]
    }
}


def expand_sectors(time_limit: int = 3600) -> dict:
    """Add new sectors to the portfolio."""
    print("\n=== PHASE 3: Sector Expansion ===")
    start = time.time()
    
    assets = load_json(SECTOR_ASSETS_FILE)
    if "sectors" not in assets:
        assets = {"sectors": {}}
    
    existing_sectors = set(assets["sectors"].keys())
    added = 0
    
    for sector_id, sector_data in NEW_SECTOR_CANDIDATES.items():
        if time.time() - start > time_limit:
            print(f"  Time limit reached")
            break
            
        if sector_id in existing_sectors:
            continue
        
        print(f"  Adding sector: {sector_data['name']}...")
        assets["sectors"][sector_id] = sector_data
        added += 1
        
        log_learning("sector_expansion", "sector_added", {
            "sector": sector_id,
            "name": sector_data["name"],
            "stocks": len(sector_data.get("stocks", []))
        })
    
    if added > 0:
        save_json(SECTOR_ASSETS_FILE, assets)
    
    return {"added": added, "total": len(assets["sectors"])}


# =============================================================================
# PHASE 4: Knowledge Ingestion
# =============================================================================

INVESTING_KNOWLEDGE = [
    {
        "topic": "value_investing",
        "content": "Value investing focuses on buying undervalued stocks trading below intrinsic value. Key metrics: P/E ratio, P/B ratio, dividend yield. Warren Buffett's approach: margin of safety, competitive moat, quality management."
    },
    {
        "topic": "momentum_investing",
        "content": "Momentum investing buys stocks with strong recent performance, expecting trends to continue. Uses 50/200 day moving averages, RSI, MACD. Risk: trend reversals can be sudden."
    },
    {
        "topic": "sector_rotation",
        "content": "Different sectors perform better in different economic cycles. Early cycle: consumer discretionary, financials. Mid cycle: tech, industrials. Late cycle: energy, materials. Recession: utilities, healthcare, consumer staples."
    },
    {
        "topic": "sentiment_indicators",
        "content": "Market sentiment indicators: VIX (fear index), put/call ratio, AAII sentiment survey, CNN Fear & Greed Index. Extreme fear often signals buying opportunity, extreme greed signals caution."
    },
    {
        "topic": "risk_management",
        "content": "Position sizing: never risk more than 1-2% of portfolio on single trade. Stop losses: 7-10% for growth stocks, tighter for volatile. Diversification: 15-25 positions across uncorrelated sectors."
    },
    {
        "topic": "earnings_analysis",
        "content": "Key earnings metrics: EPS beat/miss, revenue growth, guidance changes, margin expansion. Post-earnings drift: stocks tend to continue moving in earnings reaction direction for weeks."
    },
    {
        "topic": "macro_factors",
        "content": "Macro factors affecting markets: interest rates (inverse to stocks), inflation (erodes real returns), GDP growth, unemployment. Fed policy is the most important driver of market direction."
    },
    {
        "topic": "technical_levels",
        "content": "Key technical levels: 50-day MA (short-term trend), 200-day MA (long-term trend), 52-week high/low, round numbers. Golden cross (50 crosses above 200) is bullish, death cross is bearish."
    }
]


def ingest_knowledge(time_limit: int = 3600) -> dict:
    """Convert investing knowledge to embeddings."""
    print("\n=== PHASE 4: Knowledge Ingestion ===")
    start = time.time()
    
    knowledge = load_json(KNOWLEDGE_FILE)
    if "topics" not in knowledge:
        knowledge = {"topics": {}, "last_ingestion": None}
    
    added = 0
    
    for item in INVESTING_KNOWLEDGE:
        if time.time() - start > time_limit:
            print(f"  Time limit reached")
            break
            
        topic = item["topic"]
        if topic in knowledge["topics"]:
            continue
        
        print(f"  Processing: {topic}...")
        
        # Generate expanded knowledge using Ollama
        prompt = f"""You are a financial analyst. Expand on this investing concept with practical trading implications:

{item['content']}

Provide:
1. Key actionable signals
2. When to apply this strategy
3. Common mistakes to avoid
4. How it interacts with sentiment analysis

Keep response under 300 words, focus on practical application."""

        expanded = ollama_generate(prompt, model="llama3.2:3b", timeout=90)
        
        if expanded:
            knowledge["topics"][topic] = {
                "base": item["content"],
                "expanded": expanded,
                "ingested": datetime.now().isoformat()
            }
            added += 1
            log_learning("knowledge_ingestion", "topic_added", {"topic": topic})
        else:
            log_learning("knowledge_ingestion", "topic_failed", {"topic": topic})
        
        time.sleep(2)
    
    knowledge["last_ingestion"] = datetime.now().isoformat()
    save_json(KNOWLEDGE_FILE, knowledge)
    
    return {"added": added, "total": len(knowledge["topics"])}


# =============================================================================
# PHASE 4b: Knowledge Harvest (Weekly - External Articles)
# =============================================================================

def should_run_harvest() -> bool:
    """Check if harvest should run (weekly, on Sundays)."""
    state = load_json(HARVEST_STATE_FILE)
    last_run = state.get("last_harvest")
    
    if not last_run:
        return True
    
    # Run if it's been > 6 days
    try:
        last_date = datetime.fromisoformat(last_run)
        days_since = (datetime.now() - last_date).days
        return days_since >= 6
    except:
        return True


def harvest_external_knowledge(time_limit: int = 3600) -> dict:
    """Run knowledge harvester to fetch external articles about trading/news."""
    print("\n=== PHASE 4b: Knowledge Harvest (External Articles) ===")
    
    if not should_run_harvest():
        print("  ⏭️ Skipping - already ran this week")
        return {"status": "skipped", "reason": "weekly limit"}
    
    try:
        from knowledge_harvester import run_harvest, compile_knowledge_summary
        
        insights = run_harvest()
        
        # Update harvest state
        state = {
            "last_harvest": datetime.now().isoformat(),
            "insights_count": insights
        }
        save_json(HARVEST_STATE_FILE, state)
        
        # Compile summary for prompt evolution
        summary = compile_knowledge_summary()
        
        log_learning("knowledge_harvest", "harvest_complete", {
            "insights": insights,
            "summary_insights": len(summary.get("key_insights", [])) if summary else 0
        })
        
        return {
            "status": "complete",
            "insights_harvested": insights,
            "summary_compiled": bool(summary)
        }
        
    except ImportError as e:
        print(f"  ⚠️ knowledge_harvester.py not available: {e}")
        return {"status": "skipped", "error": str(e)}
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return {"status": "error", "error": str(e)}


# =============================================================================
# PHASE 5: Prompt Evolution
# =============================================================================

def evolve_prompts(time_limit: int = 3600) -> dict:
    """Run prompt evolution based on accuracy."""
    print("\n=== PHASE 5: Prompt Evolution ===")
    start = time.time()
    
    try:
        from prompt_evolution import evaluate_and_evolve_all
        results = evaluate_and_evolve_all()
        log_learning("prompt_evolution", "evolution_complete", results)
        return results
    except ImportError:
        print("  prompt_evolution.py not available")
        return {"status": "skipped"}
    except Exception as e:
        print(f"  Error: {e}")
        return {"status": "error", "error": str(e)}


# =============================================================================
# PHASE 6: Self-Evaluation
# =============================================================================

def self_evaluate(results: dict) -> dict:
    """Generate summary of what was learned tonight."""
    print("\n=== PHASE 6: Self-Evaluation ===")
    
    # Read today's learning log
    today = datetime.now().strftime("%Y-%m-%d")
    today_entries = []
    
    if os.path.exists(LEARNING_LOG):
        with open(LEARNING_LOG, 'r') as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry.get("timestamp", "").startswith(today):
                        today_entries.append(entry)
    
    summary = {
        "date": today,
        "phases_completed": len([r for r in results.values() if r.get("status") != "error"]),
        "news_sources_added": results.get("news_discovery", {}).get("added", 0),
        "embeddings_added": results.get("embedding_expansion", {}).get("added", 0),
        "sectors_added": results.get("sector_expansion", {}).get("added", 0),
        "knowledge_topics": results.get("knowledge_ingestion", {}).get("added", 0),
        "total_learning_events": len(today_entries)
    }
    
    # Generate AI summary
    prompt = f"""Summarize tonight's learning in 2-3 sentences for the trading log:

Results:
- News sources added: {summary['news_sources_added']}
- Company embeddings: {summary['embeddings_added']} new
- Sectors added: {summary['sectors_added']}
- Knowledge topics: {summary['knowledge_topics']}

Be concise and focus on impact to trading accuracy."""

    ai_summary = ollama_generate(prompt, timeout=30)
    if ai_summary:
        summary["ai_summary"] = ai_summary.strip()
    
    # Save summary
    summary_file = os.path.join(DATA_DIR, f"learning_summary_{today}.json")
    save_json(summary_file, summary)
    
    print(f"\n  Tonight's Learning Summary:")
    print(f"  - News sources: +{summary['news_sources_added']}")
    print(f"  - Embeddings: +{summary['embeddings_added']}")
    print(f"  - Sectors: +{summary['sectors_added']}")
    print(f"  - Knowledge: +{summary['knowledge_topics']}")
    
    if ai_summary:
        print(f"\n  AI Summary: {ai_summary[:200]}...")
    
    log_learning("self_evaluation", "summary_generated", summary)
    
    return summary


# =============================================================================
# MAIN PIPELINE
# =============================================================================

def run_nightly_learning(phases: List[str] = None):
    """Run the complete nightly learning pipeline."""
    print("=" * 60)
    print("NIGHTLY LEARNING PIPELINE")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)
    
    all_phases = ["news_discovery", "embedding_expansion", "sector_expansion", 
                  "knowledge_ingestion", "knowledge_harvest", "prompt_evolution"]
    
    if phases:
        all_phases = [p for p in all_phases if p in phases]
    
    results = {}
    
    for phase in all_phases:
        try:
            if phase == "news_discovery":
                results[phase] = discover_news_sources(TIME_BUDGET[phase])
            elif phase == "embedding_expansion":
                results[phase] = expand_embeddings(TIME_BUDGET[phase])
            elif phase == "sector_expansion":
                results[phase] = expand_sectors(TIME_BUDGET[phase])
            elif phase == "knowledge_ingestion":
                results[phase] = ingest_knowledge(TIME_BUDGET[phase])
            elif phase == "knowledge_harvest":
                results[phase] = harvest_external_knowledge(TIME_BUDGET[phase])
            elif phase == "prompt_evolution":
                results[phase] = evolve_prompts(TIME_BUDGET[phase])
        except Exception as e:
            print(f"  ERROR in {phase}: {e}")
            results[phase] = {"status": "error", "error": str(e)}
    
    # Always run self-evaluation
    results["self_evaluation"] = self_evaluate(results)
    
    print("\n" + "=" * 60)
    print(f"Completed: {datetime.now().isoformat()}")
    print("=" * 60)
    
    return results


# CLI
if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "full":
            run_nightly_learning()
        elif sys.argv[1] == "quick":
            # Quick test - just embeddings and knowledge
            run_nightly_learning(["embedding_expansion", "knowledge_ingestion"])
        elif sys.argv[1] in ["news", "embeddings", "sectors", "knowledge", "harvest", "prompts"]:
            phase_map = {
                "news": "news_discovery",
                "embeddings": "embedding_expansion",
                "sectors": "sector_expansion",
                "knowledge": "knowledge_ingestion",
                "harvest": "knowledge_harvest",
                "prompts": "prompt_evolution"
            }
            run_nightly_learning([phase_map[sys.argv[1]]])
        else:
            print(f"Unknown command: {sys.argv[1]}")
            print("\nUsage: python3 nightly_learning.py <command>")
            print("\nCommands:")
            print("  full       - Run complete pipeline (6 hours)")
            print("  quick      - Quick test (embeddings + knowledge)")
            print("  news       - Only news discovery")
            print("  embeddings - Only embedding expansion")
            print("  sectors    - Only sector expansion")
            print("  knowledge  - Only knowledge ingestion (internal)")
            print("  harvest    - Only knowledge harvest (external articles, weekly)")
            print("  prompts    - Only prompt evolution")
    else:
        print("Nightly Learning Pipeline")
        print("\nUsage: python3 nightly_learning.py <command>")
        print("\nRun 'full' for complete 6-hour learning cycle")
