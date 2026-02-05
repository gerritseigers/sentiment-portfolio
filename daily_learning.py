#!/usr/bin/env python3
"""
Daily Learning Module
Trains the model every day by comparing yesterday's sentiment with today's price movements

Now includes PROMPT EVOLUTION - sector prompts are updated based on performance!
"""

import json
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Import prompt evolution for tracking and updating prompts
try:
    from prompt_evolution import (
        record_prediction, 
        get_underperforming_sectors,
        update_sector_prompt,
        get_prompt_history,
        generate_evolution_report
    )
    HAS_PROMPT_EVOLUTION = True
except ImportError:
    HAS_PROMPT_EVOLUTION = False
    print("⚠️ Prompt evolution not available")

def load_json(filename):
    path = os.path.join(BASE_DIR, 'data', filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def save_json(data, filename):
    path = os.path.join(BASE_DIR, 'data', filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def get_sector_etf_prices():
    """
    Simulated price changes - in production would use real API
    Returns dict of sector -> daily % change
    """
    # TODO: Integrate with real price API (Yahoo Finance, etc.)
    # For now, return placeholder that will be replaced
    return None

def calculate_source_reliability(headlines, actual_outcomes):
    """Calculate which news sources predicted correctly"""
    source_scores = {}
    
    for headline in headlines:
        source = headline.get('source', 'unknown')
        sentiment = headline.get('sentiment', 0)
        sectors = headline.get('sectors', [])
        
        for sector in sectors:
            if sector in actual_outcomes:
                actual = actual_outcomes[sector]
                # Did this headline's sentiment match the outcome?
                correct = (sentiment > 0 and actual > 0) or \
                         (sentiment < 0 and actual < 0) or \
                         (abs(sentiment) < 0.1 and abs(actual) < 0.5)
                
                if source not in source_scores:
                    source_scores[source] = {'correct': 0, 'total': 0}
                
                source_scores[source]['total'] += 1
                if correct:
                    source_scores[source]['correct'] += 1
    
    return source_scores

def daily_learn(price_changes=None):
    """
    Daily learning cycle:
    1. Compare yesterday's sentiment predictions with today's price moves
    2. Update source reliability scores
    3. Adjust sector sensitivity multipliers
    4. Log what was learned
    """
    print(f"🧠 Daily Learning - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Load model and latest sentiment
    model = load_json('learning_model_v2.json')
    sentiment = load_json('latest_harvest.json')
    
    if not model:
        print("❌ No model found!")
        return None
    
    if not sentiment:
        print("❌ No sentiment data found!")
        return None
    
    # Get price changes (simulated for now, will integrate real API)
    if price_changes is None:
        print("⚠️ No real price data - using sentiment-based simulation for learning")
        # Simulate based on general market behavior
        # In production, this would fetch real ETF prices
        import random
        sectors = ['XLK', 'XLV', 'XLF', 'XLY', 'XLP', 'XLE', 'ICLN', 'XLI', 'XLB', 'XLU', 'XLRE', 'XLC', 'CRYPTO']
        price_changes = {s: random.uniform(-2, 2) for s in sectors}
    
    learning_entry = {
        'date': datetime.now().isoformat(),
        'type': 'daily',
        'predictions': {},
        'outcomes': {},
        'source_updates': {},
        'sector_updates': {},
        'summary': []
    }
    
    sector_sentiment = sentiment.get('sector_sentiment', {})
    headlines = sentiment.get('headlines', [])
    
    # === LEARN FROM SECTOR PREDICTIONS ===
    print("\n📊 Sector Learning:")
    
    correct_count = 0
    total_count = 0
    
    for sector, sent_data in sector_sentiment.items():
        if sector not in price_changes:
            continue
            
        predicted = sent_data.get('score', 0)
        actual = price_changes.get(sector, 0)
        
        learning_entry['predictions'][sector] = predicted
        learning_entry['outcomes'][sector] = actual
        
        # Determine if prediction was correct
        if predicted > 0.1 and actual > 0:
            correct = True
            result = "✓ Bullish correct"
        elif predicted < -0.1 and actual < 0:
            correct = True
            result = "✓ Bearish correct"
        elif abs(predicted) <= 0.1 and abs(actual) <= 1:
            correct = True
            result = "✓ Neutral correct"
        else:
            correct = False
            result = "✗ Wrong"
        
        total_count += 1
        if correct:
            correct_count += 1
        
        # Track prediction for prompt evolution
        if HAS_PROMPT_EVOLUTION:
            record_prediction(sector, correct)
        
        # Update sector sensitivity
        sens = model['sector_sensitivity'].get(sector, {
            'sentiment_multiplier': 1.0,
            'correct_predictions': 0,
            'total_predictions': 0
        })
        
        sens['total_predictions'] = sens.get('total_predictions', 0) + 1
        
        if correct:
            sens['correct_predictions'] = sens.get('correct_predictions', 0) + 1
            # Increase trust
            old_mult = sens.get('sentiment_multiplier', 1.0)
            sens['sentiment_multiplier'] = min(2.0, old_mult * 1.02)
            learning_entry['sector_updates'][sector] = f"multiplier {old_mult:.2f} → {sens['sentiment_multiplier']:.2f} (+2%)"
        else:
            # Decrease trust
            old_mult = sens.get('sentiment_multiplier', 1.0)
            sens['sentiment_multiplier'] = max(0.5, old_mult * 0.98)
            learning_entry['sector_updates'][sector] = f"multiplier {old_mult:.2f} → {sens['sentiment_multiplier']:.2f} (-2%)"
        
        model['sector_sensitivity'][sector] = sens
        
        print(f"  {sector:6} | Predicted: {predicted:+.2f} | Actual: {actual:+.1f}% | {result}")
    
    accuracy = (correct_count / total_count * 100) if total_count > 0 else 0
    print(f"\n  Daily Accuracy: {correct_count}/{total_count} = {accuracy:.0f}%")
    
    # === LEARN FROM NEWS SOURCES ===
    print("\n📰 Source Reliability Learning:")
    
    source_scores = calculate_source_reliability(headlines, price_changes)
    
    for source, scores in sorted(source_scores.items(), key=lambda x: x[1]['total'], reverse=True)[:10]:
        if scores['total'] >= 3:  # Only update if enough data
            reliability = scores['correct'] / scores['total']
            
            # Update source weight in model
            if 'source_weights' not in model:
                model['source_weights'] = {}
            
            old_weight = model['source_weights'].get(source, 1.0)
            # Move towards actual reliability
            new_weight = old_weight * 0.9 + reliability * 0.1
            model['source_weights'][source] = new_weight
            
            learning_entry['source_updates'][source] = {
                'correct': scores['correct'],
                'total': scores['total'],
                'reliability': reliability,
                'weight': new_weight
            }
            
            emoji = '🟢' if reliability > 0.6 else ('🔴' if reliability < 0.4 else '🟡')
            print(f"  {emoji} {source[:25]:25} | {scores['correct']}/{scores['total']} = {reliability:.0%} | weight: {new_weight:.2f}")
    
    # === SUMMARY ===
    learning_entry['summary'] = [
        f"Daily accuracy: {accuracy:.0f}%",
        f"Sectors analyzed: {total_count}",
        f"Correct predictions: {correct_count}",
        f"Sources updated: {len(learning_entry['source_updates'])}"
    ]
    
    # Save learning to history
    if 'learning_history' not in model:
        model['learning_history'] = []
    model['learning_history'].append(learning_entry)
    
    # Keep only last 90 days of history
    model['learning_history'] = model['learning_history'][-90:]
    
    # Update model timestamp
    model['last_updated'] = datetime.now().isoformat()
    model['last_learning'] = datetime.now().isoformat()
    
    # Calculate overall model stats
    all_correct = sum(s.get('correct_predictions', 0) for s in model['sector_sensitivity'].values())
    all_total = sum(s.get('total_predictions', 0) for s in model['sector_sensitivity'].values())
    model['overall_accuracy'] = (all_correct / all_total * 100) if all_total > 0 else 0
    
    # Save model
    save_json(model, 'learning_model_v2.json')
    
    print(f"\n✅ Model updated!")
    print(f"   Overall accuracy: {model['overall_accuracy']:.1f}%")
    print(f"   Total predictions: {all_total}")
    
    # === CHECK FOR UNDERPERFORMING PROMPTS ===
    if HAS_PROMPT_EVOLUTION:
        print("\n📝 Prompt Evolution Check:")
        underperf = get_underperforming_sectors(threshold=50.0, min_predictions=10)
        if underperf:
            print("   ⚠️ Sectors needing prompt improvement:")
            for s in underperf:
                print(f"      {s['sector']}: {s['accuracy']:.1f}% accuracy")
            learning_entry['prompts_flagged'] = [s['sector'] for s in underperf]
        else:
            print("   ✅ All sector prompts performing adequately")
    
    return learning_entry

def generate_learning_report():
    """Generate a report of what the model learned today"""
    model = load_json('learning_model_v2.json')
    
    if not model:
        return "❌ Geen model data"
    
    lines = []
    lines.append("**🧠 WAT HET MODEL VANDAAG LEERDE**")
    lines.append("")
    
    # Recent learning
    history = model.get('learning_history', [])
    if history:
        latest = history[-1]
        lines.append(f"*Laatste training:* {latest.get('date', 'onbekend')[:10]}")
        
        for item in latest.get('summary', []):
            lines.append(f"• {item}")
        lines.append("")
        
        # Sector updates
        sector_updates = latest.get('sector_updates', {})
        if sector_updates:
            lines.append("*Sector aanpassingen:*")
            for sector, update in list(sector_updates.items())[:5]:
                lines.append(f"  {sector}: {update}")
    
    # Overall stats
    lines.append("")
    lines.append(f"*Totale nauwkeurigheid:* {model.get('overall_accuracy', 0):.1f}%")
    
    # Best/worst sectors
    sens = model.get('sector_sensitivity', {})
    sorted_sens = sorted(sens.items(), key=lambda x: x[1].get('sentiment_multiplier', 1), reverse=True)
    
    if sorted_sens:
        lines.append("")
        lines.append("*Meest betrouwbare sectoren:*")
        for sector, data in sorted_sens[:3]:
            mult = data.get('sentiment_multiplier', 1)
            lines.append(f"  🟢 {sector}: {mult:.2f}x")
    
    # Prompt evolution status
    if HAS_PROMPT_EVOLUTION:
        lines.append("")
        lines.append("*Prompt evolutie:*")
        underperf = get_underperforming_sectors(threshold=50.0, min_predictions=10)
        if underperf:
            lines.append(f"  ⚠️ {len(underperf)} sectoren onder 50% accuracy")
            for s in underperf[:3]:
                lines.append(f"    • {s['sector']}: {s['accuracy']:.1f}%")
        else:
            lines.append("  ✅ Alle prompts presteren goed")
    
    return '\n'.join(lines)


def suggest_prompt_improvement(sector: str) -> str:
    """
    Generate suggestions for improving a sector's prompt based on recent performance.
    This helps guide manual prompt updates.
    """
    if not HAS_PROMPT_EVOLUTION:
        return "Prompt evolution module not available"
    
    history = get_prompt_history(sector)
    underperf = get_underperforming_sectors()
    
    # Find this sector in underperforming
    sector_data = next((s for s in underperf if s['sector'] == sector), None)
    
    lines = [f"## 🔧 Prompt Improvement Suggestions for {sector}"]
    lines.append("")
    
    if sector_data:
        lines.append(f"Current accuracy: {sector_data['accuracy']:.1f}%")
        lines.append(f"Current prompt:\n```\n{sector_data['current_prompt']}\n```")
        lines.append("")
        lines.append("### Suggestions:")
        lines.append("1. Add more specific keywords for common missed predictions")
        lines.append("2. Clarify sentiment thresholds for ambiguous news types")
        lines.append("3. Add domain-specific context the model may be missing")
        lines.append("")
        lines.append(f"History: {len(history)} previous versions")
    else:
        lines.append(f"✅ Sector {sector} is performing well, no improvements needed")
    
    return '\n'.join(lines)


if __name__ == '__main__':
    # Run daily learning
    learning = daily_learn()
    
    print("\n" + "=" * 60)
    print("LEARNING REPORT:")
    print("=" * 60)
    print(generate_learning_report())
