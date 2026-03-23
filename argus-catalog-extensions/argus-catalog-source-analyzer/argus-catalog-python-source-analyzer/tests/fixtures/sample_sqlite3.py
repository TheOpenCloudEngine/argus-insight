import sqlite3


class TaskRepository:

    def __init__(self, db_path="tasks.db"):
        self.conn = sqlite3.connect(db_path)

    def create_table(self):
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS tasks (id INTEGER PRIMARY KEY, title TEXT, done BOOLEAN)"
        )

    def find_all(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, title, done FROM tasks ORDER BY id")
        return cursor.fetchall()

    def find_pending(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE done = 0")
        return cursor.fetchall()

    def insert(self, title):
        self.conn.execute("INSERT INTO tasks (title, done) VALUES (?, 0)", (title,))
        self.conn.commit()

    def mark_done(self, task_id):
        self.conn.execute("UPDATE tasks SET done = 1 WHERE id = ?", (task_id,))
        self.conn.commit()

    def delete(self, task_id):
        self.conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self.conn.commit()
