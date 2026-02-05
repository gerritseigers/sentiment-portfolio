# Sentiment Portfolio System 📈🧠

Een self-learning trading systeem dat nieuwssentiment per sector analyseert en koppelt aan marktbewegingen.

## Status: ✅ Live & Operationeel

- **Paper trading:** €300k verdeeld over 6 scenario's (€50k elk)
- **News sources:** 258 bronnen
- **Sectoren:** 13 (ETF-gebaseerd)
- **Stocks:** 130+

## Architectuur

```
┌─────────────────┐     ┌────────────────────┐     ┌──────────────┐
│  News Harvester │────▶│  Ollama Sentiment  │────▶│  Sector      │
│   (4x/dag)      │     │  (sector prompts)  │     │  Sentiment   │
└─────────────────┘     └────────────────────┘     └──────────────┘
                                │                        │
                        ┌───────┴───────┐               │
                        │ Sentiment     │               │
                        │ Prompt Evo    │               │
                        └───────────────┘               │
                                                        ▼
                                                ┌──────────────┐
                                                │ Ollama       │
                                                │ Portfolio AI │
                                                └──────────────┘
                                                        │
                                                ┌───────┴───────┐
                                                │ Portfolio     │
                                                │ Prompt Evo    │
                                                └───────────────┘
                                                        │
                                                        ▼
┌─────────────────┐     ┌────────────────────┐     ┌──────────────┐
│  Price Data     │────▶│  Daily Learning    │◀────│  Selected    │
│   (APIs)        │     │  (train model)     │     │  Assets      │
└─────────────────┘     └────────────────────┘     └──────────────┘
                                │
                                ▼
                        ┌───────────────┐
                        │ Weekly        │
                        │ Rebalance     │
                        └───────────────┘
```

### Dual AI System

Het systeem gebruikt **twee onafhankelijke AI-lagen**:

1. **Sentiment AI** - Analyseert nieuws → sector sentiment score
2. **Portfolio AI** - Selecteert assets binnen sector op basis van sentiment

Beide hebben eigen prompts die onafhankelijk evolueren op basis van prestaties.

## Prompt Evolution System 🧬

**Nieuw:** Sector-specifieke prompts die evolueren op basis van prestaties.

### Hoe het werkt

1. **Elke sector heeft eigen prompt** - Tech focust op AI/chips/earnings, Finance op Fed/rente, Crypto op regulatie/ETFs
2. **Performance tracking** - Per sector: correct/total predictions
3. **Automatische logging** - Elke prompt-wijziging wordt gelogd in `data/prompt_history/`
4. **Underperformance alerts** - Sectoren onder 50% accuracy worden geflagged

### Bestanden

| Bestand | Functie |
|---------|---------|
| `sector_prompts.json` | Huidige prompts per sector + performance stats |
| `prompt_evolution.py` | Module voor prompt management & historie |
| `data/prompt_history/*.jsonl` | Volledige historie van prompt wijzigingen |

### Commands

```bash
# Bekijk prompt evolutie rapport
python3 prompt_evolution.py report

# Bekijk historie van een sector
python3 prompt_evolution.py history XLK

# Toon huidige prompt voor sector
python3 prompt_evolution.py prompt CRYPTO

# Lijst underperforming sectoren
python3 prompt_evolution.py underperforming
```

### Prompt handmatig updaten

```python
from prompt_evolution import update_sector_prompt

update_sector_prompt(
    "XLK",
    "You analyze TECHNOLOGY sector news. Focus on: AI developments, chip demand...",
    "Added emphasis on AI chip shortage impact"
)
```

## Portfolio AI System 🤖

**Nieuw:** AI-gestuurde asset selectie per sector op basis van sentiment.

### Hoe het werkt

In plaats van random assets te kiezen, vraagt het systeem aan Ollama:
> "Gegeven sentiment +0.6 (bullish) voor Tech sector, welke assets moeten we kopen?"

De AI antwoordt met een JSON allocatie:
```json
{
  "selected_assets": [
    {"ticker": "NVDA", "weight": 0.44, "reason": "AI chip leader"},
    {"ticker": "AMD", "weight": 0.33, "reason": "GPU growth"},
    {"ticker": "AAPL", "weight": 0.22, "reason": "stable base"}
  ],
  "rationale": "Bullish tech favors AI/chip exposure",
  "risk_level": "high"
}
```

### Sector-specifieke logica

| Sector | Bullish | Bearish |
|--------|---------|---------|
| XLK (Tech) | NVDA, AMD (AI/chips) | AAPL, MSFT (defensive) |
| XLF (Finance) | JPM, BAC (banks) | V, MA (payments) |
| XLE (Energy) | COP, EOG (E&P) | XOM, CVX (majors) |
| CRYPTO | BTC + ETH + alts | BTC only |

### Bestanden

| Bestand | Functie |
|---------|---------|
| `portfolio_prompts.json` | Asset selectie prompts per sector |
| `ollama_portfolio.py` | AI portfolio selection module |
| `data/portfolio_prompt_history/` | Historie van prompt wijzigingen |

### Commands

```bash
# Test portfolio selectie
python3 ollama_portfolio.py

# Selecteer assets voor sector
from ollama_portfolio import select_assets
result = select_assets("XLK", sentiment=0.6, scenario="aggressive", budget=10000)
```

---

## 13 Sectoren (ETF-based)

| Code | Sector | Focus Keywords |
|------|--------|----------------|
| XLK | Technology | AI, chips, cloud, FAANG |
| XLV | Healthcare | FDA, biotech, pharma |
| XLF | Financials | Fed, ECB, rates, banks |
| XLY | Consumer Discretionary | Retail, Tesla, Amazon |
| XLP | Consumer Staples | P&G, Walmart, defensive |
| XLE | Energy | Oil, OPEC, Shell |
| ICLN | Clean Energy | Solar, wind, EV, batteries |
| XLI | Industrials | Boeing, manufacturing |
| XLB | Materials | Gold, copper, mining |
| XLU | Utilities | Dividend, regulated |
| XLRE | Real Estate | REITs, mortgage rates |
| XLC | Communication | Streaming, Meta, Google |
| CRYPTO | Cryptocurrency | BTC, ETH, SEC, ETFs |

## 6 Trading Scenario's

| Scenario | Strategie |
|----------|-----------|
| `benchmark` | Buy & hold S&P 500 |
| `momentum` | Volg sterke sentiment trends |
| `aggressive` | Hoge allocatie naar extreme sentiment |
| `defensive` | Focus op stabiele sectoren |
| `contrarian` | Koop bij negatief sentiment |
| `spy_only` | Alleen SPY timing |

## Cron Schedule

| Tijd (UTC) | Job |
|------------|-----|
| 06:00, 12:00, 18:00, 00:00 | News harvest |
| 14:30 Maandag | Weekly rebalance (NYSE open) |
| 17:00 | Daily report |
| 21:30 | Model training |

## Sentiment Scoring

- **-1.0** = Zeer bearish (panic, crash, layoffs)
- **0.0** = Neutraal (routine updates)
- **+1.0** = Zeer bullish (earnings beat, breakthrough)

## Knowledge Harvester 🔬

**Nieuw:** Automatisch verzamelen van kennis over nieuws-trading relaties.

### Hoe het werkt

1. **Wekelijks crawlen** - Verzamelt artikelen over trading, sentiment en nieuws-analyse
2. **Ollama extractie** - Haalt inzichten, signalen en regels uit tekst
3. **Knowledge base** - Slaat alles op in `data/knowledge_base.jsonl`
4. **Prompt evolution** - Gebruikt inzichten om sector prompts te verbeteren

### Bronnen

**Engels:**
- Investopedia (sentiment, trading strategies)
- Corporate Finance Institute
- arXiv finance papers
- Seeking Alpha

**Nederlands:**
- AFM (beleggen info)
- Lynx (sentimentanalyse)
- Beleggen.com

### Bestanden

| Bestand | Functie |
|---------|---------|
| `knowledge_harvester.py` | Hoofdscript voor crawling |
| `knowledge_sources.json` | Geconfigureerde bronnen |
| `data/knowledge_base.jsonl` | Alle verzamelde inzichten |
| `data/knowledge_summary.json` | Gecompileerde samenvatting voor prompts |

### Commands

```bash
# Handmatig harvest starten
python3 knowledge_harvester.py

# Check suggestions voor een sector
python3 prompt_evolution.py suggest XLK

# Apply knowledge to prompts
python3 prompt_evolution.py evolve
```

### Integration met Nightly Learning

De harvester draait automatisch **1x per week** (zondag) als onderdeel van de nightly learning pipeline.
Resultaten worden gebruikt om underperforming sector prompts te verbeteren.

---

## Self-Learning Model

Het systeem leert dagelijks op **vier niveaus**:

### 1. Source Learning
- Welke nieuwsbronnen voorspellen correct?
- Betrouwbare bronnen krijgen hogere weights

### 2. Sentiment Prompt Learning
- Welke sector sentiment prompts werken goed?
- Prompts met <50% accuracy worden geflagged
- Historie in `data/prompt_history/`

### 3. Portfolio Prompt Learning
- Welke asset selectie prompts presteren goed?
- Vergelijkt AI-gekozen assets met marktprestaties
- Historie in `data/portfolio_prompt_history/`

### 4. Knowledge Learning *(nieuw)*
- Wekelijks verzamelen van externe kennis
- Artikelen over trading-nieuws relaties
- Academische papers en expert blogs
- Integreert in prompt evolution

```
Voorbeeld evolutie:
XLK sentiment prompt v1 → v2 → v3 (accuracy 45% → 62% → 71%)
XLK portfolio prompt v1 → v2 (returns +2% → +5%)
Knowledge harvested → 15 signals → Applied to XLF prompt
```

## Setup (MacMini)

```bash
# Ollama moet draaien
ollama serve

# Model (llama3.2:3b voor snelheid)
ollama pull llama3.2:3b

# Test sentiment
python3 ollama_sentiment.py
```

## File Structure

```
sentiment-portfolio/
├── README.md
├── config.json                  # Sector config & sources
├── news_sources.json            # 258 news sources
├── sector_assets.json           # Stocks per sector
│
├── # SENTIMENT AI
├── sector_prompts.json          # Sentiment analysis prompts
├── ollama_sentiment.py          # News sentiment scoring
├── prompt_evolution.py          # Sentiment prompt management
│
├── # PORTFOLIO AI  
├── portfolio_prompts.json       # Asset selection prompts
├── ollama_portfolio.py          # AI asset selection
│
├── # KNOWLEDGE LEARNING
├── knowledge_harvester.py       # External article crawler
├── knowledge_sources.json       # Configured sources (NL + EN)
│
├── # NIGHTLY LEARNING
├── nightly_learning.py          # Complete learning pipeline
├── phase2_feedback.py           # Self-learning feedback loop
├── refined_strategy.py          # Phase 2 strategy refinement
├── embedding_manager.py         # Company profile embeddings
│
├── # CORE SYSTEM
├── harvester.py                 # News scraping
├── harvester_macmini.py         # MacMini version
├── daily_learning.py            # Self-learning model
├── daily_report.py              # Generate reports
├── scenario_report.py           # Daily scenario performance
├── weekly_rebalance.py          # Portfolio rebalancing
├── portfolio_engine.py          # Position management
│
├── data/
│   ├── latest_harvest.json
│   ├── learning_model_v2.json
│   ├── knowledge_base.jsonl     # Harvested knowledge
│   ├── knowledge_summary.json   # Compiled insights
│   ├── phase2_decisions.jsonl   # Trading decisions log
│   ├── phase2_evaluations.jsonl # Performance evaluations
│   ├── nightly_learning_log.jsonl
│   ├── prompt_history/          # Sentiment prompt logs
│   └── portfolio_prompt_history/
└── models/
```

## Disclaimer

⚠️ Dit is een hobby-experiment met paper trading, geen financieel advies!

---
*Laatst bijgewerkt: 4 februari 2025 - Portfolio AI toegevoegd*
