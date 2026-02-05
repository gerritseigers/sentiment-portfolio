#!/usr/bin/env python3
"""
Ollama-based Portfolio Selection Module
Uses LLM to select assets within each sector based on sentiment and market conditions.

Each sector has its own prompt that evolves based on performance.
"""

import json
import urllib.request
import urllib.error
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_PROMPTS_FILE = os.path.join(BASE_DIR, 'portfolio_prompts.json')
SECTOR_ASSETS_FILE = os.path.join(BASE_DIR, 'sector_assets.json')
HISTORY_DIR = os.path.join(BASE_DIR, 'data', 'portfolio_prompt_history')

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.2:3b"  # Can upgrade to larger model for better reasoning


def load_portfolio_prompts() -> Dict:
    """Load portfolio selection prompts"""
    if os.path.exists(PORTFOLIO_PROMPTS_FILE):
        with open(PORTFOLIO_PROMPTS_FILE) as f:
            return json.load(f)
    return {"prompts": {}, "base_system_prompt": ""}


def save_portfolio_prompts(data: Dict) -> None:
    """Save portfolio prompts"""
    with open(PORTFOLIO_PROMPTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def load_sector_assets() -> Dict:
    """Load available assets per sector"""
    if os.path.exists(SECTOR_ASSETS_FILE):
        with open(SECTOR_ASSETS_FILE) as f:
            return json.load(f)
    return {"sectors": {}}


def get_portfolio_prompt(sector: str) -> str:
    """Get the full portfolio selection prompt for a sector"""
    data = load_portfolio_prompts()
    base = data.get('base_system_prompt', '')
    
    if sector not in data.get('prompts', {}):
        return base.format(
            sector_name=sector,
            sector_specific_prompt="Select assets based on sentiment and diversification principles."
        )
    
    sector_data = data['prompts'][sector]
    return base.format(
        sector_name=sector_data.get('sector_name', sector),
        sector_specific_prompt=sector_data.get('current_prompt', '')
    )


def get_sector_stocks(sector: str) -> List[Dict]:
    """Get available stocks for a sector"""
    assets = load_sector_assets()
    if sector in assets.get('sectors', {}):
        return assets['sectors'][sector].get('stocks', [])
    return []


def select_assets(
    sector: str,
    sentiment_score: float,
    scenario: str = "benchmark",
    budget: float = 10000,
    timeout: int = 60
) -> Optional[Dict]:
    """
    Use Ollama to select assets for a sector based on sentiment.
    
    Args:
        sector: Sector code (XLK, XLF, etc.)
        sentiment_score: Current sentiment (-1.0 to +1.0)
        scenario: Trading scenario (aggressive, defensive, momentum, contrarian, benchmark)
        budget: Amount to allocate in this sector
        timeout: Request timeout
        
    Returns:
        Dict with selected_assets, rationale, risk_level
    """
    system_prompt = get_portfolio_prompt(sector)
    stocks = get_sector_stocks(sector)
    
    if not stocks:
        print(f"⚠️ No stocks found for sector {sector}")
        return None
    
    # Format stock list for prompt
    stock_list = "\n".join([
        f"- {s['ticker']}: {s['name']} ({s.get('focus', 'general')}, {s.get('market_cap', 'unknown')} cap)"
        for s in stocks
    ])
    
    # Determine sentiment description
    if sentiment_score > 0.3:
        sentiment_desc = "BULLISH"
    elif sentiment_score < -0.3:
        sentiment_desc = "BEARISH"
    else:
        sentiment_desc = "NEUTRAL"
    
    # Build user prompt
    user_prompt = f"""Current conditions:
- Sector: {sector}
- Sentiment Score: {sentiment_score:+.2f} ({sentiment_desc})
- Scenario: {scenario}
- Budget: ${budget:,.0f}

Available assets:
{stock_list}

Select the best assets for this scenario. Return valid JSON only."""

    payload = json.dumps({
        "model": MODEL,
        "prompt": user_prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,  # Slightly higher for creative allocation
            "num_predict": 500  # Enough for JSON response
        }
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            response_text = result.get('response', '').strip()
            
            # Try to extract JSON from response
            parsed = parse_portfolio_response(response_text, stocks, budget)
            if parsed:
                parsed['sector'] = sector
                parsed['sentiment_score'] = sentiment_score
                parsed['scenario'] = scenario
                parsed['timestamp'] = datetime.now().isoformat()
                return parsed
            
            print(f"⚠️ Could not parse response for {sector}")
            return None
            
    except Exception as e:
        print(f"Ollama portfolio error for {sector}: {e}")
        return None


def parse_portfolio_response(response: str, available_stocks: List[Dict], budget: float) -> Optional[Dict]:
    """Parse the LLM response and extract portfolio allocation"""
    
    # Try to find JSON in response
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            
            # Validate and normalize the response
            selected = data.get('selected_assets', [])
            
            # Ensure weights sum to 1.0
            total_weight = sum(a.get('weight', 0) for a in selected)
            if total_weight > 0:
                for asset in selected:
                    asset['weight'] = asset.get('weight', 0) / total_weight
                    asset['amount'] = round(asset['weight'] * budget, 2)
            
            # Filter to valid tickers only
            valid_tickers = {s['ticker'] for s in available_stocks}
            selected = [a for a in selected if a.get('ticker') in valid_tickers]
            
            return {
                'selected_assets': selected,
                'rationale': data.get('rationale', 'No rationale provided'),
                'risk_level': data.get('risk_level', 'medium')
            }
        except json.JSONDecodeError:
            pass
    
    # Fallback: try to extract tickers mentioned
    valid_tickers = {s['ticker'] for s in available_stocks}
    mentioned = [t for t in valid_tickers if t in response.upper()]
    
    if mentioned:
        weight = 1.0 / len(mentioned)
        return {
            'selected_assets': [
                {'ticker': t, 'weight': weight, 'amount': round(weight * budget, 2), 'reason': 'mentioned in response'}
                for t in mentioned[:5]  # Max 5
            ],
            'rationale': 'Extracted from unstructured response',
            'risk_level': 'medium'
        }
    
    return None


def select_portfolio_for_all_sectors(
    sector_sentiments: Dict[str, float],
    scenario: str = "benchmark",
    total_budget: float = 50000
) -> Dict:
    """
    Select assets for all sectors based on their sentiments.
    
    Args:
        sector_sentiments: Dict of sector -> sentiment score
        scenario: Trading scenario
        total_budget: Total amount to allocate
        
    Returns:
        Dict with allocations per sector
    """
    num_sectors = len(sector_sentiments)
    budget_per_sector = total_budget / num_sectors if num_sectors > 0 else 0
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'scenario': scenario,
        'total_budget': total_budget,
        'sectors': {}
    }
    
    for sector, sentiment in sector_sentiments.items():
        print(f"📊 Selecting assets for {sector} (sentiment: {sentiment:+.2f})...")
        
        allocation = select_assets(
            sector=sector,
            sentiment_score=sentiment,
            scenario=scenario,
            budget=budget_per_sector
        )
        
        if allocation:
            results['sectors'][sector] = allocation
        else:
            # Fallback to ETF only
            results['sectors'][sector] = {
                'selected_assets': [{'ticker': sector, 'weight': 1.0, 'amount': budget_per_sector, 'reason': 'fallback to ETF'}],
                'rationale': 'LLM selection failed, defaulting to sector ETF',
                'risk_level': 'low'
            }
    
    return results


def record_portfolio_performance(sector: str, was_correct: bool) -> None:
    """Record whether a portfolio selection was correct"""
    data = load_portfolio_prompts()
    
    if sector not in data.get('prompts', {}):
        return
    
    perf = data['prompts'][sector].get('performance', {'correct': 0, 'total': 0})
    perf['total'] = perf.get('total', 0) + 1
    if was_correct:
        perf['correct'] = perf.get('correct', 0) + 1
    perf['accuracy'] = (perf['correct'] / perf['total'] * 100) if perf['total'] > 0 else 0
    
    data['prompts'][sector]['performance'] = perf
    save_portfolio_prompts(data)


def log_portfolio_prompt_change(sector: str, old_prompt: str, new_prompt: str, reason: str, performance: Dict) -> None:
    """Log a portfolio prompt change to history"""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    
    history_file = os.path.join(HISTORY_DIR, f'{sector}.jsonl')
    
    data = load_portfolio_prompts()
    version = data['prompts'].get(sector, {}).get('version', 1)
    
    entry = {
        'timestamp': datetime.now().isoformat(),
        'version_before': version,
        'version_after': version + 1,
        'old_prompt': old_prompt,
        'new_prompt': new_prompt,
        'reason': reason,
        'performance_at_change': performance
    }
    
    with open(history_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    
    print(f"📝 Logged portfolio prompt change for {sector}")


def update_portfolio_prompt(sector: str, new_prompt: str, reason: str) -> bool:
    """Update a sector's portfolio selection prompt"""
    data = load_portfolio_prompts()
    
    if sector not in data.get('prompts', {}):
        print(f"⚠️ Sector {sector} not found")
        return False
    
    sector_data = data['prompts'][sector]
    old_prompt = sector_data.get('current_prompt', '')
    performance = sector_data.get('performance', {})
    
    log_portfolio_prompt_change(sector, old_prompt, new_prompt, reason, performance)
    
    sector_data['current_prompt'] = new_prompt
    sector_data['version'] = sector_data.get('version', 1) + 1
    sector_data['last_modified'] = datetime.now().isoformat()
    
    data['prompts'][sector] = sector_data
    save_portfolio_prompts(data)
    
    print(f"✅ Updated {sector} portfolio prompt to v{sector_data['version']}")
    return True


def get_underperforming_portfolio_prompts(threshold: float = 50.0, min_selections: int = 10) -> List:
    """Get sectors with underperforming portfolio selection prompts"""
    data = load_portfolio_prompts()
    underperf = []
    
    for sector, sdata in data.get('prompts', {}).items():
        perf = sdata.get('performance', {})
        total = perf.get('total', 0)
        accuracy = perf.get('accuracy', 0)
        
        if total >= min_selections and accuracy < threshold:
            underperf.append({
                'sector': sector,
                'accuracy': accuracy,
                'total': total,
                'current_prompt': sdata.get('current_prompt', '')[:100] + '...'
            })
    
    return sorted(underperf, key=lambda x: x['accuracy'])


def generate_portfolio_report() -> str:
    """Generate a report of portfolio prompt performance"""
    data = load_portfolio_prompts()
    lines = []
    
    lines.append("# 📈 Portfolio Selection Prompt Report")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    
    for sector, sdata in sorted(data.get('prompts', {}).items()):
        perf = sdata.get('performance', {})
        version = sdata.get('version', 1)
        accuracy = perf.get('accuracy', 0)
        total = perf.get('total', 0)
        
        emoji = '🟢' if accuracy >= 60 else ('🟡' if accuracy >= 45 else '🔴')
        
        lines.append(f"## {emoji} {sector} - {sdata.get('sector_name', '')} (v{version})")
        lines.append(f"- Selection Accuracy: {accuracy:.1f}% ({perf.get('correct', 0)}/{total})")
        lines.append(f"- Last modified: {sdata.get('last_modified', 'never')[:10]}")
        lines.append("")
    
    return '\n'.join(lines)


# === Test Functions ===

def test_connection():
    """Test if Ollama is running"""
    try:
        payload = json.dumps({
            "model": MODEL,
            "prompt": "Say OK",
            "stream": False
        }).encode('utf-8')
        
        req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            print("✓ Ollama connected")
            return True
    except Exception as e:
        print(f"✗ Ollama connection failed: {e}")
        return False


def test_portfolio_selection():
    """Test portfolio selection for a few sectors"""
    print("\n🔬 Testing portfolio selection...\n")
    
    test_cases = [
        ("XLK", 0.6, "aggressive"),   # Bullish tech
        ("XLF", -0.4, "defensive"),   # Bearish financials  
        ("CRYPTO", 0.8, "momentum"),  # Very bullish crypto
    ]
    
    for sector, sentiment, scenario in test_cases:
        print(f"\n{'='*50}")
        print(f"Sector: {sector} | Sentiment: {sentiment:+.2f} | Scenario: {scenario}")
        print('='*50)
        
        result = select_assets(sector, sentiment, scenario, budget=10000)
        
        if result:
            print(f"\n📊 Selected Assets:")
            for asset in result.get('selected_assets', []):
                print(f"  • {asset['ticker']}: {asset['weight']*100:.0f}% (${asset['amount']:,.0f}) - {asset.get('reason', 'n/a')}")
            print(f"\n📝 Rationale: {result.get('rationale', 'n/a')}")
            print(f"⚠️ Risk Level: {result.get('risk_level', 'n/a')}")
        else:
            print("❌ Selection failed")


if __name__ == "__main__":
    print("Portfolio Selection Module")
    print(f"Model: {MODEL}")
    print(f"Prompts file: {PORTFOLIO_PROMPTS_FILE}")
    
    if not test_connection():
        print("\nMake sure Ollama is running: ollama serve")
        exit(1)
    
    test_portfolio_selection()
    
    print("\n" + "="*50)
    print("PORTFOLIO PROMPT REPORT:")
    print("="*50)
    print(generate_portfolio_report())
