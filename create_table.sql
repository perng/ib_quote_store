CREATE TABLE option_data (
    quote_type VARCHAR(10),
    symbol VARCHAR(10),
    expiration DATE,
    strike DECIMAL(10, 2),
    right CHAR(1),
    date DATETIME,
    open DECIMAL(10, 2),
    high DECIMAL(10, 2),
    low DECIMAL(10, 2),
    close DECIMAL(10, 2),
    volume INTEGER,
    average DECIMAL(10, 2),
    barCount INTEGER,
    PRIMARY KEY (quote_type,symbol, expiration, strike, right, date)
);

CREATE TABLE quote_status (
    quote_type VARCHAR(10),
    symbol VARCHAR(10),
    expiration DATE,
    strike DECIMAL(10, 2),
    right CHAR(1),
    latest DATETIME,
    PRIMARY KEY (quote_type, symbol, expiration, strike, right)
);

CREATE TABLE IF NOT EXISTS vix_data (
                symbol TEXT,
                date TEXT,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                average REAL,
                barCount INTEGER,
                PRIMARY KEY (symbol, date)
);

CREATE VIEW daily_option AS
SELECT 
    quote_type,
    symbol,
    expiration,
    strike,
    right,
    DATE(MAX(date)) AS date,  -- Date of the last hour
    FIRST_VALUE(open) OVER (PARTITION BY quote_type, symbol, expiration, strike, right, DATE(date) ORDER BY date) AS open,  -- Open of the first hour
    MAX(high) AS high,  -- Maximum high of all hours
    MIN(low) AS low,
    LAST_VALUE(close) OVER (PARTITION BY quote_type, symbol, expiration, strike, right, DATE(date) ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS close,  -- Close of the last hour
    SUM(volume) AS volume  -- Sum of volume of all hours    
FROM 
    option_data
WHERE quote_type = 'TRADES'	
GROUP BY 
    quote_type, symbol, expiration, strike, right, DATE(date);

