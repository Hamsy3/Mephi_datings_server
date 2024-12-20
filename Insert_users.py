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


def insert_users():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        login_base="a"
        password = "aaaaaaaa"
        grade = 5.0
        group = "B21-563"
        course = "4"
        for i in range(15):
            login = login_base + str(i+1)
            user_id = str(uuid.uuid4())
            password_salt = password + login  + 'dozen'
            password_bytes = password_salt.encode('utf-8')
            sha256 = hashlib.sha256()
            sha256.update(password_bytes)
            hashed_password = sha256.hexdigest()
            cur.execute('INSERT INTO User_auth(user_id, login, password_hash) VALUES (%s, %s, %s);', (user_id, login, hashed_password))
            cur.execute('INSERT INTO User_data(user_id, grade, first_name, "group", course, is_man) VALUES (%s, %s, %s, %s, %s, true);', (user_id, grade,login, group, course))
            cur.execute('INSERT INTO Interest(fixed_int_id, user_id) VALUES (%s, %s), (%s, %s);', (1, user_id, 2, user_id))
            cur.execute('INSERT INTO Requirement(fixed_req_id, user_id) VALUES (%s, %s), (%s, %s);', (3, user_id, 4, user_id))
            conn.commit()
        return "Success"    
    except Exception as e:
        return  e
    finally:
        cur.close()
        conn.close()
print(insert_users())