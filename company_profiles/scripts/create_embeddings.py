#!/usr/bin/env python3
"""
Create Embeddings for Company Profiles
Uses Ollama for embeddings and stores in ChromaDB
"""

import json
import os
import urllib.request
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(BASE_DIR, 'profiles')
CHROMA_DIR = os.path.join(BASE_DIR, 'embeddings', 'chroma_db')

OLLAMA_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"  # Or: mxbai-embed-large, all-minilm


def get_embedding(text: str) -> Optional[List[float]]:
    """Get embedding vector from Ollama"""
    
    payload = json.dumps({
        "model": EMBED_MODEL,
        "prompt": text
    }).encode('utf-8')
    
    try:
        req = urllib.request.Request(
            OLLAMA_URL,
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result.get('embedding')
            
    except Exception as e:
        print(f"Embedding error: {e}")
        return None


def profile_to_text(profile: Dict) -> str:
    """Convert profile to searchable text"""
    
    parts = [
        f"{profile['ticker']} - {profile['name']}",
        f"Sector: {profile.get('sector', 'unknown')}",
        f"Summary: {profile.get('summary', '')}",
        f"Business: {profile.get('business_model', '')}",
        f"Products: {', '.join(profile.get('key_products', []))}",
        f"Competitors: {', '.join(profile.get('competitors', []))}",
        f"Position: {profile.get('market_position', '')}",
        f"Risks: {', '.join(profile.get('risks', []))}",
        f"Catalysts: {', '.join(profile.get('catalysts', []))}",
        f"Keywords: {', '.join(profile.get('sentiment_keywords', []))}"
    ]
    
    return '\n'.join(parts)


def load_all_profiles() -> List[Dict]:
    """Load all profiles from profiles directory"""
    profiles = []
    
    if not os.path.exists(PROFILES_DIR):
        return profiles
    
    for filename in os.listdir(PROFILES_DIR):
        if filename.endswith('.json'):
            filepath = os.path.join(PROFILES_DIR, filename)
            with open(filepath) as f:
                profiles.append(json.load(f))
    
    return profiles


def create_embeddings_simple() -> Dict:
    """
    Create embeddings and store in simple JSON format.
    For use without ChromaDB dependency.
    """
    profiles = load_all_profiles()
    
    if not profiles:
        print("❌ No profiles found")
        return {}
    
    embeddings_data = {
        'model': EMBED_MODEL,
        'created': datetime.now().isoformat(),
        'documents': []
    }
    
    for i, profile in enumerate(profiles):
        ticker = profile['ticker']
        text = profile_to_text(profile)
        
        print(f"🔄 [{i+1}/{len(profiles)}] Creating embedding for {ticker}...")
        
        embedding = get_embedding(text)
        
        if embedding:
            embeddings_data['documents'].append({
                'ticker': ticker,
                'text': text,
                'embedding': embedding
            })
            print(f"✅ {ticker}: {len(embedding)} dimensions")
        else:
            print(f"❌ {ticker}: Failed")
    
    # Save embeddings
    os.makedirs(os.path.dirname(CHROMA_DIR), exist_ok=True)
    embeddings_file = os.path.join(os.path.dirname(CHROMA_DIR), 'embeddings.json')
    
    with open(embeddings_file, 'w') as f:
        json.dump(embeddings_data, f)
    
    print(f"\n✅ Saved {len(embeddings_data['documents'])} embeddings to {embeddings_file}")
    return embeddings_data


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    dot_product = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    
    if norm_a == 0 or norm_b == 0:
        return 0
    
    return dot_product / (norm_a * norm_b)


def search_similar(query: str, top_k: int = 3) -> List[Dict]:
    """Search for similar company profiles"""
    
    # Load embeddings
    embeddings_file = os.path.join(os.path.dirname(CHROMA_DIR), 'embeddings.json')
    
    if not os.path.exists(embeddings_file):
        print("❌ No embeddings found. Run create_embeddings first.")
        return []
    
    with open(embeddings_file) as f:
        data = json.load(f)
    
    # Get query embedding
    query_embedding = get_embedding(query)
    if not query_embedding:
        print("❌ Failed to create query embedding")
        return []
    
    # Calculate similarities
    results = []
    for doc in data['documents']:
        similarity = cosine_similarity(query_embedding, doc['embedding'])
        results.append({
            'ticker': doc['ticker'],
            'similarity': similarity,
            'text': doc['text'][:200] + '...'
        })
    
    # Sort by similarity
    results.sort(key=lambda x: x['similarity'], reverse=True)
    
    return results[:top_k]


from datetime import datetime

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'search':
        # Search mode
        query = ' '.join(sys.argv[2:]) if len(sys.argv) > 2 else "AI chip semiconductor"
        print(f"🔍 Searching for: {query}\n")
        
        results = search_similar(query, top_k=5)
        
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['ticker']} (similarity: {r['similarity']:.3f})")
            print(f"   {r['text'][:100]}...")
            print()
    else:
        # Create embeddings
        print("Creating embeddings for all profiles...")
        print(f"Using model: {EMBED_MODEL}")
        print()
        
        create_embeddings_simple()
