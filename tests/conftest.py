import sqlite3
import json
import os
import sys
import pytest

# Ensure repository root is on sys.path so `import src.*` works during tests
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

TEST_DB_PATH = "/tmp/shiol_plus_test.db"


def create_schema(conn: sqlite3.Connection):
    cur = conn.cursor()
    # Minimal tables used by endpoints/tests
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS powerball_draws (
            draw_date TEXT PRIMARY KEY,
            n1 INTEGER NOT NULL,
            n2 INTEGER NOT NULL,
            n3 INTEGER NOT NULL,
            n4 INTEGER NOT NULL,
            n5 INTEGER NOT NULL,
            pb INTEGER NOT NULL
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS generated_tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id TEXT UNIQUE,
                n1 INTEGER,
                n2 INTEGER,
                n3 INTEGER,
                n4 INTEGER,
                n5 INTEGER,
                pb INTEGER,
                strategy_used TEXT,
                confidence_score REAL,
                dataset_hash TEXT,
                json_details_path TEXT,
                draw_date TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                evaluated INTEGER DEFAULT 0,
                matches_regular INTEGER DEFAULT 0,
                matches_powerball INTEGER DEFAULT 0,
                prize_won REAL DEFAULT 0
            )
        """
    )

    # Performance tracking used by analytics
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS performance_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id INTEGER NOT NULL,
            draw_date TEXT NOT NULL,
            actual_n1 INTEGER,
            actual_n2 INTEGER,
            actual_n3 INTEGER,
            actual_n4 INTEGER,
            actual_n5 INTEGER,
            actual_pb INTEGER,
            matches_main INTEGER,
            matches_pb INTEGER,
            prize_tier TEXT,
            score_accuracy REAL,
            component_accuracy TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Public counters
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS unique_visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_fingerprint TEXT UNIQUE NOT NULL,
            first_visit TEXT DEFAULT CURRENT_TIMESTAMP,
            last_visit TEXT DEFAULT CURRENT_TIMESTAMP,
            visit_count INTEGER DEFAULT 1
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pwa_installs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_fingerprint TEXT UNIQUE NOT NULL,
            install_date TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Some endpoints reference a legacy 'draws' table; create minimal compatible view
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS draws (
            draw_date TEXT PRIMARY KEY,
            n1 INTEGER, n2 INTEGER, n3 INTEGER, n4 INTEGER, n5 INTEGER, pb INTEGER
        )
        """
    )

    # Users table (for stats and auth lookups)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_premium BOOLEAN DEFAULT 0,
            premium_expires_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_login TEXT,
            login_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            is_admin BOOLEAN DEFAULT 0
        )
        """
    )

    # Premium pass tables for unit tests of premium_pass_service
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS premium_passes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pass_token TEXT UNIQUE NOT NULL,
            jti TEXT UNIQUE NOT NULL,
            email TEXT NOT NULL,
            stripe_subscription_id TEXT UNIQUE,
            stripe_customer_id TEXT,
            user_id INTEGER,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            revoked_reason TEXT,
            device_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS premium_pass_devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pass_id INTEGER NOT NULL,
            device_fingerprint TEXT NOT NULL,
            first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(pass_id, device_fingerprint)
        )
        """
    )

    conn.commit()


def seed_basic_data(conn: sqlite3.Connection):
    cur = conn.cursor()
    # Seed two draws and mirror into legacy 'draws' table
    draws = [
        ("2025-09-01", 1, 2, 3, 4, 5, 6),
        ("2025-09-03", 10, 20, 30, 40, 50, 7),
    ]
    cur.executemany(
        "INSERT OR REPLACE INTO powerball_draws(draw_date,n1,n2,n3,n4,n5,pb) VALUES(?,?,?,?,?,?,?)",
        draws,
    )
    cur.executemany(
        "INSERT OR REPLACE INTO draws(draw_date,n1,n2,n3,n4,n5,pb) VALUES(?,?,?,?,?,?,?)",
        draws,
    )

    # Seed admin user for tests
    import bcrypt
    import hashlib
    # Password: "Admin123!" with SHA-256 pre-hash (to match hash_password_secure)
    prehash = hashlib.sha256("Admin123!".encode('utf-8')).hexdigest()
    password_hash = bcrypt.hashpw(prehash.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    cur.execute(
        """
        INSERT OR REPLACE INTO users (id, email, username, password_hash, is_premium, is_admin, premium_expires_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (1, "admin@shiolplus.com", "admin", password_hash, 1, 1, "2026-12-31T23:59:59")
    )

    # Seed predictions for both dates
    tickets = [
        ("2025-09-01", "strategy_a", 1, 2, 3, 10, 20, 6, 0.9, 0.0, "2025-09-01", None),
        ("2025-09-01", "strategy_b", 11, 12, 13, 14, 15, 7, 0.7, 0.0, "2025-09-01", None),
        ("2025-09-03", "strategy_c", 10, 20, 30, 40, 50, 7, 0.8, 0.0, "2025-09-03", None),
        ("2025-09-03", "strategy_d", 9, 19, 29, 39, 49, 1, 0.6, 0.0, "2025-09-03", None),
    ]
    cur.executemany(
        """
        INSERT INTO generated_tickets(
            draw_date, strategy_used, n1, n2, n3, n4, n5, pb,
            confidence_score, prize_won, created_at, json_details_path
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        tickets,
    )

    # Mark one as evaluated with a small prize in performance_tracking to drive analytics
    cur.execute(
        "INSERT INTO performance_tracking (prediction_id, draw_date, actual_n1, actual_n2, actual_n3, actual_n4, actual_n5, actual_pb, matches_main, matches_pb, prize_tier, score_accuracy, component_accuracy) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            1,
            "2025-09-01",
            1,
            2,
            3,
            4,
            5,
            6,
            3,
            1,
            "Match 3 + PB",
            0.8,
            json.dumps({"dummy": 1}),
        ),
    )

    conn.commit()


@pytest.fixture(scope="session")
def test_db_file():
    # Reset file DB for clean session
    try:
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)
    except Exception:
        pass
    conn = sqlite3.connect(TEST_DB_PATH, check_same_thread=False)
    create_schema(conn)
    seed_basic_data(conn)
    conn.close()
    return TEST_DB_PATH


@pytest.fixture(autouse=True)
def patch_db_path(test_db_file, monkeypatch):
    # Force the application to use the on-disk test database
    import src.database as db
    monkeypatch.setattr(db, "get_db_path", lambda: test_db_file, raising=True)
    yield


@pytest.fixture()
def fastapi_app(monkeypatch):
    # Prevent the APScheduler from starting threads during tests
    import src.api as api

    def _noop_start():
        # Simulate started state without threads
        try:
            api.scheduler.running = True
        except Exception:
            pass

    monkeypatch.setattr(api.scheduler, "start", _noop_start, raising=True)

    def _empty_jobs():
        return []

    monkeypatch.setattr(api.scheduler, "get_jobs", _empty_jobs, raising=True)
    return api.app
