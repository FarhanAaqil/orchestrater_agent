import os
DB_PATH = os.path.join(os.path.dirname(__file__), "tracker.db")
from datetime import datetime
import sqlite3

import pathlib
DB_PATH = str(pathlib.Path(__file__).parent.parent / "aaqil.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Applications table
    c.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            company TEXT,
            location TEXT,
            url TEXT,
            source TEXT,
            match_score INTEGER,
            status TEXT DEFAULT 'found',
            cover_letter TEXT,
            applied_at TEXT,
            follow_up_at TEXT,
            notes TEXT
        )
    """)

    # Projects table
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT,
            status TEXT DEFAULT 'active',
            progress INTEGER DEFAULT 0,
            deadline TEXT,
            created_at TEXT,
            github_url TEXT,
            deployed_url TEXT
        )
    """)

    # Tasks table
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            title TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'todo',
            deadline TEXT,
            created_at TEXT,
            completed_at TEXT,
            notes TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    # Goals table
    c.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            target INTEGER,
            current INTEGER DEFAULT 0,
            period TEXT DEFAULT 'weekly',
            created_at TEXT,
            deadline TEXT
        )
    """)

    # Skills table
    c.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            level TEXT DEFAULT 'beginner',
            category TEXT,
            last_used TEXT,
            notes TEXT
        )
    """)

    # Certificates table
    c.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            provider TEXT,
            status TEXT DEFAULT 'completed',
            completed_at TEXT,
            url TEXT,
            skill_area TEXT
        )
    """)

    # Interview prep table
    c.execute("""
        CREATE TABLE IF NOT EXISTS interview_prep (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT,
            role TEXT,
            questions TEXT,
            answers TEXT,
            created_at TEXT,
            interview_date TEXT
        )
    """)

    # Milestones table
    c.execute("""
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            category TEXT,
            date TEXT,
            notes TEXT
        )
    """)

    # Content posts table
    c.execute("""
        CREATE TABLE IF NOT EXISTS content_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            content TEXT,
            platform TEXT,
            status TEXT DEFAULT 'draft',
            url TEXT,
            project TEXT,
            created_at TEXT,
            published_at TEXT,
            views INTEGER DEFAULT 0,
            likes INTEGER DEFAULT 0
        )
    """)

    # Research papers table
    c.execute("""
        CREATE TABLE IF NOT EXISTS research_papers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            abstract TEXT,
            content TEXT,
            project TEXT,
            format TEXT DEFAULT 'ieee',
            status TEXT DEFAULT 'draft',
            target_journal TEXT,
            journal_url TEXT,
            submitted_at TEXT,
            decision TEXT,
            decision_date TEXT,
            created_at TEXT,
            notes TEXT
        )
    """)

    # Journal targets table
    c.execute("""
        CREATE TABLE IF NOT EXISTS journal_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            paper_id INTEGER,
            journal_name TEXT,
            publisher TEXT,
            impact_factor REAL,
            is_open_access INTEGER,
            is_predatory INTEGER DEFAULT 0,
            submission_url TEXT,
            deadline TEXT,
            status TEXT DEFAULT 'identified',
            FOREIGN KEY (paper_id) REFERENCES research_papers(id)
        )
    """)

    # Emails table
    c.execute("""
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            to_email TEXT,
            to_name TEXT,
            subject TEXT,
            body TEXT,
            category TEXT,
            status TEXT DEFAULT 'draft',
            sent_at TEXT,
            reply_received INTEGER DEFAULT 0,
            follow_up_date TEXT,
            notes TEXT,
            created_at TEXT
        )
    """)

    # Chat sessions table
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            created_at TEXT
        )
    """)

    # Chat history table
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            user_message TEXT,
            agent_name TEXT,
            response TEXT,
            created_at TEXT,
            FOREIGN KEY(session_id) REFERENCES chat_sessions(id)
        )
    """)
    
    # Try to add session_id if upgrading existing DB
    try:
        c.execute("ALTER TABLE chat_history ADD COLUMN session_id INTEGER")
    except sqlite3.OperationalError:
        pass # Column likely exists

    conn.commit()
    conn.close()


# ─── Chat Sessions & History ──────────────────────────────────────────────────

def create_chat_session(title: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO chat_sessions (title, created_at) VALUES (?, ?)", 
              (title, datetime.now().isoformat()))
    session_id = c.lastrowid
    conn.commit()
    conn.close()
    return session_id

def get_chat_sessions() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, title, created_at FROM chat_sessions ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "created_at": r[2]} for r in rows]

def delete_chat_session(session_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chat_history WHERE session_id = ?", (session_id,))
    c.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

def save_chat_message(session_id: int, user_message: str, agent_name: str, response: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO chat_history (session_id, user_message, agent_name, response, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, user_message, agent_name, response, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def load_chat_history(session_id: int, limit: int = 50) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT user_message, agent_name, response FROM chat_history WHERE session_id = ? ORDER BY created_at DESC LIMIT ?",
        (session_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    # Return in chronological order (oldest first)
    return [{"user": r[0], "agent": r[1], "response": r[2]} for r in reversed(rows)]

def clear_chat_history():
    # Only used for global clear if needed, otherwise delete_chat_session is used
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM chat_history")
    c.execute("DELETE FROM chat_sessions")
    conn.commit()
    conn.close()


# ─── Applications ─────────────────────────────────────────────────────────────

def insert_job(job: dict):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO applications
        (title, company, location, url, source, match_score, status)
        VALUES (?, ?, ?, ?, ?, ?, 'found')
    """, (job.get("title"), job.get("company"), job.get("location"),
          job.get("url"), job.get("source"), job.get("match_score", 0)))
    conn.commit()
    conn.close()

def update_status(url: str, status: str, cover_letter: str = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if cover_letter:
        c.execute("UPDATE applications SET status=?, cover_letter=?, applied_at=? WHERE url=?",
                  (status, cover_letter, datetime.now().isoformat(), url))
    else:
        c.execute("UPDATE applications SET status=? WHERE url=?", (status, url))
    conn.commit()
    conn.close()

def get_all_jobs(status: str = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM applications WHERE status=? ORDER BY match_score DESC", (status,))
    else:
        c.execute("SELECT * FROM applications ORDER BY match_score DESC")
    rows = c.fetchall()
    conn.close()
    columns = ["id", "title", "company", "location", "url", "source",
               "match_score", "status", "cover_letter", "applied_at", "follow_up_at", "notes"]
    return [dict(zip(columns, row)) for row in rows]

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT status, COUNT(*) FROM applications GROUP BY status")
    stats = dict(c.fetchall())
    conn.close()
    return stats


# ─── Projects ─────────────────────────────────────────────────────────────────

def add_project(name, description="", deadline="", github_url="", deployed_url=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT OR IGNORE INTO projects
        (name, description, deadline, created_at, github_url, deployed_url)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (name, description, deadline, datetime.now().isoformat(), github_url, deployed_url))
    conn.commit()
    conn.close()

def get_projects(status=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM projects WHERE status=?", (status,))
    else:
        c.execute("SELECT * FROM projects")
    rows = c.fetchall()
    conn.close()
    cols = ["id","name","description","status","progress","deadline","created_at","github_url","deployed_url"]
    return [dict(zip(cols, r)) for r in rows]

def update_project_progress(name, progress, status=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status:
        c.execute("UPDATE projects SET progress=?, status=? WHERE name=?", (progress, status, name))
    else:
        c.execute("UPDATE projects SET progress=? WHERE name=?", (progress, name))
    conn.commit()
    conn.close()


# ─── Tasks ────────────────────────────────────────────────────────────────────

def add_task(project_name, title, priority="medium", deadline="", notes=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM projects WHERE name=?", (project_name,))
    row = c.fetchone()
    project_id = row[0] if row else None
    c.execute("""INSERT INTO tasks (project_id, title, priority, deadline, created_at, notes)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (project_id, title, priority, deadline, datetime.now().isoformat(), notes))
    conn.commit()
    conn.close()

def get_tasks(project_name=None, status=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = """SELECT t.*, p.name as project_name FROM tasks t
               LEFT JOIN projects p ON t.project_id = p.id WHERE 1=1"""
    params = []
    if project_name:
        query += " AND p.name=?"
        params.append(project_name)
    if status:
        query += " AND t.status=?"
        params.append(status)
    query += " ORDER BY CASE t.priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    cols = ["id","project_id","title","priority","status","deadline",
            "created_at","completed_at","notes","project_name"]
    return [dict(zip(cols, r)) for r in rows]

def complete_task(task_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE tasks SET status='done', completed_at=? WHERE id=?",
              (datetime.now().isoformat(), task_id))
    conn.commit()
    conn.close()


# ─── Goals ────────────────────────────────────────────────────────────────────

def add_goal(title, target, period="weekly", deadline=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO goals (title, target, period, created_at, deadline) VALUES (?, ?, ?, ?, ?)",
              (title, target, period, datetime.now().isoformat(), deadline))
    conn.commit()
    conn.close()

def update_goal(goal_id, current):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE goals SET current=? WHERE id=?", (current, goal_id))
    conn.commit()
    conn.close()

def get_goals():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM goals ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    cols = ["id","title","target","current","period","created_at","deadline"]
    return [dict(zip(cols, r)) for r in rows]


# ─── Skills ───────────────────────────────────────────────────────────────────

def add_skill(name, level="beginner", category="", notes=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT OR REPLACE INTO skills (name, level, category, last_used, notes)
        VALUES (?, ?, ?, ?, ?)""",
        (name, level, category, datetime.now().isoformat(), notes))
    conn.commit()
    conn.close()

def get_skills(category=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if category:
        c.execute("SELECT * FROM skills WHERE category=? ORDER BY level DESC", (category,))
    else:
        c.execute("SELECT * FROM skills ORDER BY category, level DESC")
    rows = c.fetchall()
    conn.close()
    cols = ["id","name","level","category","last_used","notes"]
    return [dict(zip(cols, r)) for r in rows]


# ─── Certificates ─────────────────────────────────────────────────────────────

def add_certificate(title, provider, status="completed", url="", skill_area=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO certificates (title, provider, status, completed_at, url, skill_area)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (title, provider, status, datetime.now().isoformat(), url, skill_area))
    conn.commit()
    conn.close()

def get_certificates():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM certificates ORDER BY completed_at DESC")
    rows = c.fetchall()
    conn.close()
    cols = ["id","title","provider","status","completed_at","url","skill_area"]
    return [dict(zip(cols, r)) for r in rows]


# ─── Interview Prep ───────────────────────────────────────────────────────────

def add_interview_prep(company, role, questions, answers="", interview_date=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO interview_prep (company, role, questions, answers, created_at, interview_date)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (company, role, questions, answers, datetime.now().isoformat(), interview_date))
    conn.commit()
    conn.close()


# ─── Milestones ───────────────────────────────────────────────────────────────

def add_milestone(title, category, notes=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO milestones (title, category, date, notes) VALUES (?, ?, ?, ?)",
              (title, category, datetime.now().isoformat(), notes))
    conn.commit()
    conn.close()

def get_milestones():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM milestones ORDER BY date DESC")
    rows = c.fetchall()
    conn.close()
    cols = ["id","title","category","date","notes"]
    return [dict(zip(cols, r)) for r in rows]


# ─── Content Posts ────────────────────────────────────────────────────────────

def add_content(title, content, platform, project="", status="draft"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO content_posts (title, content, platform, project, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (title, content, platform, project, status, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_content(platform=None, status=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = "SELECT * FROM content_posts WHERE 1=1"
    params = []
    if platform:
        query += " AND platform=?"
        params.append(platform)
    if status:
        query += " AND status=?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    cols = ["id","title","content","platform","status","url","project","created_at","published_at","views","likes"]
    return [dict(zip(cols, r)) for r in rows]

def update_content_status(content_id, status, url=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE content_posts SET status=?, url=?, published_at=? WHERE id=?",
              (status, url, datetime.now().isoformat(), content_id))
    conn.commit()
    conn.close()


# ─── Research Papers ──────────────────────────────────────────────────────────

def add_paper(title, abstract, content, project, format="ieee"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO research_papers
        (title, abstract, content, project, format, created_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (title, abstract, content, project, format, datetime.now().isoformat()))
    paper_id = c.lastrowid
    conn.commit()
    conn.close()
    return paper_id

def get_papers(status=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status:
        c.execute("SELECT * FROM research_papers WHERE status=? ORDER BY created_at DESC", (status,))
    else:
        c.execute("SELECT * FROM research_papers ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    cols = ["id","title","abstract","content","project","format","status",
            "target_journal","journal_url","submitted_at","decision",
            "decision_date","created_at","notes"]
    return [dict(zip(cols, r)) for r in rows]

def update_paper_status(paper_id, status, journal="", decision=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""UPDATE research_papers
        SET status=?, target_journal=?, decision=?, submitted_at=?
        WHERE id=?""",
        (status, journal, decision, datetime.now().isoformat(), paper_id))
    conn.commit()
    conn.close()

def add_journal_target(paper_id, journal_name, publisher, impact_factor=0,
                       is_open_access=1, submission_url="", deadline=""):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO journal_targets
        (paper_id, journal_name, publisher, impact_factor, is_open_access, submission_url, deadline)
        VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (paper_id, journal_name, publisher, impact_factor, is_open_access, submission_url, deadline))
    conn.commit()
    conn.close()

def get_journal_targets(paper_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM journal_targets WHERE paper_id=? AND is_predatory=0 ORDER BY impact_factor DESC", (paper_id,))
    rows = c.fetchall()
    conn.close()
    cols = ["id","paper_id","journal_name","publisher","impact_factor",
            "is_open_access","is_predatory","submission_url","deadline","status"]
    return [dict(zip(cols, r)) for r in rows]


# ─── Emails ───────────────────────────────────────────────────────────────────

def add_email(to_email, to_name, subject, body, category="general"):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""INSERT INTO emails (to_email, to_name, subject, body, category, created_at)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (to_email, to_name, subject, body, category, datetime.now().isoformat()))
    email_id = c.lastrowid
    conn.commit()
    conn.close()
    return email_id

def mark_email_sent(email_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE emails SET status='sent', sent_at=? WHERE id=?",
              (datetime.now().isoformat(), email_id))
    conn.commit()
    conn.close()

def get_emails(category=None, status=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = "SELECT * FROM emails WHERE 1=1"
    params = []
    if category:
        query += " AND category=?"
        params.append(category)
    if status:
        query += " AND status=?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    cols = ["id","to_email","to_name","subject","body","category",
            "status","sent_at","reply_received","follow_up_date","notes","created_at"]
    return [dict(zip(cols, r)) for r in rows]


# ─── Init ─────────────────────────────────────────────────────────────────────

init_db()