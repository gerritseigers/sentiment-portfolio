#!/usr/bin/env python3
"""
Prompt Evolution Module
Manages sector-specific prompts with version history and performance tracking.

Each prompt evolves based on prediction accuracy:
- Tracks correct/incorrect predictions per sector
- Suggests prompt modifications when accuracy drops
- Logs ALL changes to prompt_history/ for full traceability
"""

import json
import os
from datetime import datetime
from typing import Optional, Dict, Any

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPTS_FILE = os.path.join(BASE_DIR, 'sector_prompts.json')
HISTORY_DIR = os.path.join(BASE_DIR, 'data', 'prompt_history')


def load_prompts() -> Dict:
    """Load sector prompts config"""
    if os.path.exists(PROMPTS_FILE):
        with open(PROMPTS_FILE) as f:
            return json.load(f)
    return {"prompts": {}, "base_system_prompt": ""}


def save_prompts(data: Dict) -> None:
    """Save sector prompts config"""
    with open(PROMPTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def get_prompt_for_sector(sector: str) -> str:
    """
    Get the full prompt for a specific sector.
    Combines base prompt with sector-specific context.
    
    Returns: Complete system prompt string
    """
    data = load_prompts()
    base = data.get('base_system_prompt', '')
    
    if sector not in data.get('prompts', {}):
        # Fallback for unknown sectors
        return base.format(
            sector_name=sector,
            sector_specific_prompt="Analyze this sector's news for financial sentiment."
        )
    
    sector_data = data['prompts'][sector]
    return base.format(
        sector_name=sector_data.get('sector_name', sector),
        sector_specific_prompt=sector_data.get('current_prompt', '')
    )


def get_sector_keywords(sector: str) -> list:
    """Get keywords that boost relevance for this sector"""
    data = load_prompts()
    if sector in data.get('prompts', {}):
        return data['prompts'][sector].get('keywords_boost', [])
    return []


def log_prompt_change(sector: str, old_prompt: str, new_prompt: str, 
                      reason: str, performance: Dict) -> None:
    """
    Log a prompt change to the history file.
    Each sector has its own JSONL file for easy tracking.
    """
    os.makedirs(HISTORY_DIR, exist_ok=True)
    
    history_file = os.path.join(HISTORY_DIR, f'{sector}.jsonl')
    
    entry = {
        'timestamp': datetime.now().isoformat(),
        'version_before': get_prompt_version(sector),
        'version_after': get_prompt_version(sector) + 1,
        'old_prompt': old_prompt,
        'new_prompt': new_prompt,
        'reason': reason,
        'performance_at_change': performance,
        'change_type': categorize_change(old_prompt, new_prompt)
    }
    
    with open(history_file, 'a') as f:
        f.write(json.dumps(entry) + '\n')
    
    print(f"📝 Logged prompt change for {sector} (v{entry['version_before']} → v{entry['version_after']})")


def get_prompt_version(sector: str) -> int:
    """Get current version number for a sector's prompt"""
    data = load_prompts()
    if sector in data.get('prompts', {}):
        return data['prompts'][sector].get('version', 1)
    return 1


def categorize_change(old: str, new: str) -> str:
    """Categorize what kind of change was made"""
    old_len = len(old)
    new_len = len(new)
    
    if new_len > old_len * 1.3:
        return 'expansion'
    elif new_len < old_len * 0.7:
        return 'simplification'
    elif old_len == 0:
        return 'initial'
    else:
        return 'refinement'


def update_sector_prompt(sector: str, new_prompt: str, reason: str) -> bool:
    """
    Update a sector's prompt and log the change.
    
    Args:
        sector: Sector code (e.g., 'XLK')
        new_prompt: New sector-specific prompt text
        reason: Why this change was made
        
    Returns: True if successful
    """
    data = load_prompts()
    
    if sector not in data.get('prompts', {}):
        print(f"⚠️ Sector {sector} not found, creating new entry")
        data['prompts'][sector] = {
            'sector_name': sector,
            'version': 0,
            'current_prompt': '',
            'keywords_boost': [],
            'created': datetime.now().isoformat(),
            'performance': {'correct': 0, 'total': 0, 'accuracy': 0}
        }
    
    sector_data = data['prompts'][sector]
    old_prompt = sector_data.get('current_prompt', '')
    performance = sector_data.get('performance', {})
    
    # Log the change
    log_prompt_change(sector, old_prompt, new_prompt, reason, performance)
    
    # Update the prompt
    sector_data['current_prompt'] = new_prompt
    sector_data['version'] = sector_data.get('version', 1) + 1
    sector_data['last_modified'] = datetime.now().isoformat()
    
    data['prompts'][sector] = sector_data
    save_prompts(data)
    
    print(f"✅ Updated {sector} prompt to v{sector_data['version']}")
    return True


def record_prediction(sector: str, was_correct: bool) -> None:
    """Record whether a prediction was correct for performance tracking"""
    data = load_prompts()
    
    if sector not in data.get('prompts', {}):
        return
    
    perf = data['prompts'][sector].get('performance', {'correct': 0, 'total': 0})
    perf['total'] = perf.get('total', 0) + 1
    if was_correct:
        perf['correct'] = perf.get('correct', 0) + 1
    
    perf['accuracy'] = (perf['correct'] / perf['total'] * 100) if perf['total'] > 0 else 0
    
    data['prompts'][sector]['performance'] = perf
    save_prompts(data)


def get_underperforming_sectors(threshold: float = 50.0, min_predictions: int = 10) -> list:
    """
    Get sectors that are performing below threshold accuracy.
    These are candidates for prompt improvement.
    """
    data = load_prompts()
    underperforming = []
    
    for sector, sdata in data.get('prompts', {}).items():
        perf = sdata.get('performance', {})
        total = perf.get('total', 0)
        accuracy = perf.get('accuracy', 0)
        
        if total >= min_predictions and accuracy < threshold:
            underperforming.append({
                'sector': sector,
                'accuracy': accuracy,
                'total': total,
                'current_prompt': sdata.get('current_prompt', '')
            })
    
    return sorted(underperforming, key=lambda x: x['accuracy'])


def get_prompt_history(sector: str, limit: int = 20) -> list:
    """Get recent prompt history for a sector"""
    history_file = os.path.join(HISTORY_DIR, f'{sector}.jsonl')
    
    if not os.path.exists(history_file):
        return []
    
    entries = []
    with open(history_file) as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))
    
    return entries[-limit:]


def generate_evolution_report() -> str:
    """Generate a report of all prompt evolution"""
    data = load_prompts()
    lines = []
    
    lines.append("# 📊 Prompt Evolution Report")
    lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
    
    for sector, sdata in sorted(data.get('prompts', {}).items()):
        perf = sdata.get('performance', {})
        version = sdata.get('version', 1)
        accuracy = perf.get('accuracy', 0)
        total = perf.get('total', 0)
        
        emoji = '🟢' if accuracy >= 60 else ('🟡' if accuracy >= 45 else '🔴')
        
        lines.append(f"## {emoji} {sector} - {sdata.get('sector_name', '')} (v{version})")
        lines.append(f"- Accuracy: {accuracy:.1f}% ({perf.get('correct', 0)}/{total})")
        lines.append(f"- Last modified: {sdata.get('last_modified', 'never')[:10]}")
        
        # Get history count
        history = get_prompt_history(sector, limit=100)
        lines.append(f"- Total prompt versions: {len(history) + 1}")
        lines.append("")
    
    # Underperforming
    underperf = get_underperforming_sectors()
    if underperf:
        lines.append("\n## ⚠️ Sectors Needing Attention")
        for s in underperf:
            lines.append(f"- {s['sector']}: {s['accuracy']:.1f}% accuracy")
    
    return '\n'.join(lines)


def reset_performance(sector: Optional[str] = None) -> None:
    """Reset performance counters (useful after major prompt changes)"""
    data = load_prompts()
    
    sectors = [sector] if sector else list(data.get('prompts', {}).keys())
    
    for s in sectors:
        if s in data.get('prompts', {}):
            data['prompts'][s]['performance'] = {'correct': 0, 'total': 0, 'accuracy': 0}
    
    save_prompts(data)
    print(f"🔄 Reset performance for: {', '.join(sectors)}")


# === Knowledge Integration ===

KNOWLEDGE_SUMMARY_FILE = os.path.join(BASE_DIR, 'data', 'knowledge_summary.json')


def load_knowledge_summary() -> Dict:
    """Load compiled knowledge from harvester."""
    if os.path.exists(KNOWLEDGE_SUMMARY_FILE):
        with open(KNOWLEDGE_SUMMARY_FILE) as f:
            return json.load(f)
    return {}


def suggest_improvements_from_knowledge(sector: str) -> list:
    """
    Suggest prompt improvements based on harvested knowledge.
    Returns list of suggested changes.
    """
    knowledge = load_knowledge_summary()
    if not knowledge:
        return []
    
    suggestions = []
    
    # Get sector-specific knowledge
    sector_knowledge = knowledge.get("sector_knowledge", {})
    sector_tips = sector_knowledge.get(sector, []) + sector_knowledge.get(sector.lower(), [])
    
    if sector_tips:
        suggestions.append({
            "type": "sector_specific",
            "source": "harvested_knowledge",
            "tips": sector_tips[:5]  # Top 5 tips
        })
    
    # Get relevant sentiment signals
    signals = knowledge.get("sentiment_signals", [])
    relevant_signals = [s for s in signals if s.get("confidence") == "high"][:3]
    
    if relevant_signals:
        suggestions.append({
            "type": "sentiment_signals",
            "source": "harvested_knowledge",
            "signals": relevant_signals
        })
    
    # Get timing rules
    timing = knowledge.get("timing_rules", [])[:3]
    if timing:
        suggestions.append({
            "type": "timing_rules",
            "source": "harvested_knowledge",
            "rules": timing
        })
    
    return suggestions


def apply_knowledge_to_prompt(sector: str, current_prompt: str) -> Optional[str]:
    """
    Enhance a sector prompt using harvested knowledge.
    Returns enhanced prompt or None if no improvements.
    """
    suggestions = suggest_improvements_from_knowledge(sector)
    if not suggestions:
        return None
    
    enhancements = []
    
    for suggestion in suggestions:
        if suggestion["type"] == "sentiment_signals":
            signals = suggestion["signals"]
            signal_text = ", ".join([
                f'"{s["signal"]}"={s["meaning"]}' 
                for s in signals
            ])
            enhancements.append(f"Key signals: {signal_text}")
        
        elif suggestion["type"] == "sector_specific":
            tips = suggestion["tips"][:2]  # Max 2 tips
            tips_text = "; ".join(tips)
            enhancements.append(f"Sector insight: {tips_text}")
        
        elif suggestion["type"] == "timing_rules":
            rules = suggestion["rules"][:1]  # Just 1 rule
            if rules:
                enhancements.append(f"Timing: {rules[0]}")
    
    if not enhancements:
        return None
    
    # Add enhancements to prompt
    enhancement_block = " | ".join(enhancements)
    enhanced_prompt = f"{current_prompt}\n\n[Knowledge-enhanced: {enhancement_block}]"
    
    return enhanced_prompt


def evaluate_and_evolve_all() -> Dict:
    """
    Main entry point for nightly learning.
    Evaluates all sectors and applies knowledge-based improvements.
    """
    data = load_prompts()
    results = {
        "sectors_evaluated": 0,
        "improvements_applied": 0,
        "underperforming": []
    }
    
    # Get underperforming sectors
    underperf = get_underperforming_sectors(threshold=55.0, min_predictions=5)
    results["underperforming"] = [s["sector"] for s in underperf]
    
    for sector, sdata in data.get('prompts', {}).items():
        results["sectors_evaluated"] += 1
        
        current_prompt = sdata.get('current_prompt', '')
        perf = sdata.get('performance', {})
        accuracy = perf.get('accuracy', 100)
        
        # Only enhance underperforming or un-enhanced prompts
        if accuracy < 55 or '[Knowledge-enhanced' not in current_prompt:
            enhanced = apply_knowledge_to_prompt(sector, current_prompt)
            
            if enhanced and enhanced != current_prompt:
                # Don't double-enhance
                if '[Knowledge-enhanced' in current_prompt:
                    # Strip old enhancement first
                    current_prompt = current_prompt.split('\n\n[Knowledge-enhanced')[0]
                    enhanced = apply_knowledge_to_prompt(sector, current_prompt)
                
                if enhanced:
                    update_sector_prompt(
                        sector, 
                        enhanced, 
                        f"Knowledge-enhanced (accuracy was {accuracy:.1f}%)"
                    )
                    results["improvements_applied"] += 1
    
    print(f"\n📊 Evolution complete: {results['improvements_applied']}/{results['sectors_evaluated']} sectors enhanced")
    
    return results


# === CLI Interface ===
if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python prompt_evolution.py report           - Show evolution report")
        print("  python prompt_evolution.py history <SECTOR> - Show sector history")
        print("  python prompt_evolution.py prompt <SECTOR>  - Show current prompt")
        print("  python prompt_evolution.py underperforming  - List weak sectors")
        print("  python prompt_evolution.py suggest <SECTOR> - Show knowledge-based suggestions")
        print("  python prompt_evolution.py evolve           - Run knowledge-based evolution")
        sys.exit(0)
    
    cmd = sys.argv[1]
    
    if cmd == 'report':
        print(generate_evolution_report())
    
    elif cmd == 'history' and len(sys.argv) > 2:
        sector = sys.argv[2].upper()
        history = get_prompt_history(sector)
        if history:
            for h in history:
                print(f"\n--- v{h['version_before']} → v{h['version_after']} ({h['timestamp'][:10]}) ---")
                print(f"Reason: {h['reason']}")
                print(f"Type: {h['change_type']}")
                print(f"Performance at change: {h['performance_at_change']}")
        else:
            print(f"No history for {sector}")
    
    elif cmd == 'prompt' and len(sys.argv) > 2:
        sector = sys.argv[2].upper()
        print(f"=== {sector} Prompt ===")
        print(get_prompt_for_sector(sector))
    
    elif cmd == 'underperforming':
        underperf = get_underperforming_sectors()
        if underperf:
            for s in underperf:
                print(f"🔴 {s['sector']}: {s['accuracy']:.1f}% ({s['total']} predictions)")
        else:
            print("✅ All sectors performing adequately")
    
    elif cmd == 'suggest' and len(sys.argv) > 2:
        sector = sys.argv[2].upper()
        suggestions = suggest_improvements_from_knowledge(sector)
        if suggestions:
            print(f"\n📚 Knowledge-based suggestions for {sector}:")
            for s in suggestions:
                print(f"\n  [{s['type']}]")
                if s['type'] == 'sentiment_signals':
                    for sig in s.get('signals', []):
                        print(f"    - {sig['signal']} → {sig['meaning']} ({sig['confidence']})")
                elif s['type'] == 'sector_specific':
                    for tip in s.get('tips', []):
                        print(f"    - {tip}")
                elif s['type'] == 'timing_rules':
                    for rule in s.get('rules', []):
                        print(f"    - {rule}")
        else:
            print(f"No knowledge available for {sector}")
            print("Tip: Run knowledge_harvester.py first to collect insights")
    
    elif cmd == 'evolve':
        print("🧬 Running knowledge-based prompt evolution...\n")
        results = evaluate_and_evolve_all()
        print(f"\n✅ Results:")
        print(f"   Sectors evaluated: {results['sectors_evaluated']}")
        print(f"   Improvements applied: {results['improvements_applied']}")
        if results['underperforming']:
            print(f"   Underperforming: {', '.join(results['underperforming'])}")
    
    else:
        print(f"Unknown command: {cmd}")
