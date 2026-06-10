import os
import time
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from loguru import logger

# A process-wide threaded connection pool. Opening a fresh connection per query
# (the previous behaviour) does not survive any real load; the pool bounds the
# number of backend connections and amortizes connect cost.
_pool: ThreadedConnectionPool | None = None


def _db_params() -> dict:
    return dict(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "quantforge"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def init_pool(minconn: int = 1, maxconn: int = 16) -> ThreadedConnectionPool:
    """Create the pool, retrying while Postgres finishes booting."""
    global _pool
    if _pool is not None:
        return _pool

    last_err: Exception | None = None
    for attempt in range(1, 11):
        try:
            _pool = ThreadedConnectionPool(minconn, maxconn, **_db_params())
            logger.info("PostgreSQL connection pool established.")
            return _pool
        except psycopg2.OperationalError as e:
            last_err = e
            logger.warning(f"Database pool init attempt {attempt} failed. Retrying in 2s...")
            time.sleep(2)
    raise RuntimeError(f"Could not establish database pool after 10 attempts: {last_err}")


def get_db_connection():
    """Borrow a connection from the pool (lazily initializing it)."""
    return init_pool().getconn()


def release_db_connection(conn) -> None:
    """Return a connection to the pool. Safe to call with None."""
    if conn is not None and _pool is not None:
        _pool.putconn(conn)


def init_database() -> None:
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        logger.info("Initializing PostgreSQL database schemas...")

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
            side CHAR(1) NOT NULL,
            type CHAR(1) NOT NULL,
            price NUMERIC(16, 4),
            quantity BIGINT NOT NULL,
            remaining_quantity BIGINT NOT NULL,
            status CHAR(1) NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);")

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

        cur.execute("SELECT COUNT(*) FROM accounts;")
        if cur.fetchone()[0] == 0:
            cur.execute("INSERT INTO accounts (name, balance) VALUES ('DefaultTrader', 100000.00);")
            logger.info("Seeded default trader account: 'DefaultTrader' with $100,000.00")

        conn.commit()
        cur.close()
        logger.info("Database schemas initialized successfully!")
    finally:
        release_db_connection(conn)


if __name__ == "__main__":
    init_database()
