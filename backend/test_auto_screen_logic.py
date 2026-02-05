
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure root (parent of backend) is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)

from backend.backtest_worker import BacktestWorker
from backend.stock_service import StockService

class TestAutoScreen(unittest.TestCase):
    def test_01_direct_screen_stocks(self):
        """Test direct screening via StockService"""
        print("\nTesting StockService.screen_stocks...")
        service = StockService()
        # Use loose criteria
        codes = service.screen_stocks(pe_max=100, dividend_min=0) 
        print(f"  Found {len(codes)} stocks")
        self.assertTrue(len(codes) > 0, "Should find some stocks with loose criteria")

    @patch('backend.backtest_worker.BacktestEngine')
    def test_02_worker_auto_screen(self, MockEngine):
        """Test BacktestWorker integration"""
        print("\nTesting BacktestWorker auto_screen flow...")
        
        # Mock DB
        mock_db = MagicMock()
        
        worker = BacktestWorker(None, mock_db)
        
        # Create task
        task = {
            'task_id': 'test_task_001',
            'mode': 'auto_screen',
            'screen_params': {'pe_max': 50, 'dividend_min': 0.5},
            'start_date': '2022-01-01',
            'end_date': '2022-01-10',
            'initial_capital': 100000,
            'max_positions': 5,
            'stock_codes': []
        }
        
        # Run _execute_backtest
        # It should:
        # 1. Update status to screening
        # 2. Call StockService.screen_stocks (we'll let it call real one or mock it? Let's call real one to be sure)
        # 3. Update task['stock_codes']
        # 4. Init BacktestEngine (Mock)
        # 5. Call engine.load_data
        # 6. Call engine.run
        # 7. Analyze and save results (Mock)
        
        # We need to mock _prepare_results to avoid errors if analyze_results returns mock
        worker._prepare_results = MagicMock(return_value={})
        
        worker._execute_backtest(task)
        
        # 1. Check if stock_codes populated
        print(f"  Task stock codes after run: {len(task['stock_codes'])}")
        self.assertTrue(len(task['stock_codes']) > 0, "Worker should populate stock_codes")
        
        # 2. Check DB calls
        # We expect 'Screening stocks...' status update
        args_list = mock_db.update_task_status.call_args_list
        messages = [call.args[3] for call in args_list]
        print(f"  Status updates: {messages}")
        self.assertTrue(any('筛选' in m for m in messages), "Should have screening status update")
        
        # 3. Check Engine calls
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.load_data.assert_called()
        mock_engine_instance.run.assert_called()
        print("  BacktestEngine.run() was called")

if __name__ == '__main__':
    unittest.main()
