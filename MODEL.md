# Sentiment Portfolio Model

*Versie 1.0 - Februari 2026*

Een zelf-lerend, AI-gestuurd sentiment-trading systeem dat nieuwssentiment vertaalt naar portfolio-allocaties.

---

## 🎯 Core Hypothese

> **Positief nieuws sentiment op dag T → positieve prijsbeweging op dag T+1 tot T+3**

Het model test deze hypothese door:
1. Nieuws te verzamelen uit 258+ bronnen
2. Sentiment te analyseren per sector met Ollama AI
3. Portfolio-beslissingen te nemen op basis van sentiment
4. Te leren van de uitkomsten (zelf-correctie)

---

## 🏗️ Architectuur Overzicht

```
┌─────────────────────────────────────────────────────────────────┐
│                      DATA LAYER                                  │
├─────────────────────────────────────────────────────────────────┤
│  News Sources (258+)  │  Price Data (yfinance)  │  Knowledge DB │
│  - NOS, Guardian      │  - Real-time quotes     │  - Harvested  │
│  - BBC, Reuters       │  - Historical data      │    articles   │
│  - Sector-specific    │  - ETF tracking         │  - Insights   │
└───────────┬───────────┴────────────┬────────────┴───────┬───────┘
            │                        │                    │
            ▼                        ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AI LAYER (Dual AI)                          │
├────────────────────────────┬────────────────────────────────────┤
│     SENTIMENT AI           │         PORTFOLIO AI               │
│     (llama3.2:3b)          │         (llama3.1:8b)              │
│                            │                                    │
│  • Analyseert headlines    │  • Selecteert assets per sector   │
│  • Sector-specifieke       │  • Gebruikt embeddings voor       │
│    prompts                 │    company context                │
│  • Score: -1.0 tot +1.0    │  • Bullish/Neutral/Bearish logic  │
│  • Snel (3B model)         │  • Complex (8B model)             │
└────────────────────────────┴────────────────────────────────────┘
            │                        │
            ▼                        ▼
┌─────────────────────────────────────────────────────────────────┐
│                   STRATEGY LAYER                                 │
├─────────────────────────────────────────────────────────────────┤
│  Phase 1: Quick Reaction        │  Phase 2: Refined Strategy    │
│  • Directe sentiment → trade    │  • Company embeddings         │
│  • Snelle beslissingen          │  • News context matching      │
│  • Basis allocatie              │  • Positie verfijning         │
└─────────────────────────────────┴─────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PORTFOLIO LAYER                                │
├─────────────────────────────────────────────────────────────────┤
│  6 Scenario's × €50.000 = €300.000 Paper Trading                │
│                                                                  │
│  • benchmark    - Basis sentiment-gewogen                       │
│  • momentum     - Volgt sterke trends                           │
│  • aggressive   - Hoge allocatie bij sterk sentiment            │
│  • defensive    - Focus op stabiliteit                          │
│  • contrarian   - Koopt bij negatief sentiment                  │
│  • spy_only     - Alleen SPY (benchmark vergelijking)           │
└─────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   LEARNING LAYER                                 │
├─────────────────────────────────────────────────────────────────┤
│  Self-Learning Mechanisms:                                       │
│  • Prompt Evolution - Prompts verbeteren op basis van accuracy  │
│  • Phase 2 Feedback - Evalueer beslissingen na 3 dagen          │
│  • Nightly Learning - Expand sectoren, embeddings, knowledge    │
│  • Knowledge Harvester - Externe artikelen → inzichten          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🧠 Dual AI Systeem

### 1. Sentiment AI (`ollama_sentiment.py`)

**Model:** `llama3.2:3b` (snel, efficiënt)

**Functie:** Vertaalt nieuws headlines naar sentiment scores per sector.

**Sector-specifieke prompts** (`sector_prompts.json`):
```
XLK (Tech):     Focus op AI, chips, cloud, M&A, antitrust
XLV (Health):   Focus op FDA, clinical trials, drug pricing
XLF (Finance):  Focus op rente, krediet, bankregulering
XLE (Energy):   Focus op olie, OPEC, geopolitiek
CRYPTO:         Focus op regulering, adoption, DeFi
... (13 sectoren totaal)
```

**Output:** Score van -1.0 (zeer bearish) tot +1.0 (zeer bullish)

**Prompt Evolution:** Prompts evolueren automatisch op basis van voorspellingsaccuracy. Als een prompt consistent verkeerde signalen geeft, wordt de prompt aangepast.

### 2. Portfolio AI (`ollama_portfolio.py`)

**Model:** `llama3.1:8b` (complexer, nauwkeuriger)

**Functie:** Selecteert specifieke assets binnen een sector op basis van sentiment.

**Logic per sector** (`portfolio_prompts.json`):
```
BULLISH (>0.3):   Kies high-growth, high-beta assets
NEUTRAL:          Balans tussen groei en stabiliteit
BEARISH (<-0.3):  Kies defensive, dividend-paying assets
```

**Voorbeeld (Tech sector):**
- Bullish → NVDA, AMD, AVGO (AI/chip exposure)
- Bearish → AAPL, MSFT, GOOGL (fortress balance sheets)

---

## 📊 Sectoren & Assets

**13 Actieve Sectoren:**

| Code | Sector | ETF | # Stocks | Focus |
|------|--------|-----|----------|-------|
| XLK | Technology | XLK | 12 | AI, cloud, chips |
| XLV | Healthcare | XLV | 10 | Pharma, biotech |
| XLF | Financials | XLF | 10 | Banks, payments |
| XLY | Consumer Disc. | XLY | 10 | Retail, travel |
| XLP | Consumer Staples | XLP | 10 | Defensive |
| XLE | Energy | XLE | 10 | Oil & gas |
| XLI | Industrials | XLI | 10 | Manufacturing |
| XLB | Materials | XLB | 10 | Commodities |
| XLU | Utilities | XLU | 10 | Infrastructure |
| XLRE | Real Estate | XLRE | 10 | REITs |
| XLC | Communication | XLC | 10 | Media, telecom |
| CRYPTO | Crypto | - | 8 | BTC, ETH, SOL |
| ICLN | Clean Energy | ICLN | 10 | Solar, wind, EV |

**Totaal:** ~130 individuele assets

---

## 🔄 Two-Phase Trading Strategy

### Phase 1: Quick Reaction
```
Trigger: Nieuws event / Scheduled scan
Latency: < 5 minuten
Actions:
  1. Harvest headlines
  2. Sentiment AI analyseert per sector
  3. Portfolio AI selecteert assets
  4. Genereer trade signals
```

### Phase 2: Refined Strategy
```
Trigger: 30 min na Phase 1
Latency: 15-30 minuten
Actions:
  1. Fetch missing company embeddings
  2. Match news to specific companies
  3. Verfijn allocaties met extra context
  4. Adjust positions indien nodig
```

**Company Embeddings:**
- Ollama genereert "profielen" per bedrijf
- Bevat: sector, business model, risk factors, competitors
- Wordt gebruikt om nieuws te matchen met relevante bedrijven
- 32/34 embeddings compleet (94% coverage)

---

## 📈 6 Scenario's

Elk scenario krijgt €50.000 startkapitaal:

| Scenario | Strategie | Risk Level |
|----------|-----------|------------|
| **benchmark** | Pure sentiment-gewogen allocatie | Medium |
| **momentum** | Verhoog posities in trending sectoren | High |
| **aggressive** | 2x weight bij sterk sentiment (>0.5) | Very High |
| **defensive** | Max 15% per sector, focus op stabiliteit | Low |
| **contrarian** | Koop bij negatief sentiment | High |
| **spy_only** | 100% SPY ETF (benchmark vergelijking) | Medium |

**Scoring Systeem (1-10):**
```
Score 10:  > +5% return     🟢
Score 8-9: +2% tot +5%      🟢
Score 6-7: -0.5% tot +2%    🟡 (break-even zone)
Score 4-5: -2% tot -0.5%    🟠
Score 1-3: < -2%            🔴
```

---

## 🎓 Self-Learning Mechanisms

### 1. Prompt Evolution (`prompt_evolution.py`)
```
Elke sector prompt heeft:
- version: Versienummer
- performance: { correct, total, accuracy }
- history: Alle vorige versies (JSONL)

Bij accuracy < 50% na 10+ predictions:
→ Genereer verbeterde prompt
→ Bewaar oude versie in history
→ Deploy nieuwe prompt
```

### 2. Phase 2 Feedback (`phase2_feedback.py`)
```
Na 3 dagen:
1. Haal actuele prijzen op
2. Vergelijk met voorspelling
3. Update confidence threshold

Win rate > 60%: Verhoog confidence
Win rate < 40%: Verlaag confidence, adjust strategy
```

### 3. Nightly Learning (`nightly_learning.py`)
```
Draait: 00:00 - 06:00 (6 uur window)

Taken:
1. Expand sectors (ontdek nieuwe sub-sectoren)
2. Fetch missing embeddings
3. Knowledge harvest (wekelijks op zondag)
4. Consolidate learning insights
```

### 4. Knowledge Harvester (`knowledge_harvester.py`)
```
Bronnen: AFM, Lynx, Investopedia, arXiv, CFI
Output: 
- key_insights: Algemene trading wijsheden
- sentiment_signals: Nieuws → prijs relaties
- timing_rules: Wanneer te handelen

Integreert met prompt_evolution voor betere prompts
```

---

## ⏰ Cron Schedule

| Tijd (CET) | Job | Frequentie |
|------------|-----|------------|
| 07:00 | Sentiment Ochtend Scan | Dagelijks |
| 07:30 | Ochtend Todo | Dagelijks |
| 09:00 | Hobart Vlucht Check | Dagelijks |
| 12:00, 15:00, 18:00, 22:00 | News Harvest | 4x/dag |
| 18:00 | Dagelijks Sentiment Rapport | Dagelijks |
| 19:00 | Sentiment Avond Evaluatie | Dagelijks |
| 19:30 | Scenario Dagrapport | Dagelijks |
| 20:00 | Phase 2 Feedback Evaluatie | Dagelijks |
| 21:00 | Daily Self-Reflection | Dagelijks |
| 22:30 | Daily Model Training | Dagelijks |
| 00:00 | Nightly Learning Pipeline | Dagelijks (6hr) |
| Ma 09:00 | Weekly Rebalance | Wekelijks |

---

## 📁 Data Bestanden

```
sentiment-portfolio/
├── config.json              # Hoofd configuratie
├── sector_assets.json       # Stocks per sector
├── sector_prompts.json      # Sentiment AI prompts
├── portfolio_prompts.json   # Portfolio AI prompts
├── company_embeddings.json  # Bedrijfsprofielen
├── knowledge_sources.json   # Externe bronnen
│
├── models/
│   ├── learning_model.json  # Hoofd learning model
│   └── learning_model_v2.json
│
├── data/
│   ├── latest_harvest.json     # Laatste nieuws
│   ├── sentiment_cache.json    # Cached sentiment scores
│   ├── portfolio_state.json    # Huidige posities
│   ├── phase2_decisions.jsonl  # Phase 2 beslissingen
│   ├── refined_strategy_log.jsonl
│   ├── nightly_learning_log.jsonl
│   ├── daily_reflections.jsonl
│   ├── prompt_history.jsonl    # Prompt versie geschiedenis
│   ├── knowledge_base.jsonl    # Externe kennis
│   └── knowledge_summary.json
│
├── history/                 # Historische data (append-only)
│   └── {various}.jsonl
│
└── reports/
    └── daily_YYYY-MM-DD.md  # Dagelijkse rapporten
```

---

## 🔧 Technische Stack

| Component | Technologie |
|-----------|-------------|
| AI Models | Ollama (llama3.2:3b, llama3.1:8b) |
| Runtime | MacMini (lokaal, gratis) |
| Price Data | yfinance |
| News Scraping | Python + web_fetch |
| Scheduling | OpenClaw Cron |
| Storage | JSON/JSONL files |
| Notifications | Telegram |

---

## 📊 Performance Tracking

**Metrics die worden bijgehouden:**

1. **Per Scenario:**
   - Total return %
   - Sharpe ratio
   - Max drawdown
   - Win rate

2. **Per Sector:**
   - Sentiment accuracy
   - Prediction lag (optimal T+n)
   - Source reliability

3. **Per Prompt:**
   - Correct/total predictions
   - Accuracy %
   - Version history

4. **Overall:**
   - Daily P&L
   - Weekly rebalance impact
   - Learning velocity

---

## 🚀 Roadmap

**Completed:**
- ✅ Dual AI architecture
- ✅ 13 sectors, 130 stocks
- ✅ 6 scenario paper trading
- ✅ Self-learning prompts
- ✅ Phase 2 feedback loop
- ✅ Nightly learning pipeline
- ✅ Knowledge harvester

**Planned:**
- [ ] Real-time alerts bij grote sentiment shifts
- [ ] Backtesting framework
- [ ] Multi-model ensemble (vergelijk Ollama modellen)
- [ ] Earnings calendar integratie
- [ ] Risk management (stop-loss automation)

---

*Laatste update: 5 februari 2026*
