#!/usr/bin/env python3
"""
Daily Sentiment Report Generator
Generates easy-to-understand daily reports
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def load_json(filename):
    path = os.path.join(BASE_DIR, 'data', filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def get_sector_name(code):
    names = {
        'XLK': 'Technology', 'XLV': 'Healthcare', 'XLF': 'Financials',
        'XLY': 'Consumer Discr.', 'XLP': 'Consumer Staples', 'XLE': 'Energy',
        'ICLN': 'Clean Energy', 'XLI': 'Industrials', 'XLB': 'Materials',
        'XLU': 'Utilities', 'XLRE': 'Real Estate', 'XLC': 'Communication',
        'CRYPTO': 'Crypto', 'general': 'Algemeen'
    }
    return names.get(code, code)

def interpret_score(score):
    """Human-readable interpretation of sentiment score"""
    if score > 0.4:
        return "🟢🔥 Zeer positief - sterk koopsignaal"
    elif score > 0.2:
        return "🟢 Positief - bullish sentiment"
    elif score > 0.05:
        return "🟢 Licht positief"
    elif score > -0.05:
        return "🟡 Neutraal - afwachten"
    elif score > -0.2:
        return "🔴 Licht negatief"
    elif score > -0.4:
        return "🔴 Negatief - bearish sentiment"
    else:
        return "🔴⚠️ Zeer negatief - verkoopsignaal"

def generate_daily_report():
    """Generate comprehensive daily report"""
    sentiment = load_json('latest_harvest.json')
    portfolios = load_json('portfolios.json')
    model = load_json('learning_model_v2.json')
    
    if not sentiment:
        return "❌ Geen sentiment data beschikbaar"
    
    lines = []
    now = datetime.now()
    
    # Header
    lines.append(f"📰 **DAGELIJKS SENTIMENT RAPPORT**")
    lines.append(f"📅 {now.strftime('%A %d %B %Y')} - {now.strftime('%H:%M')}")
    lines.append("")
    
    # Stats
    stats = sentiment.get('stats', {})
    lines.append(f"📊 *{stats.get('total_headlines', 0)} nieuwsberichten* van {stats.get('sources_total', 0)} bronnen")
    lines.append("")
    
    # === SECTOR RANKINGS ===
    lines.append("**🏆 SECTOR RANKINGS VANDAAG**")
    lines.append("")
    
    sector_sent = sentiment.get('sector_sentiment', {})
    sorted_sectors = sorted(sector_sent.items(), key=lambda x: x[1].get('score', 0), reverse=True)
    
    # Top 3 Bullish
    lines.append("*📈 MEEST POSITIEF:*")
    for i, (sector, data) in enumerate(sorted_sectors[:3], 1):
        score = data.get('score', 0)
        count = data.get('count', 0)
        name = get_sector_name(sector)
        interpretation = interpret_score(score)
        lines.append(f"{i}. **{name}** ({sector})")
        lines.append(f"   Score: {score:+.2f} | {count} artikelen")
        lines.append(f"   → {interpretation}")
        
        # Top headline if available
        top_pos = data.get('top_positive', [])
        if top_pos:
            lines.append(f"   📰 _{top_pos[0][:60]}..._")
        lines.append("")
    
    # Bottom 3 Bearish
    lines.append("*📉 MEEST NEGATIEF:*")
    for i, (sector, data) in enumerate(sorted_sectors[-3:], 1):
        score = data.get('score', 0)
        count = data.get('count', 0)
        name = get_sector_name(sector)
        interpretation = interpret_score(score)
        lines.append(f"{i}. **{name}** ({sector})")
        lines.append(f"   Score: {score:+.2f} | {count} artikelen")
        lines.append(f"   → {interpretation}")
        
        top_neg = data.get('top_negative', [])
        if top_neg:
            lines.append(f"   📰 _{top_neg[0][:60]}..._")
        lines.append("")
    
    # === WHAT THIS MEANS ===
    lines.append("**💡 WAT BETEKENT DIT?**")
    lines.append("")
    
    # Calculate overall market sentiment
    all_scores = [d.get('score', 0) for d in sector_sent.values()]
    avg_sentiment = sum(all_scores) / len(all_scores) if all_scores else 0
    
    if avg_sentiment > 0.15:
        lines.append("🟢 **Markt stemming: BULLISH**")
        lines.append("Het nieuws is overwegend positief. De momentum strategie zal meer risico nemen.")
    elif avg_sentiment < -0.15:
        lines.append("🔴 **Markt stemming: BEARISH**")
        lines.append("Het nieuws is overwegend negatief. De defensieve strategie beschermt het kapitaal.")
    else:
        lines.append("🟡 **Markt stemming: NEUTRAAL**")
        lines.append("Geen duidelijke richting. Portfolios blijven dicht bij hun basisallocatie.")
    lines.append("")
    
    # === PORTFOLIO IMPACT ===
    if portfolios:
        lines.append("**💰 PORTFOLIO IMPACT**")
        lines.append("")
        
        # Show what each scenario would do
        top_sector = sorted_sectors[0][0] if sorted_sectors else 'XLK'
        bottom_sector = sorted_sectors[-1][0] if sorted_sectors else 'XLRE'
        top_name = get_sector_name(top_sector)
        bottom_name = get_sector_name(bottom_sector)
        
        lines.append(f"📈 *Momentum*: Verhoogt {top_name}, verlaagt {bottom_name}")
        lines.append(f"⚡ *Aggressive*: Concentreert in top 3 sectoren")
        lines.append(f"🛡️ *Defensive*: {'Beweegt niet (signaal niet sterk genoeg)' if abs(avg_sentiment) < 0.3 else 'Past aan op sterk signaal'}")
        lines.append(f"🔄 *Contrarian*: Koopt {bottom_name} (tegen de stroom in)")
        lines.append("")
    
    # === ALERTS ===
    strong_signals = [(s, d) for s, d in sorted_sectors if abs(d.get('score', 0)) > 0.35]
    if strong_signals:
        lines.append("**⚠️ STERKE SIGNALEN**")
        for sector, data in strong_signals:
            score = data.get('score', 0)
            name = get_sector_name(sector)
            if score > 0:
                lines.append(f"🟢🔥 {name}: STERK POSITIEF ({score:+.2f})")
            else:
                lines.append(f"🔴⚠️ {name}: STERK NEGATIEF ({score:+.2f})")
        lines.append("")
    
    # === MODEL STATUS ===
    if model:
        lines.append("**🧠 MODEL STATUS**")
        sens = model.get('sector_sensitivity', {})
        total_pred = sum(s.get('total_predictions', 0) for s in sens.values())
        correct_pred = sum(s.get('correct_predictions', 0) for s in sens.values())
        
        if total_pred > 0:
            accuracy = (correct_pred / total_pred) * 100
            lines.append(f"Voorspellingen tot nu toe: {total_pred}")
            lines.append(f"Nauwkeurigheid: {accuracy:.0f}%")
        else:
            lines.append("Model is aan het leren (nog geen data)")
        lines.append("")
    
    # Footer
    lines.append("_Volgende harvest: binnen enkele uren_")
    lines.append("_Rebalance: elke maandag 09:00_")
    
    return '\n'.join(lines)

if __name__ == '__main__':
    report = generate_daily_report()
    print(report)
    
    # Save report
    today = datetime.now().strftime('%Y-%m-%d')
    report_dir = os.path.join(BASE_DIR, 'data', 'reports')
    os.makedirs(report_dir, exist_ok=True)
    
    with open(os.path.join(report_dir, f'daily_{today}.txt'), 'w') as f:
        f.write(report)
    
    print(f"\n📁 Saved to: data/reports/daily_{today}.txt")
