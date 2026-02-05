#!/usr/bin/env python3
"""
RAG Query Module for Sentiment Analysis
Retrieves relevant company context for news headlines
"""

import json
import os
from typing import Dict, List, Optional
from create_embeddings import get_embedding, cosine_similarity

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EMBEDDINGS_FILE = os.path.join(BASE_DIR, 'embeddings', 'embeddings.json')
PROFILES_DIR = os.path.join(BASE_DIR, 'profiles')


class CompanyRAG:
    """RAG system for company context retrieval"""
    
    def __init__(self):
        self.embeddings_data = None
        self.profiles = {}
        self._load_data()
    
    def _load_data(self):
        """Load embeddings and profiles"""
        # Load embeddings
        if os.path.exists(EMBEDDINGS_FILE):
            with open(EMBEDDINGS_FILE) as f:
                self.embeddings_data = json.load(f)
        
        # Load profiles
        if os.path.exists(PROFILES_DIR):
            for filename in os.listdir(PROFILES_DIR):
                if filename.endswith('.json'):
                    ticker = filename[:-5]
                    with open(os.path.join(PROFILES_DIR, filename)) as f:
                        self.profiles[ticker] = json.load(f)
    
    def get_relevant_context(self, headline: str, top_k: int = 2) -> List[Dict]:
        """
        Get relevant company context for a news headline.
        
        Args:
            headline: News headline text
            top_k: Number of relevant companies to return
            
        Returns:
            List of relevant company profiles with similarity scores
        """
        if not self.embeddings_data:
            return []
        
        # Get headline embedding
        query_embedding = get_embedding(headline)
        if not query_embedding:
            return []
        
        # Find similar companies
        results = []
        for doc in self.embeddings_data.get('documents', []):
            similarity = cosine_similarity(query_embedding, doc['embedding'])
            
            if similarity > 0.3:  # Minimum threshold
                ticker = doc['ticker']
                profile = self.profiles.get(ticker, {})
                
                results.append({
                    'ticker': ticker,
                    'name': profile.get('name', ticker),
                    'similarity': similarity,
                    'summary': profile.get('summary', ''),
                    'risks': profile.get('risks', []),
                    'catalysts': profile.get('catalysts', []),
                    'sentiment_keywords': profile.get('sentiment_keywords', [])
                })
        
        # Sort by similarity
        results.sort(key=lambda x: x['similarity'], reverse=True)
        
        return results[:top_k]
    
    def enrich_sentiment_prompt(self, headline: str, sector: str = None) -> str:
        """
        Create an enriched prompt for sentiment analysis with company context.
        
        Args:
            headline: News headline
            sector: Optional sector filter
            
        Returns:
            Enriched context string to add to sentiment prompt
        """
        context = self.get_relevant_context(headline)
        
        if not context:
            return ""
        
        lines = ["RELEVANT COMPANY CONTEXT:"]
        
        for comp in context:
            lines.append(f"\n{comp['ticker']} ({comp['name']}):")
            lines.append(f"  {comp['summary'][:150]}...")
            
            if comp['risks']:
                lines.append(f"  Key risks: {', '.join(comp['risks'][:3])}")
            if comp['catalysts']:
                lines.append(f"  Catalysts: {', '.join(comp['catalysts'][:3])}")
        
        return '\n'.join(lines)
    
    def analyze_with_context(self, headline: str) -> Dict:
        """
        Full analysis with RAG context.
        Returns headline with enriched context for sentiment analysis.
        """
        context = self.get_relevant_context(headline)
        enriched_prompt = self.enrich_sentiment_prompt(headline)
        
        return {
            'headline': headline,
            'relevant_companies': [c['ticker'] for c in context],
            'context': enriched_prompt,
            'suggested_sectors': list(set(
                self.profiles.get(c['ticker'], {}).get('sector', '') 
                for c in context
            ))
        }


def demo():
    """Demo the RAG system"""
    rag = CompanyRAG()
    
    test_headlines = [
        "NVIDIA announces record Q4 earnings driven by AI chip demand",
        "Apple faces antitrust investigation in EU over App Store policies",
        "Federal Reserve signals potential rate cuts, bank stocks rally",
        "Tesla recalls 2 million vehicles over autopilot concerns",
        "Bitcoin ETF sees record inflows as crypto market surges"
    ]
    
    print("🔍 RAG Company Context Demo\n")
    print("="*60)
    
    for headline in test_headlines:
        print(f"\n📰 {headline}\n")
        
        result = rag.analyze_with_context(headline)
        
        print(f"📊 Relevant companies: {result['relevant_companies']}")
        print(f"🏷️  Suggested sectors: {result['suggested_sectors']}")
        
        if result['context']:
            print(f"\n📝 Context:\n{result['context'][:300]}...")
        
        print("\n" + "-"*60)


if __name__ == '__main__':
    demo()
