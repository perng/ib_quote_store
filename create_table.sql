CREATE TABLE option_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    barCount INTEGER
);