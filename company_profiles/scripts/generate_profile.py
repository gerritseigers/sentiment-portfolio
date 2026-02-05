#!/usr/bin/env python3
"""
Generate Company Profile using Ollama
Creates a structured profile for RAG-enhanced sentiment analysis
"""

import json
import os
import urllib.request
from datetime import datetime
from typing import Dict, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(BASE_DIR, 'profiles')
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"

PROFILE_TEMPLATE = """Generate a company profile for {ticker} ({name}) in JSON format.

The profile should include:
- summary: 2-3 sentences about what the company does
- business_model: How they make money (1 sentence)
- key_products: List of 3-5 main products/services
- competitors: List of 3-5 main competitors
- market_position: Their position in the market (1 sentence)
- risks: List of 3-5 key business risks
- catalysts: List of 3-5 potential positive catalysts
- sentiment_keywords: List of 5-10 keywords that indicate news about this company

Respond with ONLY valid JSON, no explanation. Example format:
{{
  "summary": "...",
  "business_model": "...",
  "key_products": ["...", "..."],
  "competitors": ["...", "..."],
  "market_position": "...",
  "risks": ["...", "..."],
  "catalysts": ["...", "..."],
  "sentiment_keywords": ["...", "..."]
}}"""


def generate_profile_with_ollama(ticker: str, name: str, sector: str) -> Optional[Dict]:
    """Use Ollama to generate a company profile"""
    
    prompt = PROFILE_TEMPLATE.format(ticker=ticker, name=name)
    
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 800
        }
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            response = result.get('response', '')
            
            # Try to parse JSON from response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                profile_data = json.loads(json_match.group())
                
                # Add metadata
                profile_data['ticker'] = ticker
                profile_data['name'] = name
                profile_data['sector'] = sector
                profile_data['updated'] = datetime.now().isoformat()[:10]
                profile_data['recent_events'] = []
                
                return profile_data
                
    except Exception as e:
        print(f"Error generating profile for {ticker}: {e}")
    
    return None


def save_profile(profile: Dict) -> str:
    """Save profile to JSON file"""
    os.makedirs(PROFILES_DIR, exist_ok=True)
    
    filepath = os.path.join(PROFILES_DIR, f"{profile['ticker']}.json")
    with open(filepath, 'w') as f:
        json.dump(profile, f, indent=2)
    
    return filepath


def load_profile(ticker: str) -> Optional[Dict]:
    """Load existing profile"""
    filepath = os.path.join(PROFILES_DIR, f"{ticker}.json")
    if os.path.exists(filepath):
        with open(filepath) as f:
            return json.load(f)
    return None


def generate_all_profiles(sector_assets_path: str, limit: int = None) -> None:
    """Generate profiles for all companies in sector_assets.json"""
    
    with open(sector_assets_path) as f:
        data = json.load(f)
    
    count = 0
    for sector, info in data.get('sectors', {}).items():
        for stock in info.get('stocks', []):
            ticker = stock['ticker']
            name = stock['name']
            
            # Skip if profile exists
            if load_profile(ticker):
                print(f"⏭️  {ticker}: Profile exists, skipping")
                continue
            
            print(f"🔄 Generating profile for {ticker} ({name})...")
            profile = generate_profile_with_ollama(ticker, name, sector)
            
            if profile:
                filepath = save_profile(profile)
                print(f"✅ {ticker}: Saved to {filepath}")
                count += 1
            else:
                print(f"❌ {ticker}: Failed to generate")
            
            if limit and count >= limit:
                print(f"\n⏹️  Reached limit of {limit} profiles")
                return
    
    print(f"\n✅ Generated {count} new profiles")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        # Generate single profile
        ticker = sys.argv[1].upper()
        name = sys.argv[2] if len(sys.argv) > 2 else ticker
        sector = sys.argv[3] if len(sys.argv) > 3 else "unknown"
        
        print(f"Generating profile for {ticker}...")
        profile = generate_profile_with_ollama(ticker, name, sector)
        
        if profile:
            filepath = save_profile(profile)
            print(f"✅ Saved to {filepath}")
            print(json.dumps(profile, indent=2))
        else:
            print("❌ Failed to generate profile")
    else:
        print("Usage:")
        print("  python generate_profile.py AAPL 'Apple Inc.' XLK")
        print("  python generate_profile.py --all  # Generate all profiles")
