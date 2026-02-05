#!/usr/bin/env python3
"""
Sentiment Portfolio Engine v1.0
- 6 scenarios x €50k = €300k paper trading
- Self-learning model
- Weekly rebalancing
- Earnings calendar awareness
- Stop-loss mechanism
"""

import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class PortfolioEngine:
    def __init__(self):
        self.config = self._load_config()
        self.sectors = self._load_sectors()
        self.model = self._load_or_create_model()
        
    def _load_config(self):
        return {
            'start_capital_per_scenario': 50000,
            'scenarios': ['benchmark', 'momentum', 'aggressive', 'defensive', 'contrarian', 'spy_only'],
            'max_stocks_per_sector': 10,
            'rebalance_day': 'monday',  # Weekly on Monday
            'sectors': ['XLK', 'XLV', 'XLF', 'XLY', 'XLP', 'XLE', 'ICLN', 'XLI', 'XLB', 'XLU', 'XLRE', 'XLC', 'CRYPTO']
        }
    
    def _load_sectors(self):
        path = os.path.join(BASE_DIR, 'sector_assets.json')
        with open(path) as f:
            return json.load(f)['sectors']
    
    def _load_or_create_model(self):
        path = os.path.join(BASE_DIR, 'data', 'learning_model_v2.json')
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return self._create_initial_model()
    
    def _create_initial_model(self):
        """Create initial self-learning model"""
        model = {
            'version': '2.0',
            'created': datetime.now().isoformat(),
            'last_updated': datetime.now().isoformat(),
            
            # Source reliability scores (start at 1.0, learn over time)
            'source_weights': {},
            
            # Sector sensitivity to sentiment
            'sector_sensitivity': {
                sector: {
                    'sentiment_multiplier': 1.0,
                    'optimal_lag_days': 3,
                    'volatility_factor': 1.0,
                    'correct_predictions': 0,
                    'total_predictions': 0
                } for sector in self.config['sectors']
            },
            
            # Time decay weights for sentiment
            'time_decay': {
                'day_0': 1.0,    # Today
                'day_1': 0.7,    # Yesterday
                'day_2': 0.5,    # 2 days ago
                'day_3': 0.3,    # 3 days ago
                'day_4': 0.15,   # 4 days ago
                'day_5_plus': 0.05
            },
            
            # Scenario performance tracking
            'scenario_performance': {
                scenario: {
                    'total_return_pct': 0,
                    'weekly_returns': [],
                    'sharpe_ratio': None,
                    'max_drawdown': 0,
                    'win_rate': None
                } for scenario in self.config['scenarios']
            },
            
            # Learning log
            'learning_history': []
        }
        
        self._save_model(model)
        return model
    
    def _save_model(self, model=None):
        if model is None:
            model = self.model
        model['last_updated'] = datetime.now().isoformat()
        path = os.path.join(BASE_DIR, 'data', 'learning_model_v2.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(model, f, indent=2)
    
    def create_initial_portfolios(self):
        """Create initial portfolio allocations for all scenarios"""
        portfolios = {}
        
        for scenario in self.config['scenarios']:
            portfolios[scenario] = {
                'name': scenario,
                'created': datetime.now().isoformat(),
                'start_capital': self.config['start_capital_per_scenario'],
                'current_value': self.config['start_capital_per_scenario'],
                'cash': 0,
                'positions': {},
                'history': [],
                'stop_loss_pct': self._get_stop_loss(scenario),
                'strategy': self._get_strategy_description(scenario)
            }
            
            # Initialize positions based on scenario
            if scenario == 'spy_only':
                portfolios[scenario]['positions'] = {
                    'SPY': {
                        'shares': 0,  # Will be calculated with real prices
                        'value': self.config['start_capital_per_scenario'],
                        'allocation_pct': 100,
                        'entry_price': None
                    }
                }
            else:
                portfolios[scenario]['positions'] = self._create_initial_allocation(scenario)
        
        # Save portfolios
        path = os.path.join(BASE_DIR, 'data', 'portfolios.json')
        with open(path, 'w') as f:
            json.dump(portfolios, f, indent=2)
        
        return portfolios
    
    def _get_stop_loss(self, scenario):
        """Get stop-loss percentage per scenario"""
        stop_losses = {
            'benchmark': 20,      # Wide stop for buy-and-hold
            'momentum': 12,       # Medium
            'aggressive': 15,     # Can handle volatility
            'defensive': 8,       # Tight stop
            'contrarian': 18,     # Needs room for mean reversion
            'spy_only': 15        # Market stop
        }
        return stop_losses.get(scenario, 15)
    
    def _get_strategy_description(self, scenario):
        descriptions = {
            'benchmark': 'Equal weight across all sectors, no rebalancing based on sentiment',
            'momentum': 'Overweight sectors with positive sentiment, underweight negative',
            'aggressive': 'Concentrate in top 3 bullish sectors, zero in bearish',
            'defensive': 'Base in stable sectors, only move on strong signals (>0.4)',
            'contrarian': 'Buy sectors with negative sentiment, sell on positive',
            'spy_only': 'Simple S&P 500 buy-and-hold benchmark'
        }
        return descriptions.get(scenario, '')
    
    def _create_initial_allocation(self, scenario):
        """Create initial stock allocation based on scenario"""
        positions = {}
        capital = self.config['start_capital_per_scenario']
        num_sectors = len(self.config['sectors'])
        
        if scenario == 'benchmark':
            # Equal weight across all sectors
            per_sector = capital / num_sectors
            stocks_per_sector = 3  # Start with top 3
            
            for sector_code in self.config['sectors']:
                sector = self.sectors.get(sector_code, {})
                stocks = sector.get('stocks', [])[:stocks_per_sector]
                per_stock = per_sector / len(stocks) if stocks else 0
                
                for stock in stocks:
                    positions[stock['ticker']] = {
                        'sector': sector_code,
                        'target_value': per_stock,
                        'target_pct': (per_stock / capital) * 100,
                        'shares': 0,  # Will be calculated with real prices
                        'current_value': per_stock
                    }
        
        elif scenario == 'momentum':
            # Will be adjusted based on sentiment, start equal
            per_sector = capital / num_sectors
            stocks_per_sector = 3
            
            for sector_code in self.config['sectors']:
                sector = self.sectors.get(sector_code, {})
                stocks = sector.get('stocks', [])[:stocks_per_sector]
                per_stock = per_sector / len(stocks) if stocks else 0
                
                for stock in stocks:
                    positions[stock['ticker']] = {
                        'sector': sector_code,
                        'target_value': per_stock,
                        'target_pct': (per_stock / capital) * 100,
                        'shares': 0,
                        'current_value': per_stock
                    }
        
        elif scenario == 'aggressive':
            # Concentrated in fewer sectors (will adjust based on sentiment)
            # Start with top 5 sectors, heavier weight
            top_sectors = self.config['sectors'][:5]
            per_sector = capital / 5
            stocks_per_sector = 5  # More stocks in fewer sectors
            
            for sector_code in top_sectors:
                sector = self.sectors.get(sector_code, {})
                stocks = sector.get('stocks', [])[:stocks_per_sector]
                per_stock = per_sector / len(stocks) if stocks else 0
                
                for stock in stocks:
                    positions[stock['ticker']] = {
                        'sector': sector_code,
                        'target_value': per_stock,
                        'target_pct': (per_stock / capital) * 100,
                        'shares': 0,
                        'current_value': per_stock
                    }
        
        elif scenario == 'defensive':
            # Focus on stable sectors: Utilities, Staples, Healthcare, REITs
            defensive_sectors = ['XLU', 'XLP', 'XLV', 'XLRE', 'XLF']
            per_sector = capital / len(defensive_sectors)
            stocks_per_sector = 4
            
            for sector_code in defensive_sectors:
                sector = self.sectors.get(sector_code, {})
                stocks = sector.get('stocks', [])[:stocks_per_sector]
                per_stock = per_sector / len(stocks) if stocks else 0
                
                for stock in stocks:
                    positions[stock['ticker']] = {
                        'sector': sector_code,
                        'target_value': per_stock,
                        'target_pct': (per_stock / capital) * 100,
                        'shares': 0,
                        'current_value': per_stock
                    }
        
        elif scenario == 'contrarian':
            # Start equal, will buy dips
            per_sector = capital / num_sectors
            stocks_per_sector = 3
            
            for sector_code in self.config['sectors']:
                sector = self.sectors.get(sector_code, {})
                stocks = sector.get('stocks', [])[:stocks_per_sector]
                per_stock = per_sector / len(stocks) if stocks else 0
                
                for stock in stocks:
                    positions[stock['ticker']] = {
                        'sector': sector_code,
                        'target_value': per_stock,
                        'target_pct': (per_stock / capital) * 100,
                        'shares': 0,
                        'current_value': per_stock
                    }
        
        return positions
    
    def calculate_rebalance(self, scenario: str, sentiment_data: Dict) -> Dict:
        """Calculate new target allocations based on sentiment"""
        
        if scenario == 'spy_only':
            return {'SPY': 100}  # Always 100% SPY
        
        if scenario == 'benchmark':
            # No change based on sentiment
            equal_weight = 100 / len(self.config['sectors'])
            return {s: equal_weight for s in self.config['sectors']}
        
        sector_scores = sentiment_data.get('sector_sentiment', {})
        allocations = {}
        
        if scenario == 'momentum':
            # Weight by sentiment score
            base_weight = 100 / len(self.config['sectors'])
            
            for sector in self.config['sectors']:
                score = sector_scores.get(sector, {}).get('score', 0)
                # Adjust weight: +50% for strong positive, -50% for strong negative
                adjustment = score * 50  # -50% to +50%
                weight = max(2, min(20, base_weight + adjustment))  # Min 2%, Max 20%
                allocations[sector] = weight
            
            # Normalize to 100%
            total = sum(allocations.values())
            allocations = {k: (v/total)*100 for k, v in allocations.items()}
        
        elif scenario == 'aggressive':
            # Top 3 sectors get 90%, rest get 10%
            sorted_sectors = sorted(
                self.config['sectors'],
                key=lambda s: sector_scores.get(s, {}).get('score', 0),
                reverse=True
            )
            
            top_3 = sorted_sectors[:3]
            for sector in self.config['sectors']:
                if sector in top_3:
                    allocations[sector] = 30  # 30% each for top 3
                else:
                    allocations[sector] = 1  # 1% for others (10% / 10 sectors)
        
        elif scenario == 'defensive':
            # Only overweight if sentiment > 0.4
            defensive_base = ['XLU', 'XLP', 'XLV', 'XLRE', 'XLF']
            
            for sector in self.config['sectors']:
                score = sector_scores.get(sector, {}).get('score', 0)
                
                if sector in defensive_base:
                    base = 15  # Higher base for defensive
                else:
                    base = 3
                
                # Only increase if very positive
                if score > 0.4:
                    allocations[sector] = base + 5
                elif score < -0.3:
                    allocations[sector] = max(1, base - 5)
                else:
                    allocations[sector] = base
            
            # Normalize
            total = sum(allocations.values())
            allocations = {k: (v/total)*100 for k, v in allocations.items()}
        
        elif scenario == 'contrarian':
            # Buy negative sentiment, sell positive
            base_weight = 100 / len(self.config['sectors'])
            
            for sector in self.config['sectors']:
                score = sector_scores.get(sector, {}).get('score', 0)
                # Inverse: negative sentiment = buy more
                adjustment = -score * 50
                weight = max(2, min(20, base_weight + adjustment))
                allocations[sector] = weight
            
            # Normalize
            total = sum(allocations.values())
            allocations = {k: (v/total)*100 for k, v in allocations.items()}
        
        return allocations
    
    def learn_from_week(self, previous_sentiment: Dict, price_changes: Dict):
        """Update model based on what actually happened"""
        learning_entry = {
            'date': datetime.now().isoformat(),
            'predictions': {},
            'outcomes': {},
            'adjustments': []
        }
        
        for sector in self.config['sectors']:
            predicted_direction = previous_sentiment.get(sector, {}).get('score', 0)
            actual_change = price_changes.get(sector, 0)
            
            # Did we predict correctly?
            correct = (predicted_direction > 0 and actual_change > 0) or \
                     (predicted_direction < 0 and actual_change < 0) or \
                     (abs(predicted_direction) < 0.1 and abs(actual_change) < 1)
            
            learning_entry['predictions'][sector] = predicted_direction
            learning_entry['outcomes'][sector] = actual_change
            
            # Update sector sensitivity
            sens = self.model['sector_sensitivity'][sector]
            sens['total_predictions'] += 1
            if correct:
                sens['correct_predictions'] += 1
                # Increase trust in sentiment for this sector
                sens['sentiment_multiplier'] = min(2.0, sens['sentiment_multiplier'] * 1.05)
                learning_entry['adjustments'].append(f"{sector}: ✓ correct, multiplier +5%")
            else:
                # Decrease trust
                sens['sentiment_multiplier'] = max(0.5, sens['sentiment_multiplier'] * 0.95)
                learning_entry['adjustments'].append(f"{sector}: ✗ wrong, multiplier -5%")
        
        self.model['learning_history'].append(learning_entry)
        self._save_model()
        
        return learning_entry


def initialize_system():
    """Initialize the complete portfolio system"""
    print("🚀 Initializing Sentiment Portfolio System v1.0")
    print("=" * 60)
    
    engine = PortfolioEngine()
    
    print("\n📊 Creating 6 scenarios x €50k = €300k paper portfolio")
    portfolios = engine.create_initial_portfolios()
    
    print("\n✅ Portfolios created:")
    for name, portfolio in portfolios.items():
        print(f"   {name:12} | €{portfolio['start_capital']:,} | Stop-loss: {portfolio['stop_loss_pct']}%")
        print(f"              | {portfolio['strategy'][:60]}...")
    
    print(f"\n🧠 Self-learning model initialized")
    print(f"   - {len(engine.model['sector_sensitivity'])} sectors tracked")
    print(f"   - Time decay: Today 100% → Day 5+ 5%")
    print(f"   - Will learn from weekly outcomes")
    
    print("\n📁 Files created:")
    print(f"   - data/portfolios.json")
    print(f"   - data/learning_model_v2.json")
    
    return engine, portfolios


if __name__ == '__main__':
    initialize_system()
