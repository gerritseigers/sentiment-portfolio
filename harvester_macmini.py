#!/usr/bin/env python3
"""
News Harvester v4.0 - With Ollama LLM Sentiment Analysis
Runs on MacMini with llama3.1:8b for accurate sentiment scoring
"""

import json
import os
import re
import ssl
import time
import urllib.request
import urllib.error
from datetime import datetime
from xml.etree import ElementTree
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed

ssl._create_default_https_context = ssl._create_unverified_context

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

# Ollama settings
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"
USE_OLLAMA = True  # Set to False to fall back to keyword-based

SENTIMENT_PROMPT = """Rate the financial/market sentiment of this news headline.
Score from -1.0 (very bearish/negative) to +1.0 (very bullish/positive).
RESPOND WITH ONLY A NUMBER. No explanation.

Headline: "{headline}"

Score:"""

class SimpleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.in_script = False
        
    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.in_script = True
    
    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.in_script = False
            
    def handle_data(self, data):
        if not self.in_script:
            self.text.append(data.strip())
    
    def get_text(self):
        return ' '.join(filter(None, self.text))


def load_config():
    """Load news sources configuration"""
    config_path = os.path.join(BASE_DIR, 'news_sources.json')
    with open(config_path) as f:
        return json.load(f)


def fetch_rss(feed, timeout=8):
    """Fetch and parse RSS feed"""
    headlines = []
    try:
        req = urllib.request.Request(feed['url'], headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            content = response.read()
            tree = ElementTree.fromstring(content)
            
            items = (tree.findall('.//item') or 
                    tree.findall('.//{http://www.w3.org/2005/Atom}entry') or
                    tree.findall('.//{http://purl.org/rss/1.0/}item'))
            
            for item in items[:15]:
                title = (item.find('title') or 
                        item.find('{http://www.w3.org/2005/Atom}title') or
                        item.find('{http://purl.org/rss/1.0/}title'))
                
                if title is not None and title.text:
                    text = title.text.strip()
                    if len(text) > 10:
                        headlines.append({
                            'title': text[:200],
                            'source': feed['name'],
                            'type': 'rss'
                        })
        return headlines, True
    except Exception:
        return [], False


def fetch_webpage(site, timeout=10):
    """Fetch webpage and extract headlines"""
    headlines = []
    try:
        req = urllib.request.Request(site['url'], headers=HEADERS)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            patterns = [
                r'<h[123][^>]*>([^<]{20,150})</h[123]>',
                r'<a[^>]*>([^<]{25,150})</a>',
                r'"headline"[^>]*>([^<]{20,150})<',
                r'title="([^"]{25,150})"',
            ]
            
            found = set()
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches[:10]:
                    text = re.sub(r'<[^>]+>', '', match).strip()
                    text = re.sub(r'\s+', ' ', text)
                    if len(text) > 20 and text not in found:
                        found.add(text)
                        headlines.append({
                            'title': text[:200],
                            'source': site['name'],
                            'type': 'web'
                        })
            
        return headlines[:10], True
    except Exception:
        return [], False


def ollama_sentiment(headline, timeout=20):
    """Get sentiment score from Ollama"""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": SENTIMENT_PROMPT.format(headline=headline),
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 10}
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            response_text = result.get('response', '0').strip()
            
            match = re.search(r'[-+]?\d*\.?\d+', response_text)
            if match:
                score = float(match.group())
                return max(min(score, 1.0), -1.0)
            return 0.0
    except Exception as e:
        return None


def keyword_sentiment(text):
    """Fallback keyword-based sentiment"""
    text_lower = text.lower()
    
    strong_pos = ['surge', 'soar', 'skyrocket', 'boom', 'record high', 'beat expectations', 'blowout']
    pos = ['rise', 'gain', 'up', 'jump', 'rally', 'climb', 'bullish', 'growth', 'profit', 'beat', 'upgrade', 'buy', 'strong', 'expand', 'boost', 'positive', 'higher', 'increase', 'breakthrough', 'deal', 'partnership', 'launch']
    
    strong_neg = ['crash', 'plunge', 'collapse', 'tank', 'disaster', 'crisis', 'bankruptcy', 'fraud', 'scandal']
    neg = ['fall', 'drop', 'down', 'decline', 'sink', 'bearish', 'loss', 'miss', 'cut', 'downgrade', 'sell', 'weak', 'warning', 'risk', 'fear', 'layoff', 'recession', 'debt', 'lawsuit', 'lower', 'decrease', 'slowdown']
    
    score = 0
    for w in strong_pos:
        if w in text_lower: score += 0.4
    for w in pos:
        if w in text_lower: score += 0.15
    for w in strong_neg:
        if w in text_lower: score -= 0.4
    for w in neg:
        if w in text_lower: score -= 0.15
    
    return max(min(score, 1.0), -1.0)


def analyze_headlines_ollama(headlines, max_workers=3):
    """Batch analyze headlines with Ollama (parallel but careful with resources)"""
    print(f"🧠 Analyzing {len(headlines)} headlines with Ollama ({OLLAMA_MODEL})...")
    
    results = {}
    failed = 0
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(ollama_sentiment, hl['title']): i 
            for i, hl in enumerate(headlines)
        }
        
        done = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                score = future.result()
                if score is not None:
                    headlines[idx]['sentiment'] = round(score, 2)
                    headlines[idx]['sentiment_source'] = 'ollama'
                else:
                    # Fallback to keyword
                    headlines[idx]['sentiment'] = round(keyword_sentiment(headlines[idx]['title']), 2)
                    headlines[idx]['sentiment_source'] = 'keyword'
                    failed += 1
            except Exception:
                headlines[idx]['sentiment'] = round(keyword_sentiment(headlines[idx]['title']), 2)
                headlines[idx]['sentiment_source'] = 'keyword'
                failed += 1
            
            done += 1
            if done % 50 == 0:
                print(f"   Progress: {done}/{len(headlines)} ({failed} fallbacks)")
    
    print(f"   ✓ Done. {len(headlines) - failed} Ollama, {failed} keyword fallback")
    return headlines


def classify_sectors(headline, sectors):
    """Classify headline into sectors"""
    title_lower = headline['title'].lower()
    matched = []
    
    for sector_code, sector_info in sectors.items():
        for keyword in sector_info.get('keywords', []):
            if keyword.lower() in title_lower:
                matched.append(sector_code)
                break
    
    return matched if matched else ['general']


def aggregate_sentiment(headlines, sectors):
    """Aggregate sentiment per sector"""
    sector_data = {code: {'headlines': [], 'scores': []} for code in sectors.keys()}
    sector_data['general'] = {'headlines': [], 'scores': []}
    
    for hl in headlines:
        sentiment = hl.get('sentiment', 0)
        for sector in hl.get('sectors', ['general']):
            if sector in sector_data:
                sector_data[sector]['headlines'].append(hl)
                sector_data[sector]['scores'].append(sentiment)
    
    results = {}
    for sector, data in sector_data.items():
        if data['scores']:
            avg = sum(data['scores']) / len(data['scores'])
            top = sorted(data['headlines'], key=lambda x: abs(x.get('sentiment', 0)), reverse=True)[:5]
            results[sector] = {
                'score': round(avg, 3),
                'count': len(data['scores']),
                'signal': 'BUY' if avg > 0.25 else ('SELL' if avg < -0.25 else 'HOLD'),
                'top_positive': [h['title'][:80] for h in top if h.get('sentiment', 0) > 0][:2],
                'top_negative': [h['title'][:80] for h in top if h.get('sentiment', 0) < 0][:2]
            }
    
    return results


def harvest_all(verbose=True):
    """Main harvest function"""
    config = load_config()
    all_headlines = []
    stats = {'rss_success': 0, 'rss_fail': 0, 'web_success': 0, 'web_fail': 0}
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"📰 NEWS HARVESTER v4.0 + OLLAMA - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}\n")
    
    # Collect RSS feeds
    rss_feeds = []
    for category, feeds in config.get('rss_feeds', {}).items():
        for feed in feeds:
            feed['category'] = category
            rss_feeds.append(feed)
    
    if verbose:
        print(f"🔄 Harvesting {len(rss_feeds)} RSS feeds...")
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(fetch_rss, feed): feed for feed in rss_feeds}
        for future in as_completed(futures):
            headlines, success = future.result()
            if success:
                stats['rss_success'] += 1
                all_headlines.extend(headlines)
            else:
                stats['rss_fail'] += 1
    
    if verbose:
        print(f"   ✓ RSS: {stats['rss_success']} ok, {stats['rss_fail']} failed")
    
    # Web scraping
    if 'web_scrape' in config:
        web_sites = []
        for category, sites in config['web_scrape'].items():
            for site in sites:
                site['category'] = category
                web_sites.append(site)
        
        if verbose:
            print(f"🌐 Scraping {len(web_sites)} websites...")
        
        with ThreadPoolExecutor(max_workers=15) as executor:
            futures = {executor.submit(fetch_webpage, site): site for site in web_sites}
            for future in as_completed(futures):
                headlines, success = future.result()
                if success:
                    stats['web_success'] += 1
                    all_headlines.extend(headlines)
                else:
                    stats['web_fail'] += 1
        
        if verbose:
            print(f"   ✓ Web: {stats['web_success']} ok, {stats['web_fail']} failed")
    
    # Deduplicate
    seen = set()
    unique = []
    for hl in all_headlines:
        key = hl['title'][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(hl)
    
    if verbose:
        print(f"\n📊 {len(unique)} unique headlines")
    
    # Sector classification
    sectors = config.get('us_sectors', {})
    for hl in unique:
        hl['sectors'] = classify_sectors(hl, sectors)
    
    # Sentiment analysis (Ollama or keyword)
    if USE_OLLAMA:
        unique = analyze_headlines_ollama(unique)
    else:
        for hl in unique:
            hl['sentiment'] = round(keyword_sentiment(hl['title']), 2)
            hl['sentiment_source'] = 'keyword'
    
    # Aggregate
    sector_sentiment = aggregate_sentiment(unique, sectors)
    sorted_sectors = sorted(sector_sentiment.items(), key=lambda x: x[1]['score'], reverse=True)
    
    # Build report
    ollama_count = sum(1 for h in unique if h.get('sentiment_source') == 'ollama')
    report = {
        'timestamp': datetime.now().isoformat(),
        'stats': {
            'total_headlines': len(unique),
            'rss_feeds_success': stats['rss_success'],
            'rss_feeds_failed': stats['rss_fail'],
            'web_scrape_success': stats['web_success'],
            'web_scrape_failed': stats['web_fail'],
            'sources_total': stats['rss_success'] + stats['web_success'],
            'ollama_analyzed': ollama_count,
            'keyword_fallback': len(unique) - ollama_count
        },
        'sector_sentiment': sector_sentiment,
        'rankings': {
            'bullish': [s[0] for s in sorted_sectors[:3] if s[1]['score'] > 0.1],
            'bearish': [s[0] for s in sorted_sectors if s[1]['score'] < -0.1][-3:]
        },
        'headlines': unique
    }
    
    # Save
    os.makedirs(DATA_DIR, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    hour = datetime.now().strftime('%H')
    
    harvest_dir = os.path.join(DATA_DIR, 'harvests', today)
    os.makedirs(harvest_dir, exist_ok=True)
    
    output_file = os.path.join(harvest_dir, f'harvest_{hour}00.json')
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    latest_file = os.path.join(DATA_DIR, 'latest_harvest.json')
    with open(latest_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    if verbose:
        print(f"\n{'='*70}")
        print("📈 SECTOR SENTIMENT RANKINGS")
        print(f"{'='*70}")
        
        for sector, data in sorted_sectors:
            if data['count'] > 0:
                if data['score'] > 0.2:
                    emoji = '🟢🔥'
                elif data['score'] > 0:
                    emoji = '🟢'
                elif data['score'] < -0.2:
                    emoji = '🔴⚠️'
                elif data['score'] < 0:
                    emoji = '🔴'
                else:
                    emoji = '🟡'
                
                name = sectors.get(sector, {}).get('name', sector)[:20]
                print(f"{emoji} {sector:6} {name:20} | {data['score']:+.3f} | {data['signal']:4} | {data['count']:3} headlines")
        
        print(f"\n📁 Saved: {output_file}")
        print(f"🧠 Sentiment: {ollama_count} Ollama / {len(unique)-ollama_count} keyword")
    
    return report


if __name__ == '__main__':
    harvest_all()
