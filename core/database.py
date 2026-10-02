import sqlite3
import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jobs_data.db")

class JobDatabase:
    """Управление локальной базой данных SQLite для дедупликации и настроек."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Таблица уже просмотренных / отправленных вакансий
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS seen_jobs (
                    job_id TEXT PRIMARY KEY,
                    title TEXT,
                    company TEXT,
                    location TEXT,
                    source TEXT,
                    url TEXT,
                    published_at TEXT,
                    seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица избранных вакансий
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS saved_jobs (
                    job_id TEXT PRIMARY KEY,
                    title TEXT,
                    company TEXT,
                    url TEXT,
                    saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Таблица настроек и состояния пользователя
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)
            conn.commit()

    def is_job_seen(self, job_id: str) -> bool:
        """Проверяет, отправлялась ли уже эта вакансия соискателю."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM seen_jobs WHERE job_id = ?", (job_id,))
            return cursor.fetchone() is not None

    def mark_job_as_seen(self, job_id: str, title: str = "", company: str = "",
                          location: str = "", source: str = "", url: str = "",
                          published_at: Optional[str] = None):
        """Сохраняет ID вакансии, чтобы никогда не присылать её повторно."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR IGNORE INTO seen_jobs (job_id, title, company, location, source, url, published_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (job_id, title, company, location, source, url, published_at or datetime.now().isoformat()))
            conn.commit()

    def save_favorite_job(self, job_id: str, title: str, company: str, url: str):
        """Сохранить вакансию в Избранное."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO saved_jobs (job_id, title, company, url)
                VALUES (?, ?, ?, ?)
            """, (job_id, title, company, url))
            conn.commit()

    def get_saved_jobs(self) -> List[Dict[str, Any]]:
        """Получить список всех избранных вакансий."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT job_id, title, company, url, saved_at FROM saved_jobs ORDER BY saved_at DESC")
            rows = cursor.fetchall()
            return [{"id": r[0], "title": r[1], "company": r[2], "url": r[3], "saved_at": r[4]} for r in rows]

    def set_setting(self, key: str, value: str):
        """Сохранить параметр (например, chat_id или radius)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
            conn.commit()

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Получить значение параметра."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else default

    def get_stats(self) -> Dict[str, Any]:
        """Статистика работы бота."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM seen_jobs")
            seen_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM saved_jobs")
            saved_count = cursor.fetchone()[0]
            return {
                "total_seen": seen_count,
                "total_saved": saved_count
            }
