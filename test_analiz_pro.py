import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from bist_analiz_pro import SmartFetcher, FinancialAnalyzer, SECTOR_MAPPINGS

class TestSmartFetcher(unittest.TestCase):
    @patch('bist_analiz_pro.fetch_financials')
    def test_fetch_success_group1(self, mock_fetch):
        # Setup mock to return dataframe with >5 columns
        mock_df = pd.DataFrame({
            'c1': [1], 'c2': [2], 'c3': [3], 'c4': [4], 'c5': [5], 'c6': [6]
        })

        # Side effect: First call returns DF
        mock_fetch.side_effect = [mock_df, None, None]

        df, group = SmartFetcher.fetch('TEST', '2023', '2023')

        self.assertIsNotNone(df)
        self.assertEqual(group, '1')
        self.assertEqual(mock_fetch.call_count, 1)

    @patch('bist_analiz_pro.fetch_financials')
    def test_fetch_success_group2(self, mock_fetch):
        # Setup mock to return dataframe with >5 columns
        mock_df = pd.DataFrame({
            'c1': [1], 'c2': [2], 'c3': [3], 'c4': [4], 'c5': [5], 'c6': [6]
        })

        # Side effect: First call (Group 1) returns None, Second (Group 2) returns DF
        mock_fetch.side_effect = [None, mock_df, None]

        df, group = SmartFetcher.fetch('TEST', '2023', '2023')

        self.assertIsNotNone(df)
        self.assertEqual(group, '2')
        self.assertEqual(mock_fetch.call_count, 2)

    @patch('bist_analiz_pro.fetch_financials')
    def test_fetch_fail_all(self, mock_fetch):
        mock_fetch.return_value = None

        df, group = SmartFetcher.fetch('FAIL', '2023', '2023')

        self.assertIsNone(df)
        self.assertEqual(mock_fetch.call_count, 3) # Tried 1, 2, 3

class TestFinancialAnalyzer(unittest.TestCase):
    def setUp(self):
        # Create dummy dataframes for different sectors
        self.df_ind = pd.DataFrame({
            'FINANCIAL_ITEM_NAME_TR': ['Hasılat', 'Esas Faaliyet Karı (Zararı)', 'Amortisman Giderleri', 'Dönem Karı (Zararı)', 'Özkaynaklar'],
            '2023/3': [100, 20, 5, 10, 500],
            '2023/6': [250, 60, 12, 35, 520],
            '2023/9': [450, 110, 20, 70, 550],
            '2023/12': [700, 180, 30, 120, 600]
        })

        self.df_bank = pd.DataFrame({
            'FINANCIAL_ITEM_NAME_TR': ['III. NET FAİZ GELİRİ/GİDERİ (I - II)', 'XI. NET FAALİYET KARI/ZARARI (VIII-IX-X)', 'XXIII. NET DÖNEM KARI/ZARARI (XVII+XXII)', 'XVI. ÖZKAYNAKLAR'],
            '2023/3': [500, 300, 200, 5000],
            '2023/6': [1100, 650, 450, 5200]
        })

    def test_detect_sector_industrial(self):
        sector = FinancialAnalyzer.detect_sector(self.df_ind)
        self.assertEqual(sector, "Endüstriyel")

    def test_detect_sector_bank(self):
        sector = FinancialAnalyzer.detect_sector(self.df_bank)
        self.assertEqual(sector, "Banka")

    def test_calculate_period_cumulative(self):
        # Cumulative mode should return raw value
        val = FinancialAnalyzer.calculate_period(self.df_ind, "Endüstriyel", "Revenue", "2023", "6", mode="kumulatif")
        self.assertEqual(val, 250)

    def test_calculate_period_isolated_q1(self):
        # Q1 isolated = Q1 cumulative
        val = FinancialAnalyzer.calculate_period(self.df_ind, "Endüstriyel", "Revenue", "2023", "3", mode="izole")
        self.assertEqual(val, 100)

    def test_calculate_period_isolated_q2(self):
        # Q2 isolated = 6M - 3M = 250 - 100 = 150
        val = FinancialAnalyzer.calculate_period(self.df_ind, "Endüstriyel", "Revenue", "2023", "6", mode="izole")
        self.assertEqual(val, 150)

    def test_calculate_period_isolated_stock_item(self):
        # Equity is a stock item, should NOT subtract previous quarter
        # Q2 Equity = 520 (not 520 - 500)
        val = FinancialAnalyzer.calculate_period(self.df_ind, "Endüstriyel", "Equity", "2023", "6", mode="izole")
        self.assertEqual(val, 520)

    def test_calculate_period_bank_isolated(self):
        # Bank Q2 Operating Profit = 650 - 300 = 350
        val = FinancialAnalyzer.calculate_period(self.df_bank, "Banka", "Operating_Profit", "2023", "6", mode="izole")
        self.assertEqual(val, 350)

    def test_calculate_ebitda_industrial_isolated(self):
        # Q2 Operating Profit (Isolated) = 60 - 20 = 40
        # Q2 Amortization (Isolated) = 12 - 5 = 7
        # EBITDA = 40 + 7 = 47
        val = FinancialAnalyzer.calculate_period(self.df_ind, "Endüstriyel", "EBITDA", "2023", "6", mode="izole")
        self.assertEqual(val, 47)

    def test_calculate_ebitda_industrial_cumulative(self):
        # Q2 Operating Profit (Cum) = 60
        # Q2 Amortization (Cum) = 12
        # EBITDA = 72
        val = FinancialAnalyzer.calculate_period(self.df_ind, "Endüstriyel", "EBITDA", "2023", "6", mode="kumulatif")
        self.assertEqual(val, 72)

if __name__ == '__main__':
    unittest.main()
