#!/usr/bin/env python3
"""
Weekly Rebalance & Report Generator
Runs every Monday to rebalance portfolios based on sentiment
"""

import json
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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

def get_latest_sentiment():
    """Get most recent sentiment harvest"""
    path = os.path.join(BASE_DIR, 'data', 'latest_harvest.json')
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def calculate_new_allocations(scenario, sentiment):
    """Calculate target allocations based on scenario and sentiment"""
    sectors = ['XLK', 'XLV', 'XLF', 'XLY', 'XLP', 'XLE', 'ICLN', 'XLI', 'XLB', 'XLU', 'XLRE', 'XLC', 'CRYPTO']
    sector_scores = sentiment.get('sector_sentiment', {})
    
    allocations = {}
    
    if scenario == 'spy_only':
        return {'SPY': 100}
    
    if scenario == 'benchmark':
        equal = 100 / len(sectors)
        return {s: round(equal, 2) for s in sectors}
    
    if scenario == 'momentum':
        base = 100 / len(sectors)
        for sector in sectors:
            score = sector_scores.get(sector, {}).get('score', 0)
            adj = score * 50
            allocations[sector] = max(2, min(20, base + adj))
        total = sum(allocations.values())
        return {k: round((v/total)*100, 2) for k, v in allocations.items()}
    
    if scenario == 'aggressive':
        sorted_sectors = sorted(sectors, key=lambda s: sector_scores.get(s, {}).get('score', 0), reverse=True)
        top_3 = sorted_sectors[:3]
        for sector in sectors:
            allocations[sector] = 30 if sector in top_3 else 1
        total = sum(allocations.values())
        return {k: round((v/total)*100, 2) for k, v in allocations.items()}
    
    if scenario == 'defensive':
        defensive = ['XLU', 'XLP', 'XLV', 'XLRE', 'XLF']
        for sector in sectors:
            score = sector_scores.get(sector, {}).get('score', 0)
            base = 15 if sector in defensive else 3
            if score > 0.4:
                allocations[sector] = base + 5
            elif score < -0.3:
                allocations[sector] = max(1, base - 5)
            else:
                allocations[sector] = base
        total = sum(allocations.values())
        return {k: round((v/total)*100, 2) for k, v in allocations.items()}
    
    if scenario == 'contrarian':
        base = 100 / len(sectors)
        for sector in sectors:
            score = sector_scores.get(sector, {}).get('score', 0)
            adj = -score * 50  # Inverse!
            allocations[sector] = max(2, min(20, base + adj))
        total = sum(allocations.values())
        return {k: round((v/total)*100, 2) for k, v in allocations.items()}
    
    return allocations

def generate_weekly_report():
    """Generate weekly portfolio report"""
    portfolios = load_json('portfolios.json')
    sentiment = get_latest_sentiment()
    model = load_json('learning_model_v2.json')
    
    if not portfolios or not sentiment:
        return "❌ Geen data beschikbaar voor rapport"
    
    report_lines = []
    report_lines.append("📊 **WEKELIJKS PORTFOLIO RAPPORT**")
    report_lines.append(f"📅 {datetime.now().strftime('%d %B %Y')}")
    report_lines.append("")
    
    # Sentiment summary
    sector_sent = sentiment.get('sector_sentiment', {})
    sorted_sectors = sorted(sector_sent.items(), key=lambda x: x[1].get('score', 0), reverse=True)
    
    report_lines.append("**🎯 SENTIMENT RANKINGS**")
    top_3 = sorted_sectors[:3]
    bottom_3 = sorted_sectors[-3:]
    
    report_lines.append("*Bullish:*")
    for sector, data in top_3:
        emoji = '🟢' if data['score'] > 0.2 else '🟡'
        report_lines.append(f"  {emoji} {sector}: {data['score']:+.2f}")
    
    report_lines.append("*Bearish:*")
    for sector, data in bottom_3:
        emoji = '🔴' if data['score'] < -0.2 else '🟡'
        report_lines.append(f"  {emoji} {sector}: {data['score']:+.2f}")
    
    report_lines.append("")
    report_lines.append("**💰 PORTFOLIO STATUS (€50k elk)**")
    
    # Portfolio status per scenario
    scenarios = ['benchmark', 'momentum', 'aggressive', 'defensive', 'contrarian', 'spy_only']
    scenario_emoji = {
        'benchmark': '🎯', 'momentum': '📈', 'aggressive': '⚡',
        'defensive': '🛡️', 'contrarian': '🔄', 'spy_only': '📊'
    }
    
    for scenario in scenarios:
        emoji = scenario_emoji.get(scenario, '📌')
        port = portfolios.get(scenario, {})
        value = port.get('current_value', 50000)
        start = port.get('start_capital', 50000)
        pnl = value - start
        pnl_pct = (pnl / start) * 100 if start > 0 else 0
        
        pnl_emoji = '📈' if pnl >= 0 else '📉'
        report_lines.append(f"{emoji} **{scenario}**: €{value:,.0f} ({pnl_emoji} {pnl_pct:+.1f}%)")
    
    report_lines.append("")
    report_lines.append("**🔄 NIEUWE ALLOCATIES DEZE WEEK**")
    
    # Show new allocations for momentum (most interesting)
    new_alloc = calculate_new_allocations('momentum', sentiment)
    sorted_alloc = sorted(new_alloc.items(), key=lambda x: x[1], reverse=True)
    
    report_lines.append("*Momentum strategie:*")
    for sector, pct in sorted_alloc[:5]:
        report_lines.append(f"  {sector}: {pct:.1f}%")
    report_lines.append("  ...")
    
    # Learning stats
    if model:
        report_lines.append("")
        report_lines.append("**🧠 MODEL LEARNING**")
        total_pred = sum(s.get('total_predictions', 0) for s in model.get('sector_sensitivity', {}).values())
        correct_pred = sum(s.get('correct_predictions', 0) for s in model.get('sector_sensitivity', {}).values())
        if total_pred > 0:
            accuracy = (correct_pred / total_pred) * 100
            report_lines.append(f"  Voorspellingen: {total_pred}")
            report_lines.append(f"  Nauwkeurigheid: {accuracy:.1f}%")
    
    report_lines.append("")
    report_lines.append(f"_Volgende rebalance: volgende week maandag_")
    
    return '\n'.join(report_lines)

def run_weekly_rebalance():
    """Main weekly rebalance function"""
    print(f"🔄 Weekly Rebalance - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)
    
    # Load data
    portfolios = load_json('portfolios.json')
    sentiment = get_latest_sentiment()
    
    if not portfolios:
        print("❌ No portfolios found!")
        return None
    
    if not sentiment:
        print("⚠️ No sentiment data - running harvest first...")
        os.system(f'python3 {os.path.join(BASE_DIR, "harvester.py")}')
        sentiment = get_latest_sentiment()
    
    # Calculate and apply new allocations
    print("\n📊 Calculating new allocations...")
    
    rebalance_log = {
        'date': datetime.now().isoformat(),
        'allocations': {}
    }
    
    for scenario in portfolios.keys():
        new_alloc = calculate_new_allocations(scenario, sentiment)
        rebalance_log['allocations'][scenario] = new_alloc
        
        # Update portfolio targets
        portfolios[scenario]['last_rebalance'] = datetime.now().isoformat()
        portfolios[scenario]['target_allocations'] = new_alloc
        
        print(f"\n  {scenario}:")
        sorted_alloc = sorted(new_alloc.items(), key=lambda x: x[1], reverse=True)[:5]
        for sector, pct in sorted_alloc:
            print(f"    {sector}: {pct:.1f}%")
    
    # Save updated portfolios
    save_json(portfolios, 'portfolios.json')
    
    # Save rebalance log
    logs = load_json('rebalance_history.json') or []
    logs.append(rebalance_log)
    save_json(logs, 'rebalance_history.json')
    
    # Generate report
    print("\n📝 Generating report...")
    report = generate_weekly_report()
    
    # Save report
    report_file = os.path.join(BASE_DIR, 'data', 'reports', f"weekly_{datetime.now().strftime('%Y-%m-%d')}.txt")
    os.makedirs(os.path.dirname(report_file), exist_ok=True)
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(f"\n✅ Rebalance complete!")
    print(f"📁 Report saved: {report_file}")
    
    return report

if __name__ == '__main__':
    report = run_weekly_rebalance()
    print("\n" + "=" * 60)
    print("RAPPORT VOOR TELEGRAM:")
    print("=" * 60)
    print(report)
