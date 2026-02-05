
import sys
import os
import unittest
import pandas as pd
from unittest.mock import MagicMock

# Ensure root (parent of backend) is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)

from backtest_engine import BacktestEngine

class TestCapitalStats(unittest.TestCase):
    def test_invested_capital_stats(self):
        """Test max/min/avg invested capital calculation"""
        print("\nTesting Capital Stats Calculation...")
        
        # Initialize engine
        engine = BacktestEngine('2022-01-01', '2022-01-10', initial_capital=100000)
        
        # Mock daily_stats
        # Scenario:
        # Day 1: Invested 10,000
        # Day 2: Invested 50,000
        # Day 3: Invested 20,000
        mock_daily_stats = pd.DataFrame([
            {'date': '2022-01-01', 'stock_value': 10000, 'total_value': 100000},
            {'date': '2022-01-02', 'stock_value': 50000, 'total_value': 100000},
            {'date': '2022-01-03', 'stock_value': 20000, 'total_value': 100000},
        ])
        
        # Mock portfolio and trades (needed for analyze_results to run without error)
        engine.portfolio = MagicMock()
        engine.portfolio.get_daily_stats_df.return_value = mock_daily_stats
        engine.portfolio.get_trades_df.return_value = pd.DataFrame() # No trades for this test
        
        # Run analysis
        engine._analyze_by_stock = MagicMock(return_value=pd.DataFrame()) # Mock stock analysis
        results = engine.analyze_results()
        stats = results['overall_stats']
        
        print("\nStats calculated:")
        for k in ['最大投入', '最小投入', '平均投入', '最大利用率', '平均利用率']:
            print(f"  {k}: {stats.get(k)}")
            
        # Verify values
        self.assertEqual(stats['最大投入'], '50,000.00')
        self.assertEqual(stats['最小投入'], '10,000.00')
        # Avg = (10000+50000+20000)/3 = 26666.666...
        self.assertEqual(stats['平均投入'], '26,666.67')
        
        # Verify utilization (Initial = 100,000)
        self.assertEqual(stats['最大利用率'], '50.00%')
        self.assertEqual(stats['平均利用率'], '26.67%')
        
        print("\n✓ Capital Stats Verification Passed")

if __name__ == '__main__':
    unittest.main()
