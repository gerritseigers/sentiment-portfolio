#!/usr/bin/env python3
"""
Knowledge Harvester - Verzamelt kennis over nieuws-trading relaties
Draait wekelijks, voedt de prompt evolution met bewezen inzichten.

Bronnen:
- Trading blogs en analyses (NL + EN)
- Academische papers (via arXiv, SSRN)
- Financial news analysis artikelen

Output: data/knowledge_base.jsonl
"""

import json
import os
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
import requests
from urllib.parse import urlparse, urljoin
import time

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
KNOWLEDGE_FILE = DATA_DIR / "knowledge_base.jsonl"
HARVEST_LOG = DATA_DIR / "knowledge_harvest_log.jsonl"
SOURCES_FILE = SCRIPT_DIR / "knowledge_sources.json"

# Ollama config
OLLAMA_URL = "http://localhost:11434/api/generate"
ANALYSIS_MODEL = "llama3.1:8b"  # Complexer model voor kennis extractie

# Rate limiting
REQUEST_DELAY = 2.0  # Seconds between requests (be polite)


def load_sources():
    """Load configured knowledge sources."""
    if not SOURCES_FILE.exists():
        return get_default_sources()
    with open(SOURCES_FILE) as f:
        return json.load(f)


def get_default_sources():
    """Default knowledge sources - trading & news analysis."""
    return {
        "blogs_en": [
            {
                "name": "Investopedia - News Trading",
                "url": "https://www.investopedia.com/articles/active-trading/051415/how-trade-news.asp",
                "type": "article"
            },
            {
                "name": "Investopedia - Sentiment Analysis",
                "url": "https://www.investopedia.com/terms/s/sentimentindicator.asp",
                "type": "article"
            },
            {
                "name": "Corporate Finance Institute - Sentiment",
                "url": "https://corporatefinanceinstitute.com/resources/career-map/sell-side/capital-markets/market-sentiment/",
                "type": "article"
            }
        ],
        "blogs_nl": [
            {
                "name": "IEX - Beleggingsnieuws",
                "url": "https://www.iex.nl/Artikel/",
                "type": "index",
                "pattern": "/Artikel/\\d+"
            },
            {
                "name": "Belegger.nl - Columns",
                "url": "https://www.belegger.nl/columns/",
                "type": "index"
            }
        ],
        "research": [
            {
                "name": "arXiv Finance - Sentiment",
                "url": "https://arxiv.org/search/?query=stock+market+sentiment+news&searchtype=all",
                "type": "search_index"
            },
            {
                "name": "SSRN Finance",
                "url": "https://papers.ssrn.com/sol3/results.cfm?RequestTimeout=50000000&txtKey_Words=news+sentiment+stock",
                "type": "search_index"
            }
        ],
        "rss_feeds": [
            {
                "name": "Seeking Alpha - Market Analysis",
                "url": "https://seekingalpha.com/market-news/all/feed",
                "type": "rss"
            }
        ]
    }


def fetch_url(url, timeout=30):
    """Fetch URL content with proper headers."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Knowledge Research Bot",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,nl;q=0.8"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"  ⚠️ Failed to fetch {url}: {e}")
        return None


def extract_text_from_html(html):
    """Extract readable text from HTML (simple version)."""
    if not html:
        return ""
    
    # Remove scripts, styles, etc.
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<nav[^>]*>.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<footer[^>]*>.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<header[^>]*>.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', html)
    
    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    # Limit length
    if len(text) > 15000:
        text = text[:15000] + "..."
    
    return text


def extract_insights_with_ollama(text, source_name, source_url):
    """Use Ollama to extract trading/sentiment insights from text."""
    
    prompt = f"""Analyze this article about trading and news sentiment. Extract actionable insights.

Source: {source_name}
URL: {source_url}

Text:
{text[:8000]}

Extract the following in JSON format:
{{
    "key_insights": [
        "insight 1 about news-trading relationship",
        "insight 2 about sentiment indicators",
        ...
    ],
    "sentiment_signals": [
        {{
            "signal": "specific word or pattern",
            "meaning": "what it indicates (bullish/bearish)",
            "confidence": "high/medium/low"
        }}
    ],
    "timing_rules": [
        "rule about when news impacts prices"
    ],
    "sector_specific": {{
        "sector_name": ["relevant insight for this sector"]
    }},
    "quality_score": 1-10,
    "summary": "one paragraph summary of main learnings"
}}

Return ONLY valid JSON, no other text."""

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": ANALYSIS_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.3}
            },
            timeout=120
        )
        
        if response.status_code == 200:
            result = response.json().get("response", "")
            # Try to parse JSON from response
            json_match = re.search(r'\{[\s\S]*\}', result)
            if json_match:
                return json.loads(json_match.group())
        
        return None
    except Exception as e:
        print(f"  ⚠️ Ollama extraction failed: {e}")
        return None


def content_hash(text):
    """Generate hash of content to avoid duplicates."""
    return hashlib.md5(text[:1000].encode()).hexdigest()


def load_existing_hashes():
    """Load hashes of already processed content."""
    hashes = set()
    if KNOWLEDGE_FILE.exists():
        with open(KNOWLEDGE_FILE) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if "content_hash" in entry:
                        hashes.add(entry["content_hash"])
                except:
                    pass
    return hashes


def save_insight(insight_data):
    """Append insight to knowledge base."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(KNOWLEDGE_FILE, "a") as f:
        f.write(json.dumps(insight_data) + "\n")


def log_harvest(log_entry):
    """Log harvest activity."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(HARVEST_LOG, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def harvest_article(source):
    """Harvest and analyze a single article."""
    print(f"  📖 Fetching: {source['name']}")
    
    html = fetch_url(source["url"])
    if not html:
        return None
    
    text = extract_text_from_html(html)
    if len(text) < 500:
        print(f"    ⚠️ Too little content ({len(text)} chars)")
        return None
    
    # Check for duplicate
    existing_hashes = load_existing_hashes()
    hash_val = content_hash(text)
    if hash_val in existing_hashes:
        print(f"    ⏭️ Already processed (duplicate)")
        return None
    
    print(f"    🤖 Analyzing with Ollama...")
    insights = extract_insights_with_ollama(text, source["name"], source["url"])
    
    if not insights:
        print(f"    ⚠️ No insights extracted")
        return None
    
    # Build knowledge entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "source_name": source["name"],
        "source_url": source["url"],
        "source_type": source.get("type", "article"),
        "content_hash": hash_val,
        "insights": insights,
        "text_length": len(text)
    }
    
    save_insight(entry)
    print(f"    ✅ Saved {len(insights.get('key_insights', []))} insights")
    
    return entry


def harvest_index_page(source):
    """Harvest links from an index page and process articles."""
    print(f"  📑 Scanning index: {source['name']}")
    
    html = fetch_url(source["url"])
    if not html:
        return []
    
    # Find article links
    pattern = source.get("pattern", r'href="([^"]+)"')
    links = re.findall(pattern, html)
    
    # Filter and dedupe
    base_url = source["url"]
    articles = []
    seen = set()
    
    for link in links[:10]:  # Limit to 10 articles per source
        if not link.startswith("http"):
            link = urljoin(base_url, link)
        
        if link not in seen and "article" in link.lower() or "/artikel/" in link.lower():
            seen.add(link)
            articles.append({
                "name": f"{source['name']} - Article",
                "url": link,
                "type": "article"
            })
    
    print(f"    Found {len(articles)} article links")
    
    results = []
    for article in articles[:5]:  # Process max 5
        time.sleep(REQUEST_DELAY)
        result = harvest_article(article)
        if result:
            results.append(result)
    
    return results


def compile_knowledge_summary():
    """Compile insights into actionable summary for prompt evolution."""
    if not KNOWLEDGE_FILE.exists():
        return None
    
    all_insights = []
    sentiment_signals = []
    timing_rules = []
    sector_knowledge = {}
    
    with open(KNOWLEDGE_FILE) as f:
        for line in f:
            try:
                entry = json.loads(line)
                insights = entry.get("insights", {})
                
                all_insights.extend(insights.get("key_insights", []))
                sentiment_signals.extend(insights.get("sentiment_signals", []))
                timing_rules.extend(insights.get("timing_rules", []))
                
                for sector, tips in insights.get("sector_specific", {}).items():
                    if sector not in sector_knowledge:
                        sector_knowledge[sector] = []
                    sector_knowledge[sector].extend(tips)
            except:
                pass
    
    return {
        "total_sources": len(all_insights),
        "key_insights": list(set(all_insights))[:50],  # Top 50 unique
        "sentiment_signals": sentiment_signals[:30],
        "timing_rules": list(set(timing_rules))[:20],
        "sector_knowledge": sector_knowledge,
        "compiled_at": datetime.now().isoformat()
    }


def run_harvest():
    """Run the full knowledge harvest."""
    print("=" * 60)
    print("🔬 KNOWLEDGE HARVESTER")
    print(f"   Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    sources = load_sources()
    total_insights = 0
    
    harvest_log = {
        "timestamp": datetime.now().isoformat(),
        "sources_processed": 0,
        "insights_extracted": 0,
        "errors": []
    }
    
    # Process each category
    for category, source_list in sources.items():
        print(f"\n📂 Category: {category}")
        print("-" * 40)
        
        for source in source_list:
            try:
                time.sleep(REQUEST_DELAY)
                
                if source.get("type") == "index" or source.get("type") == "search_index":
                    results = harvest_index_page(source)
                    total_insights += len(results)
                else:
                    result = harvest_article(source)
                    if result:
                        total_insights += 1
                
                harvest_log["sources_processed"] += 1
                
            except Exception as e:
                print(f"  ❌ Error processing {source['name']}: {e}")
                harvest_log["errors"].append(str(e))
    
    harvest_log["insights_extracted"] = total_insights
    log_harvest(harvest_log)
    
    # Compile summary
    print("\n" + "=" * 60)
    print("📊 COMPILING KNOWLEDGE SUMMARY")
    print("=" * 60)
    
    summary = compile_knowledge_summary()
    if summary:
        summary_file = DATA_DIR / "knowledge_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"✅ Summary saved: {len(summary.get('key_insights', []))} insights compiled")
    
    print("\n" + "=" * 60)
    print(f"✅ HARVEST COMPLETE")
    print(f"   Total insights: {total_insights}")
    print(f"   Knowledge base: {KNOWLEDGE_FILE}")
    print("=" * 60)
    
    return total_insights


if __name__ == "__main__":
    run_harvest()
