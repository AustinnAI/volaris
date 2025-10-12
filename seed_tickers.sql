-- seed_tickers.sql
INSERT INTO tickers (symbol, name, sector, is_active) VALUES
('SPY', 'SPDR S&P 500 ETF', 'ETF', true),
('QQQ', 'Invesco QQQ Trust', 'ETF', true),
('IWM', 'iShares Russell 2000 ETF', 'ETF', true),
('AAPL', 'Apple Inc.', 'Technology', true),
('MSFT', 'Microsoft Corporation', 'Technology', true),
('NVDA', 'NVIDIA Corporation', 'Technology', true),
('TSLA', 'Tesla Inc.', 'Automotive', true),
('AMZN', 'Amazon.com Inc.', 'Consumer Cyclical', true)
ON CONFLICT (symbol) DO NOTHING;