#!/usr/bin/env python3
"""
LLM-based Sentiment Analysis
Prepares headlines for LLM analysis via agent
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def prepare_for_llm_analysis(max_headlines=100):
    """
    Prepare headlines for LLM analysis
    Saves a file that the agent can process
    """
    
    # Load latest harvest
    harvest_path = os.path.join(BASE_DIR, 'data', 'latest_harvest.json')
    if not os.path.exists(harvest_path):
        print("No harvest data found")
        return None
    
    with open(harvest_path) as f:
        harvest = json.load(f)
    
    headlines = harvest.get('headlines', [])
    
    # Filter to most important (not yet LLM analyzed)
    to_analyze = [h for h in headlines if not h.get('llm_analyzed')][:max_headlines]
    
    # Save for agent processing
    output = {
        'timestamp': datetime.now().isoformat(),
        'count': len(to_analyze),
        'headlines': [
            {'idx': i, 'source': h.get('source', '?'), 'title': h.get('title', '')}
            for i, h in enumerate(to_analyze)
        ]
    }
    
    output_path = os.path.join(BASE_DIR, 'data', 'pending_llm_analysis.json')
    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"Prepared {len(to_analyze)} headlines for LLM analysis")
    print(f"Saved to: {output_path}")
    
    return output

def save_llm_results(results: list):
    """
    Save LLM analysis results back to harvest
    Called by agent after analysis
    """
    
    harvest_path = os.path.join(BASE_DIR, 'data', 'latest_harvest.json')
    with open(harvest_path) as f:
        harvest = json.load(f)
    
    headlines = harvest.get('headlines', [])
    
    # Create lookup by title
    title_to_result = {r.get('title', '')[:50]: r for r in results}
    
    # Update headlines with LLM results
    updated = 0
    for h in headlines:
        key = h.get('title', '')[:50]
        if key in title_to_result:
            r = title_to_result[key]
            h['sentiment'] = r.get('sentiment', h.get('sentiment', 0))
            h['sectors'] = r.get('sectors', h.get('sectors', ['general']))
            h['llm_analyzed'] = True
            updated += 1
    
    # Recalculate sector sentiment
    sector_scores = {}
    for h in headlines:
        sent = h.get('sentiment', 0)
        for sector in h.get('sectors', ['general']):
            if sector not in sector_scores:
                sector_scores[sector] = {'scores': [], 'headlines': []}
            sector_scores[sector]['scores'].append(sent)
            sector_scores[sector]['headlines'].append(h)
    
    # Aggregate
    harvest['sector_sentiment'] = {}
    for sector, data in sector_scores.items():
        if data['scores']:
            avg = sum(data['scores']) / len(data['scores'])
            harvest['sector_sentiment'][sector] = {
                'score': round(avg, 3),
                'count': len(data['scores']),
                'signal': 'BUY' if avg > 0.25 else ('SELL' if avg < -0.25 else 'HOLD')
            }
    
    harvest['llm_analyzed'] = True
    harvest['llm_updated'] = datetime.now().isoformat()
    
    with open(harvest_path, 'w') as f:
        json.dump(harvest, f, indent=2)
    
    print(f"Updated {updated} headlines with LLM sentiment")
    return updated

def get_analysis_prompt():
    """Generate prompt for agent to use"""
    
    pending_path = os.path.join(BASE_DIR, 'data', 'pending_llm_analysis.json')
    if not os.path.exists(pending_path):
        return None
    
    with open(pending_path) as f:
        data = json.load(f)
    
    headlines = data.get('headlines', [])
    
    prompt = """Analyze sentiment for these financial headlines.
For each, give sentiment (-1.0 to +1.0) and sectors.

Sectors: XLK=Tech, XLV=Healthcare, XLF=Finance, XLY=Consumer, XLP=Staples, 
XLE=Energy, ICLN=Clean Energy, XLI=Industrial, XLB=Materials, XLU=Utilities, 
XLRE=Real Estate, XLC=Communication, CRYPTO=Crypto

Headlines:
"""
    
    for h in headlines[:50]:  # Limit to 50 for token efficiency
        prompt += f"\n{h['idx']}. [{h['source']}] {h['title']}"
    
    prompt += """

Reply as JSON array:
[{"idx":0,"sentiment":0.5,"sectors":["XLK"],"title":"...first 30 chars..."},...]"""
    
    return prompt

if __name__ == '__main__':
    prepare_for_llm_analysis()
    print("\n" + "="*60)
    print("PROMPT FOR AGENT:")
    print("="*60)
    prompt = get_analysis_prompt()
    if prompt:
        print(prompt[:1000] + "...")
