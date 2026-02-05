#!/usr/bin/env python3
"""
End-of-Day Scenario Performance Report
Generates a summary of all trading scenarios with:
- Best/worst performing sectors
- Overall score (1-10, where 6 = break-even)
- Total P&L
- Color coding (green = good, red = bad)
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_json(filename: str) -> Optional[Dict]:
    """Load JSON file from data directory"""
    path = os.path.join(BASE_DIR, 'data', filename)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def save_json(data: Dict, filename: str) -> None:
    """Save JSON file to data directory"""
    path = os.path.join(BASE_DIR, 'data', filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def calculate_score(pnl_percent: float) -> int:
    """
    Convert P&L percentage to score 1-10.
    Score 6 = break-even (0%)
    
    Scale:
    - 10 = +4% or more
    - 9  = +3% to +4%
    - 8  = +2% to +3%
    - 7  = +1% to +2%
    - 6  = -0.5% to +1% (break-even zone)
    - 5  = -1% to -0.5%
    - 4  = -2% to -1%
    - 3  = -3% to -2%
    - 2  = -4% to -3%
    - 1  = worse than -4%
    """
    if pnl_percent >= 4.0:
        return 10
    elif pnl_percent >= 3.0:
        return 9
    elif pnl_percent >= 2.0:
        return 8
    elif pnl_percent >= 1.0:
        return 7
    elif pnl_percent >= -0.5:
        return 6
    elif pnl_percent >= -1.0:
        return 5
    elif pnl_percent >= -2.0:
        return 4
    elif pnl_percent >= -3.0:
        return 3
    elif pnl_percent >= -4.0:
        return 2
    else:
        return 1


def get_score_emoji(score: int) -> str:
    """Get color emoji based on score"""
    if score >= 8:
        return "🟢"  # Excellent
    elif score >= 6:
        return "🟡"  # OK / Break-even
    elif score >= 4:
        return "🟠"  # Warning
    else:
        return "🔴"  # Bad


def get_score_bar(score: int) -> str:
    """Visual bar representation of score"""
    filled = "█" * score
    empty = "░" * (10 - score)
    return f"{filled}{empty}"


def generate_scenario_report(portfolio_data: Dict = None) -> str:
    """
    Generate end-of-day scenario performance report.
    
    Args:
        portfolio_data: Portfolio state with scenarios. If None, loads from file.
        
    Returns:
        Formatted report string
    """
    if portfolio_data is None:
        portfolio_data = load_json('portfolio_state.json')
    
    if not portfolio_data:
        return "❌ Geen portfolio data gevonden"
    
    scenarios = portfolio_data.get('scenarios', {})
    
    if not scenarios:
        return "❌ Geen scenario's gevonden"
    
    lines = []
    today = datetime.now().strftime('%Y-%m-%d')
    
    lines.append(f"# 📊 DAGRAPPORT - {today}")
    lines.append(f"*Gegenereerd: {datetime.now().strftime('%H:%M')}*")
    lines.append("")
    
    # Summary table header
    lines.append("## Scenario Overzicht")
    lines.append("")
    
    total_pnl = 0
    scenario_results = []
    
    for scenario_name, scenario_data in scenarios.items():
        # Get scenario metrics
        initial_value = scenario_data.get('initial_value', 50000)
        current_value = scenario_data.get('current_value', initial_value)
        pnl = current_value - initial_value
        pnl_percent = (pnl / initial_value * 100) if initial_value > 0 else 0
        
        # Get sector performances
        sectors = scenario_data.get('sectors', {})
        sector_perfs = []
        
        for sector_name, sector_data in sectors.items():
            sector_initial = sector_data.get('initial_value', 0)
            sector_current = sector_data.get('current_value', sector_initial)
            if sector_initial > 0:
                sector_pnl_pct = (sector_current - sector_initial) / sector_initial * 100
                sector_perfs.append({
                    'name': sector_name,
                    'pnl_percent': sector_pnl_pct,
                    'pnl': sector_current - sector_initial
                })
        
        # Sort sectors by performance
        sector_perfs.sort(key=lambda x: x['pnl_percent'], reverse=True)
        
        best_sector = sector_perfs[0] if sector_perfs else None
        worst_sector = sector_perfs[-1] if sector_perfs else None
        
        score = calculate_score(pnl_percent)
        emoji = get_score_emoji(score)
        
        scenario_results.append({
            'name': scenario_name,
            'pnl': pnl,
            'pnl_percent': pnl_percent,
            'score': score,
            'emoji': emoji,
            'best_sector': best_sector,
            'worst_sector': worst_sector,
            'current_value': current_value
        })
        
        total_pnl += pnl
    
    # Sort scenarios by score (best first)
    scenario_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Generate report for each scenario
    for result in scenario_results:
        emoji = result['emoji']
        name = result['name'].upper()
        score = result['score']
        pnl = result['pnl']
        pnl_pct = result['pnl_percent']
        bar = get_score_bar(score)
        
        # P&L formatting
        pnl_sign = "+" if pnl >= 0 else ""
        pnl_color = "📈" if pnl >= 0 else "📉"
        
        lines.append(f"### {emoji} {name}")
        lines.append(f"**Score: {score}/10** {bar}")
        lines.append(f"{pnl_color} P&L: {pnl_sign}€{pnl:,.0f} ({pnl_sign}{pnl_pct:.1f}%)")
        
        if result['best_sector']:
            best = result['best_sector']
            lines.append(f"🏆 Best: **{best['name']}** (+{best['pnl_percent']:.1f}%)")
        
        if result['worst_sector']:
            worst = result['worst_sector']
            lines.append(f"⚠️ Worst: **{worst['name']}** ({worst['pnl_percent']:.1f}%)")
        
        lines.append("")
    
    # Total summary
    lines.append("---")
    lines.append("## 💰 TOTAAL")
    
    total_sign = "+" if total_pnl >= 0 else ""
    total_emoji = "🟢" if total_pnl >= 0 else "🔴"
    
    lines.append(f"{total_emoji} **{total_sign}€{total_pnl:,.0f}**")
    
    # Best and worst scenarios
    if scenario_results:
        best_scenario = scenario_results[0]
        worst_scenario = scenario_results[-1]
        
        lines.append("")
        lines.append(f"🥇 Best scenario: **{best_scenario['name'].upper()}** (score {best_scenario['score']})")
        lines.append(f"🥉 Worst scenario: **{worst_scenario['name'].upper()}** (score {worst_scenario['score']})")
    
    # Score legend
    lines.append("")
    lines.append("---")
    lines.append("*Score: 🟢 8-10 excellent | 🟡 6-7 break-even | 🟠 4-5 warning | 🔴 1-3 bad*")
    
    return '\n'.join(lines)


def generate_sample_report() -> str:
    """Generate a sample report with mock data for demonstration"""
    
    sample_data = {
        'scenarios': {
            'benchmark': {
                'initial_value': 50000,
                'current_value': 50750,
                'sectors': {
                    'XLK': {'initial_value': 5000, 'current_value': 5200},
                    'XLF': {'initial_value': 5000, 'current_value': 4950},
                    'XLE': {'initial_value': 5000, 'current_value': 5100},
                    'XLV': {'initial_value': 5000, 'current_value': 5050},
                    'CRYPTO': {'initial_value': 5000, 'current_value': 5300},
                }
            },
            'momentum': {
                'initial_value': 50000,
                'current_value': 51200,
                'sectors': {
                    'XLK': {'initial_value': 8000, 'current_value': 8500},
                    'CRYPTO': {'initial_value': 8000, 'current_value': 8600},
                    'XLE': {'initial_value': 4000, 'current_value': 4100},
                }
            },
            'aggressive': {
                'initial_value': 50000,
                'current_value': 52500,
                'sectors': {
                    'XLK': {'initial_value': 15000, 'current_value': 16000},
                    'CRYPTO': {'initial_value': 15000, 'current_value': 16200},
                    'XLF': {'initial_value': 5000, 'current_value': 5100},
                }
            },
            'defensive': {
                'initial_value': 50000,
                'current_value': 50200,
                'sectors': {
                    'XLP': {'initial_value': 10000, 'current_value': 10100},
                    'XLU': {'initial_value': 10000, 'current_value': 10050},
                    'XLV': {'initial_value': 10000, 'current_value': 10080},
                }
            },
            'contrarian': {
                'initial_value': 50000,
                'current_value': 48500,
                'sectors': {
                    'XLE': {'initial_value': 10000, 'current_value': 9500},
                    'XLRE': {'initial_value': 10000, 'current_value': 9700},
                    'XLF': {'initial_value': 10000, 'current_value': 9800},
                }
            },
            'spy_only': {
                'initial_value': 50000,
                'current_value': 50400,
                'sectors': {
                    'SPY': {'initial_value': 50000, 'current_value': 50400},
                }
            }
        }
    }
    
    return generate_scenario_report(sample_data)


def send_daily_report(report: str) -> None:
    """
    Send the daily report (placeholder for integration).
    In production, this would send via Telegram/email.
    """
    print(report)
    
    # Save report to file
    today = datetime.now().strftime('%Y-%m-%d')
    save_path = os.path.join(BASE_DIR, 'data', 'reports', f'daily_{today}.md')
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    
    with open(save_path, 'w') as f:
        f.write(report)
    
    print(f"\n📁 Report saved to: {save_path}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'sample':
        # Generate sample report
        print("Generating sample report...\n")
        report = generate_sample_report()
    else:
        # Generate real report
        report = generate_scenario_report()
    
    send_daily_report(report)
