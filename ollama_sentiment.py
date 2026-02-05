#!/usr/bin/env python3
"""
Ollama-based Sentiment Analysis Module
Uses llama3.1:8b for accurate financial sentiment scoring

Now with SECTOR-SPECIFIC PROMPTS that evolve during training!
Each sector has its own prompt optimized for that domain.
"""

import json
import urllib.request
import urllib.error
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

# Import prompt evolution for sector-specific prompts
try:
    from prompt_evolution import get_prompt_for_sector, get_sector_keywords
    HAS_EVOLUTION = True
except ImportError:
    HAS_EVOLUTION = False
    print("⚠️ prompt_evolution not available, using generic prompts")

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "llama3.1:8b"

# Fallback generic prompt (used if no sector specified)
GENERIC_SYSTEM_PROMPT = """You are a financial sentiment analyzer. Rate the sentiment of news headlines on a scale from -1.0 (very bearish/negative) to +1.0 (very bullish/positive).

Guidelines:
- Headlines about price increases, earnings beats, upgrades, deals → positive (0.3 to 1.0)
- Headlines about price drops, layoffs, lawsuits, downgrades → negative (-1.0 to -0.3)
- Neutral news, mixed signals, routine updates → near zero (-0.2 to 0.2)

RESPOND WITH ONLY A NUMBER between -1.0 and 1.0. No explanation."""


def get_system_prompt(sector: str = None) -> str:
    """Get the appropriate system prompt - sector-specific or generic"""
    if sector and HAS_EVOLUTION:
        return get_prompt_for_sector(sector)
    return GENERIC_SYSTEM_PROMPT


def analyze_sentiment(headline: str, sector: str = None, timeout: int = 15) -> float:
    """
    Analyze a single headline with Ollama.
    
    Args:
        headline: The news headline text
        sector: Optional sector code (XLK, XLF, etc.) for sector-specific prompt
        timeout: Request timeout in seconds
    
    Returns:
        Sentiment score from -1.0 to 1.0, or None on error
    """
    system_prompt = get_system_prompt(sector)
    
    prompt = f"Rate the financial sentiment of this headline:\n\n\"{headline}\"\n\nScore (-1.0 to +1.0):"
    
    payload = json.dumps({
        "model": MODEL,
        "prompt": prompt,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 10
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
            response_text = result.get('response', '0').strip()
            
            # Parse the number from response
            match = re.search(r'[-+]?\d*\.?\d+', response_text)
            if match:
                score = float(match.group())
                return max(min(score, 1.0), -1.0)  # Clamp to [-1, 1]
            return 0.0
            
    except Exception as e:
        print(f"Ollama error for '{headline[:50]}...': {e}")
        return None


def batch_analyze(headlines, sectors=None, max_workers=4, fallback_fn=None):
    """
    Analyze multiple headlines in parallel with sector-specific prompts.
    
    Args:
        headlines: List of headline strings or dicts with 'title' and optionally 'sectors' keys
        sectors: Optional dict mapping headline index to sector code, or single sector for all
        max_workers: Parallel workers (careful with Ollama memory)
        fallback_fn: Function to call if Ollama fails (e.g., keyword-based)
    
    Returns:
        List of sentiment scores (same order as input)
    """
    results = [None] * len(headlines)
    
    def get_title(h):
        return h['title'] if isinstance(h, dict) else h
    
    def get_sector(h, idx):
        # Priority: headline dict > sectors param > None
        if isinstance(h, dict) and h.get('sectors'):
            # Use first sector if multiple
            s = h['sectors']
            return s[0] if isinstance(s, list) else s
        if isinstance(sectors, dict):
            return sectors.get(idx)
        if isinstance(sectors, str):
            return sectors
        return None
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {
            executor.submit(
                analyze_sentiment, 
                get_title(h), 
                get_sector(h, i)
            ): i 
            for i, h in enumerate(headlines)
        }
        
        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                score = future.result()
                if score is not None:
                    results[idx] = score
                elif fallback_fn:
                    results[idx] = fallback_fn(get_title(headlines[idx]))
            except Exception as e:
                if fallback_fn:
                    results[idx] = fallback_fn(get_title(headlines[idx]))
            
            completed += 1
            if completed % 50 == 0:
                print(f"   Analyzed {completed}/{len(headlines)} headlines...")
    
    return results


def batch_analyze_by_sector(headlines_by_sector: dict, max_workers=4, fallback_fn=None):
    """
    Analyze headlines grouped by sector - most efficient for sector-specific prompts.
    
    Args:
        headlines_by_sector: Dict of sector -> list of headlines
            Example: {'XLK': ['Apple earnings...', 'Microsoft...'], 'XLF': ['Fed rate...']}
    
    Returns:
        Dict of sector -> list of scores
    """
    results = {}
    
    for sector, headlines in headlines_by_sector.items():
        print(f"📊 Analyzing {len(headlines)} headlines for {sector}...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(analyze_sentiment, h, sector)
                for h in headlines
            ]
            
            sector_results = []
            for future in as_completed(futures):
                try:
                    score = future.result()
                    sector_results.append(score if score is not None else 0.0)
                except Exception:
                    sector_results.append(0.0 if not fallback_fn else fallback_fn(headlines[len(sector_results)]))
        
        results[sector] = sector_results
    
    return results


def test_connection():
    """Test if Ollama is running and model is available"""
    try:
        score = analyze_sentiment("Apple stock surges 10% after record earnings", timeout=30)
        if score is not None:
            print(f"✓ Ollama connected. Test sentiment: {score:+.2f}")
            return True
    except Exception as e:
        print(f"✗ Ollama connection failed: {e}")
    return False


def test_sector_prompts():
    """Test that sector-specific prompts are working"""
    print("\n🔬 Testing sector-specific prompts...")
    
    test_cases = [
        ("XLK", "NVIDIA announces breakthrough AI chip with 50% better performance"),
        ("XLF", "Federal Reserve signals three rate cuts expected in 2025"),
        ("XLE", "OPEC+ agrees to extend oil production cuts through Q2"),
        ("CRYPTO", "SEC approves spot Ethereum ETF applications"),
        ("XLV", "FDA grants fast-track approval for new cancer treatment"),
    ]
    
    for sector, headline in test_cases:
        score = analyze_sentiment(headline, sector=sector)
        emoji = "🟢" if score and score > 0.2 else ("🔴" if score and score < -0.2 else "🟡")
        prompt_type = "sector" if HAS_EVOLUTION else "generic"
        print(f"  {emoji} [{sector}] {score:+.2f} ({prompt_type}) | {headline[:50]}...")


if __name__ == "__main__":
    print("Testing Ollama sentiment analysis with sector-specific prompts...")
    print(f"Sector prompts available: {HAS_EVOLUTION}")
    
    if not test_connection():
        print("Make sure Ollama is running: ollama serve")
        exit(1)
    
    # Test generic headlines
    test_headlines = [
        "Apple shares surge 8% on record iPhone sales",
        "Tesla stock plunges amid production concerns",
        "Fed signals potential rate cuts in 2025",
        "Microsoft announces $10B AI partnership",
        "Bank of America cuts 3,000 jobs in restructuring",
    ]
    
    print(f"\n📰 Generic analysis ({len(test_headlines)} headlines):\n")
    
    for headline in test_headlines:
        score = analyze_sentiment(headline)
        emoji = "🟢" if score > 0.2 else ("🔴" if score < -0.2 else "🟡")
        print(f"{emoji} {score:+.2f} | {headline[:60]}")
    
    # Test sector-specific
    test_sector_prompts()
