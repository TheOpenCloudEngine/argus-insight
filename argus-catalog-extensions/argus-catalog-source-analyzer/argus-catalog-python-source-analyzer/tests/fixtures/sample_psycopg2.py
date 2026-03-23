import psycopg2


def get_connection():
    return psycopg2.connect(
        host="localhost", port=5432,
        dbname="mydb", user="admin", password="secret",
    )


def find_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email FROM users WHERE active = true")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return rows


def insert_user(username, email):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (username, email) VALUES (%s, %s)", (username, email))
    conn.commit()
    cursor.close()
    conn.close()


def find_user_orders(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT o.order_no, o.total FROM orders o WHERE o.user_id = %s",
        (user_id,),
    )
    return cursor.fetchall()


def delete_inactive_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE active = false")
    conn.commit()


def batch_insert_logs(entries):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.executemany(
        "INSERT INTO audit_log (action, user_id, created_at) VALUES (%s, %s, NOW())",
        entries,
    )
    conn.commit()
