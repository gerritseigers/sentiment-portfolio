# Company Profiles voor RAG

Deze folder bevat bedrijfsprofielen voor de RAG-enhanced sentiment analyse.

## Structuur

```
company_profiles/
├── profiles/           # JSON profielen per bedrijf
│   ├── AAPL.json
│   ├── MSFT.json
│   └── ...
├── embeddings/         # Vector embeddings
│   └── chroma_db/      # ChromaDB storage
├── templates/          # Profiel templates
└── scripts/
    ├── generate_profile.py   # Genereer profiel voor bedrijf
    ├── create_embeddings.py  # Maak embeddings
    └── query_rag.py          # Query de RAG database
```

## Profiel Schema

```json
{
  "ticker": "AAPL",
  "name": "Apple Inc.",
  "sector": "XLK",
  "summary": "Apple ontwerpt en verkoopt consumer electronics...",
  "business_model": "Hardware + Services ecosystem",
  "key_products": ["iPhone", "Mac", "iPad", "Services"],
  "competitors": ["Samsung", "Google", "Microsoft"],
  "market_position": "Premium segment leader",
  "risks": ["China exposure", "iPhone dependency", "Regulation"],
  "catalysts": ["AI features", "Vision Pro", "Services growth"],
  "recent_events": [],
  "sentiment_keywords": ["iPhone sales", "App Store", "Tim Cook"],
  "updated": "2025-02-04"
}
```

## Embeddings

- **Model:** Ollama `nomic-embed-text` of `mxbai-embed-large`
- **Vector DB:** ChromaDB (lokaal, geen server nodig)
- **Chunk size:** Hele profiel als 1 document (klein genoeg)

## Query Flow

1. Nieuws headline binnenkomt
2. Zoek relevante bedrijfsprofielen via embedding similarity
3. Voeg context toe aan sentiment prompt
4. Verbeterde sentiment score
