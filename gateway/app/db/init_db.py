import os
import time
import psycopg2
from loguru import logger

def get_db_connection():
    db_host = os.getenv("POSTGRES_HOST", "localhost")
    db_port = os.getenv("POSTGRES_PORT", "5432")
    db_name = os.getenv("POSTGRES_DB", "quantforge")
    db_user = os.getenv("POSTGRES_USER", "postgres")
    db_password = os.getenv("POSTGRES_PASSWORD", "postgres")

    # Retry database connection if postgres container is still booting up
    for i in range(10):
        try:
            conn = psycopg2.connect(
                host=db_host,
                port=db_port,
                dbname=db_name,
                user=db_user,
                password=db_password
            )
            return conn
        except psycopg2.OperationalError as e:
            logger.warning(f"Database connection attempt {i+1} failed. Retrying in 2 seconds...")
            time.sleep(2)
    raise Exception("Could not connect to the database after 10 attempts.")

def init_database():
    conn = get_db_connection()
    cur = conn.cursor()

    logger.info("Initializing PostgreSQL database schemas...")

    # Create tables
    cur.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        account_id SERIAL PRIMARY KEY,
        name VARCHAR(50) UNIQUE NOT NULL,
        balance NUMERIC(16, 4) NOT NULL DEFAULT 100000.00,
        margin_utilization NUMERIC(16, 4) NOT NULL DEFAULT 0.00
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id BIGINT PRIMARY KEY,
        account_id INT NOT NULL,
        symbol VARCHAR(16) NOT NULL,
        side CHAR(1) NOT NULL, -- 'B' for Buy, 'S' for Sell
        type CHAR(1) NOT NULL, -- 'L' for Limit, 'M' for Market
        price NUMERIC(16, 4),
        quantity BIGINT NOT NULL,
        remaining_quantity BIGINT NOT NULL,
        status CHAR(1) NOT NULL, -- 'N'ew, 'P'artial, 'F'illed, 'C'ancelled, 'R'ejected
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS executions (
        execution_id SERIAL PRIMARY KEY,
        order_id BIGINT NOT NULL,
        trade_id VARCHAR(64) UNIQUE,
        price NUMERIC(16, 4) NOT NULL,
        quantity BIGINT NOT NULL,
        timestamp BIGINT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS positions (
        position_id SERIAL PRIMARY KEY,
        account_id INT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
        symbol VARCHAR(16) NOT NULL,
        quantity BIGINT NOT NULL DEFAULT 0,
        average_price NUMERIC(16, 4) NOT NULL DEFAULT 0.00,
        UNIQUE (account_id, symbol)
    );
    """)

    # Seed default account if empty
    cur.execute("SELECT COUNT(*) FROM accounts;")
    if cur.fetchone()[0] == 0:
        cur.execute("INSERT INTO accounts (name, balance) VALUES ('DefaultTrader', 100000.00);")
        logger.info("Seeded default trader account: 'DefaultTrader' with $100,000.00")

    conn.commit()
    cur.close()
    conn.close()
    logger.info("Database schemas initialized successfully!")

if __name__ == "__main__":
    init_database()
