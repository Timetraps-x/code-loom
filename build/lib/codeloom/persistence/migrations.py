CURRENT_SCHEMA_VERSION = 13

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
        continuation_source_stage TEXT,
        continuation_stage TEXT,
        continuation_reason TEXT,
        continuation_attempt_id INTEGER,
        continuation_task_id TEXT,
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
        based_on_execution_hash TEXT,
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
        task_packet_hash TEXT,
        task_packet_ref TEXT,
        task_packet_version TEXT,
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
        start_tree TEXT,
        start_head TEXT,
        snapshot_semantics TEXT,
        start_status_json TEXT,
        snapshot_repositories_json TEXT,
        latest_sealed_tree TEXT,
        latest_seal_revision INTEGER NOT NULL DEFAULT 0,
        latest_review_status TEXT,
        latest_sealed_changes_ref TEXT,
        task_packet_hash TEXT,
        task_packet_ref TEXT,
        task_packet_version TEXT,
        task_packet_json TEXT,
        input_attempts_json TEXT,
        completion_token TEXT,
        completion_status TEXT,
        completion_summary TEXT,
        completion_candidate_ref TEXT,
        completion_candidate_hash TEXT,
        completion_candidate_json TEXT,
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
        summary_ref TEXT,
        summary_text TEXT,
        summary_hash TEXT,
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
        content_hash TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(attempt_id) REFERENCES attempts(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS review_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        attempt_id INTEGER NOT NULL,
        seal_revision INTEGER NOT NULL,
        sealed_tree TEXT NOT NULL,
        status TEXT NOT NULL,
        review_scope TEXT NOT NULL,
        summary_ref TEXT,
        summary_json TEXT,
        summary_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(attempt_id) REFERENCES attempts(id),
        UNIQUE(attempt_id, seal_revision)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sealed_changes (
        attempt_id INTEGER NOT NULL,
        seal_revision INTEGER NOT NULL,
        sealed_tree TEXT NOT NULL,
        manifest_json TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        PRIMARY KEY (attempt_id, seal_revision),
        FOREIGN KEY(attempt_id) REFERENCES attempts(id)
    )
    """,
]
