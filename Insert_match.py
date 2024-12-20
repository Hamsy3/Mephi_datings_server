import psycopg2
import uuid
from psycopg2.extras import DictCursor
import hashlib

def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="127.0.0.1",
            database="Mephi_datings",
            user="postgres",
            password="Iorosah5i"
        )
        return conn
    except Exception as e:
        return e


def insert_match():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        login_base="a"
        cur.execute('SELECT user_id FROM User_auth WHERE login = %s;', ('a1',))
        user_liking_id = cur.fetchone()['user_id']
        for i in range(6):
            cur.execute('SELECT user_id FROM User_auth WHERE login = %s;', (login_base + str(i+2),))
            user_liked_id = cur.fetchone()['user_id']
            cur.execute('INSERT INTO "Match"(user_liking_id, user_liked_id) VALUES (%s, %s);', (user_liking_id, user_liked_id))
            conn.commit()
        return "Success"    
    except Exception as e:
        return  e
    finally:
        cur.close()
        conn.close()
print(insert_match())