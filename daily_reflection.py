#!/usr/bin/env python3
"""
Daily Self-Reflection - AI suggests improvements for itself.

Analyzes:
- Today's decisions and their quality
- Patterns in errors or successes
- Potential blind spots
- Concrete improvement suggestions

Outputs improvement proposals to be reviewed.
"""

import json
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
REFLECTIONS_FILE = os.path.join(DATA_DIR, "daily_reflections.jsonl")

OLLAMA_URL = "http://localhost:11434/api/generate"


def load_today_data():
    """Load all data from today for reflection."""
    today = datetime.now().strftime("%Y-%m-%d")
    data = {
        "date": today,
        "decisions": [],
        "learning": [],
        "errors": []
    }
    
    # Load Phase 2 decisions
    decisions_file = os.path.join(DATA_DIR, "phase2_decisions.jsonl")
    if os.path.exists(decisions_file):
        with open(decisions_file, 'r') as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    if d.get("date") == today:
                        data["decisions"].append(d)
    
    # Load learning log
    learning_file = os.path.join(DATA_DIR, "nightly_learning_log.jsonl")
    if os.path.exists(learning_file):
        with open(learning_file, 'r') as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    if d.get("timestamp", "").startswith(today):
                        data["learning"].append(d)
    
    # Load refined strategy log for errors/patterns
    strategy_file = os.path.join(DATA_DIR, "refined_strategy_log.jsonl")
    if os.path.exists(strategy_file):
        with open(strategy_file, 'r') as f:
            for line in f:
                if line.strip():
                    d = json.loads(line)
                    if d.get("timestamp", "").startswith(today):
                        if d.get("error") or d.get("action") == "keep":
                            data["errors"].append(d)
    
    return data


def ollama_reflect(prompt, timeout=120):
    """Use Ollama to generate reflection."""
    import urllib.request
    try:
        payload = json.dumps({
            "model": "llama3.2:3b",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 800}
        }).encode("utf-8")
        req = urllib.request.Request(OLLAMA_URL, data=payload, 
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")).get("response", "")
    except Exception as e:
        return f"Reflection error: {e}"


def generate_reflection():
    """Generate daily self-reflection with improvement suggestions."""
    today_data = load_today_data()
    
    # Build context
    decisions_summary = f"{len(today_data['decisions'])} portfolio decisions made"
    if today_data['decisions']:
        actions = [d.get('action') for d in today_data['decisions']]
        decisions_summary += f" ({actions.count('adjust')} adjusts, {actions.count('keep')} keeps)"
        
        # Check confidence levels
        confidences = [d.get('confidence', 0) for d in today_data['decisions']]
        avg_conf = sum(confidences) / len(confidences) if confidences else 0
        decisions_summary += f", avg confidence: {avg_conf:.0%}"
    
    learning_summary = f"{len(today_data['learning'])} learning events"
    errors_summary = f"{len(today_data['errors'])} potential issues"
    
    prompt = f"""You are a trading AI doing end-of-day self-reflection. Analyze your performance and suggest concrete improvements.

TODAY'S SUMMARY ({today_data['date']}):
- Decisions: {decisions_summary}
- Learning: {learning_summary}  
- Issues: {errors_summary}

DECISION DETAILS:
{json.dumps(today_data['decisions'][:5], indent=2) if today_data['decisions'] else 'No decisions today'}

REFLECT ON:
1. What patterns do you see in today's decisions?
2. Were confidence levels appropriate?
3. Any blind spots or biases detected?
4. What would you do differently tomorrow?

OUTPUT FORMAT (be specific and actionable):
## Today's Assessment
[1-2 sentences on overall performance]

## What Worked
- [specific thing that worked]

## What Could Improve  
- [specific improvement with concrete action]

## Tomorrow's Focus
- [one specific thing to focus on]

## Self-Improvement Suggestion
[One concrete change to prompts, thresholds, or strategy]"""

    reflection = ollama_reflect(prompt)
    
    # Save reflection
    record = {
        "date": today_data["date"],
        "timestamp": datetime.now().isoformat(),
        "decisions_count": len(today_data["decisions"]),
        "learning_count": len(today_data["learning"]),
        "issues_count": len(today_data["errors"]),
        "reflection": reflection,
        "auto_suggestions": extract_suggestions(reflection)
    }
    
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REFLECTIONS_FILE, 'a') as f:
        f.write(json.dumps(record) + "\n")
    
    return record


def extract_suggestions(reflection_text):
    """Extract actionable suggestions from reflection."""
    suggestions = []
    
    # Look for specific patterns
    if "confidence" in reflection_text.lower():
        if "lower" in reflection_text.lower() or "too high" in reflection_text.lower():
            suggestions.append({"type": "threshold", "action": "review confidence threshold"})
        if "higher" in reflection_text.lower() or "too low" in reflection_text.lower():
            suggestions.append({"type": "threshold", "action": "may need more aggressive threshold"})
    
    if "prompt" in reflection_text.lower():
        suggestions.append({"type": "prompt", "action": "review and update prompts"})
    
    if "diversi" in reflection_text.lower():
        suggestions.append({"type": "strategy", "action": "review diversification"})
    
    if "sector" in reflection_text.lower() and ("missing" in reflection_text.lower() or "add" in reflection_text.lower()):
        suggestions.append({"type": "expansion", "action": "consider adding sectors"})
    
    return suggestions


def get_recent_reflections(days=7):
    """Get recent reflections."""
    if not os.path.exists(REFLECTIONS_FILE):
        return []
    
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    reflections = []
    
    with open(REFLECTIONS_FILE, 'r') as f:
        for line in f:
            if line.strip():
                r = json.loads(line)
                if r.get("date", "") >= cutoff:
                    reflections.append(r)
    
    return reflections


def print_reflection(reflection):
    """Print a formatted reflection."""
    print("=" * 60)
    print(f"DAILY SELF-REFLECTION - {reflection['date']}")
    print("=" * 60)
    print(f"\nStats: {reflection['decisions_count']} decisions, {reflection['learning_count']} learning events")
    print("\n" + reflection.get("reflection", "No reflection generated"))
    
    if reflection.get("auto_suggestions"):
        print("\n📋 AUTO-DETECTED SUGGESTIONS:")
        for s in reflection["auto_suggestions"]:
            print(f"  - [{s['type']}] {s['action']}")


def run_daily_reflection():
    """Run the daily reflection process."""
    print("Generating daily self-reflection...")
    reflection = generate_reflection()
    print_reflection(reflection)
    return reflection


# CLI
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == "run":
            run_daily_reflection()
        elif cmd == "history":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 7
            reflections = get_recent_reflections(days)
            print(f"Last {days} days: {len(reflections)} reflections")
            for r in reflections:
                print(f"\n--- {r['date']} ---")
                print(r.get("reflection", "")[:200] + "...")
        else:
            print(f"Unknown command: {cmd}")
    else:
        print("Daily Self-Reflection")
        print("\nUsage: python3 daily_reflection.py <command>")
        print("\nCommands:")
        print("  run      - Generate today's reflection")
        print("  history  - Show recent reflections")
