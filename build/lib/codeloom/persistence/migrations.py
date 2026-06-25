CURRENT_SCHEMA_VERSION = 1

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS branch_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        repo_path TEXT NOT NULL,
        branch_name TEXT NOT NULL,
        branch_slug TEXT NOT NULL,
        artifact_root TEXT NOT NULL,
        active_stage TEXT,
        active_spec_hash TEXT,
        active_plan_hash TEXT,
        active_tasks_hash TEXT,
        active_ship_hash TEXT,
        recommended_next TEXT,
        recommended_task_id TEXT,
        updated_at TEXT NOT NULL,
        UNIQUE(repo_path, branch_name)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS artifact_revisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        branch_session_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        path TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        based_on_spec_hash TEXT,
        based_on_plan_hash TEXT,
        based_on_tasks_hash TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(branch_session_id) REFERENCES branch_sessions(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS task_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        branch_session_id INTEGER NOT NULL,
        task_id TEXT NOT NULL,
        task_fingerprint TEXT NOT NULL,
        tasks_hash TEXT NOT NULL,
        title TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(branch_session_id) REFERENCES branch_sessions(id),
        UNIQUE(branch_session_id, task_id, tasks_hash)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS attempts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        branch_session_id INTEGER NOT NULL,
        task_id TEXT NOT NULL,
        attempt_no INTEGER NOT NULL,
        runtime TEXT NOT NULL,
        based_on_spec_hash TEXT,
        based_on_plan_hash TEXT,
        based_on_tasks_hash TEXT,
        task_fingerprint TEXT,
        status TEXT NOT NULL,
        summary TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT,
        FOREIGN KEY(branch_session_id) REFERENCES branch_sessions(id),
        UNIQUE(branch_session_id, task_id, attempt_no)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS verifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL,
        command TEXT,
        status TEXT NOT NULL,
        exit_code INTEGER,
        stdout_ref TEXT,
        stderr_ref TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(attempt_id) REFERENCES attempts(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS findings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        branch_session_id INTEGER NOT NULL,
        attempt_id INTEGER,
        kind TEXT NOT NULL,
        severity TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT NOT NULL,
        suggested_next TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(branch_session_id) REFERENCES branch_sessions(id),
        FOREIGN KEY(attempt_id) REFERENCES attempts(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS runtime_refs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(attempt_id) REFERENCES attempts(id)
    )
    """,
]
