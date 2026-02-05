#!/usr/bin/env python3
"""
News Harvester v3.0 - Comprehensive US Market Coverage
197 RSS feeds + 61 web scrape sources = 258 total sources
"""

import json
import os
import re
import ssl
import time
from datetime import datetime
from urllib.request import urlopen, Request
from xml.etree import ElementTree
from html.parser import HTMLParser
from concurrent.futures import ThreadPoolExecutor, as_completed

ssl._create_default_https_context = ssl._create_unverified_context

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

class SimpleHTMLParser(HTMLParser):
    """Extract text from HTML"""
    def __init__(self):
        super().__init__()
        self.text = []
        self.in_script = False
        self.in_style = False
        
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
    with open(os.path.join(BASE_DIR, 'news_sources.json')) as f:
        return json.load(f)

def fetch_rss(feed, timeout=8):
    """Fetch and parse RSS feed"""
    headlines = []
    try:
        req = Request(feed['url'], headers=HEADERS)
        with urlopen(req, timeout=timeout) as response:
            content = response.read()
            tree = ElementTree.fromstring(content)
            
            # Handle RSS 2.0, Atom, and RDF formats
            items = (tree.findall('.//item') or 
                    tree.findall('.//{http://www.w3.org/2005/Atom}entry') or
                    tree.findall('.//{http://purl.org/rss/1.0/}item'))
            
            for item in items[:15]:
                title = (item.find('title') or 
                        item.find('{http://www.w3.org/2005/Atom}title') or
                        item.find('{http://purl.org/rss/1.0/}title'))
                
                if title is not None and title.text:
                    text = title.text.strip()
                    if len(text) > 10:  # Filter out too short titles
                        headlines.append({
                            'title': text[:200],
                            'source': feed['name'],
                            'type': 'rss'
                        })
        return headlines, True
    except Exception as e:
        return [], False

def fetch_webpage(site, timeout=10):
    """Fetch webpage and extract headlines via simple pattern matching"""
    headlines = []
    try:
        req = Request(site['url'], headers=HEADERS)
        with urlopen(req, timeout=timeout) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
            # Simple headline extraction - look for common patterns
            # Headlines in <h1>, <h2>, <h3>, <a> tags with meaningful text
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
    except Exception as e:
        return [], False

def classify_sectors(headline, sectors):
    """Classify headline into sectors based on keywords"""
    title_lower = headline['title'].lower()
    matched = []
    
    for sector_code, sector_info in sectors.items():
        for keyword in sector_info['keywords']:
            if keyword.lower() in title_lower:
                matched.append(sector_code)
                break
    
    return matched if matched else ['general']

def simple_sentiment(text):
    """Enhanced keyword-based sentiment analysis"""
    text_lower = text.lower()
    
    strong_positive = ['surge', 'soar', 'skyrocket', 'boom', 'breakout', 'record high', 'all-time high', 'beat expectations', 'blowout', 'massive gain']
    positive = ['rise', 'gain', 'up', 'jump', 'rally', 'climb', 'advance', 'bullish', 'optimistic', 'growth', 'profit', 'beat', 'upgrade', 'buy', 'outperform', 'strong', 'recovery', 'expand', 'success', 'boost', 'improve', 'positive', 'higher', 'increase', 'exceed', 'momentum', 'breakthrough', 'innovation', 'deal', 'partnership', 'acquisition', 'launch', 'stijg', 'winst', 'groei', 'positief']
    
    strong_negative = ['crash', 'plunge', 'collapse', 'tank', 'disaster', 'crisis', 'bankruptcy', 'fraud', 'scandal', 'all-time low', 'miss badly']
    negative = ['fall', 'drop', 'down', 'decline', 'sink', 'slip', 'bearish', 'pessimistic', 'loss', 'miss', 'cut', 'downgrade', 'sell', 'underperform', 'weak', 'warning', 'risk', 'fear', 'concern', 'worry', 'threat', 'layoff', 'recession', 'inflation', 'debt', 'default', 'lawsuit', 'investigation', 'probe', 'lower', 'decrease', 'slowdown', 'delay', 'daal', 'verlies', 'negatief', 'risico']
    
    score = 0
    for word in strong_positive:
        if word in text_lower: score += 0.4
    for word in positive:
        if word in text_lower: score += 0.15
    for word in strong_negative:
        if word in text_lower: score -= 0.4
    for word in negative:
        if word in text_lower: score -= 0.15
    
    return max(min(score, 1.0), -1.0)

def aggregate_sentiment(headlines, sectors):
    """Aggregate sentiment per sector"""
    sector_data = {code: {'headlines': [], 'scores': []} for code in sectors.keys()}
    sector_data['general'] = {'headlines': [], 'scores': []}
    
    for hl in headlines:
        sentiment = simple_sentiment(hl['title'])
        hl['sentiment'] = round(sentiment, 2)
        
        for sector in hl.get('sectors', ['general']):
            if sector in sector_data:
                sector_data[sector]['headlines'].append(hl)
                sector_data[sector]['scores'].append(sentiment)
    
    results = {}
    for sector, data in sector_data.items():
        if data['scores']:
            avg = sum(data['scores']) / len(data['scores'])
            top_headlines = sorted(data['headlines'], key=lambda x: abs(x['sentiment']), reverse=True)[:5]
            results[sector] = {
                'score': round(avg, 3),
                'count': len(data['scores']),
                'signal': 'BUY' if avg > 0.25 else ('SELL' if avg < -0.25 else 'HOLD'),
                'top_positive': [h['title'][:80] for h in top_headlines if h['sentiment'] > 0][:2],
                'top_negative': [h['title'][:80] for h in top_headlines if h['sentiment'] < 0][:2]
            }
    
    return results

def harvest_all(verbose=True):
    """Main harvest function with parallel fetching"""
    config = load_config()
    all_headlines = []
    stats = {'rss_success': 0, 'rss_fail': 0, 'web_success': 0, 'web_fail': 0}
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"📰 NEWS HARVESTER v3.0 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print(f"{'='*70}\n")
    
    # Collect all RSS feeds
    rss_feeds = []
    for category, feeds in config['rss_feeds'].items():
        for feed in feeds:
            feed['category'] = category
            rss_feeds.append(feed)
    
    if verbose:
        print(f"🔄 Harvesting {len(rss_feeds)} RSS feeds...")
    
    # Parallel RSS fetching
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
        print(f"   ✓ RSS: {stats['rss_success']} succeeded, {stats['rss_fail']} failed")
    
    # Collect web scrape sites
    if 'web_scrape' in config:
        web_sites = []
        for category, sites in config['web_scrape'].items():
            for site in sites:
                site['category'] = category
                web_sites.append(site)
        
        if verbose:
            print(f"🌐 Scraping {len(web_sites)} websites...")
        
        # Parallel web scraping
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
            print(f"   ✓ Web: {stats['web_success']} succeeded, {stats['web_fail']} failed")
    
    # Deduplicate headlines
    seen = set()
    unique_headlines = []
    for hl in all_headlines:
        key = hl['title'][:50].lower()
        if key not in seen:
            seen.add(key)
            unique_headlines.append(hl)
    
    if verbose:
        print(f"\n📊 Processing {len(unique_headlines)} unique headlines...")
    
    # Classify sectors
    sectors = config.get('us_sectors', {})
    for hl in unique_headlines:
        hl['sectors'] = classify_sectors(hl, sectors)
    
    # Calculate sentiment
    sector_sentiment = aggregate_sentiment(unique_headlines, sectors)
    sorted_sectors = sorted(sector_sentiment.items(), key=lambda x: x[1]['score'], reverse=True)
    
    # Build report
    report = {
        'timestamp': datetime.now().isoformat(),
        'stats': {
            'total_headlines': len(unique_headlines),
            'rss_feeds_success': stats['rss_success'],
            'rss_feeds_failed': stats['rss_fail'],
            'web_scrape_success': stats['web_success'],
            'web_scrape_failed': stats['web_fail'],
            'sources_total': stats['rss_success'] + stats['web_success']
        },
        'sector_sentiment': sector_sentiment,
        'rankings': {
            'bullish': [s[0] for s in sorted_sectors[:3] if s[1]['score'] > 0.1],
            'bearish': [s[0] for s in sorted_sectors if s[1]['score'] < -0.1][-3:]
        },
        'headlines': unique_headlines
    }
    
    # Save report
    today = datetime.now().strftime('%Y-%m-%d')
    hour = datetime.now().strftime('%H')
    output_dir = os.path.join(BASE_DIR, 'data', 'harvests', today)
    os.makedirs(output_dir, exist_ok=True)
    
    output_file = os.path.join(output_dir, f'harvest_{hour}00.json')
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Also save latest
    latest_file = os.path.join(BASE_DIR, 'data', 'latest_harvest.json')
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
                print(f"{emoji} {sector:6} {name:20} | {data['score']:+.3f} | {data['signal']:4} | {data['count']:4} articles")
        
        print(f"\n📁 Saved: {output_file}")
        print(f"📊 Total: {len(unique_headlines)} headlines from {report['stats']['sources_total']} sources")
    
    return report

if __name__ == '__main__':
    harvest_all()
