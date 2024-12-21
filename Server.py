from flask import Flask, jsonify, request, send_from_directory
import psycopg2
import uuid
from psycopg2.extras import DictCursor
from bs4 import BeautifulSoup
import logging
import requests
#import psycopg2.extras
import hashlib
import re
from datetime import datetime
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from datetime import timedelta
import os
import glob
app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)

#Получение всех данных пользователей
def get_user_data(user_id, status_sent=0):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        cur.execute('SELECT telegram_tag, last_name, last_name_is_hidden, first_name, middle_name, middle_name_is_hidden, \
                    is_man, age, age_is_hidden, height, height_is_hidden, is_smoking, is_smoking_is_hidden, is_drinking, is_drinking_is_hidden, \
                    zodiac, zodiac_is_hidden, fav_music, fav_music_is_hidden, fav_sports, fav_sports_is_hidden, \
                    bio, grade, grade_is_hidden, "group", group_is_hidden, course FROM User_data WHERE user_id = %s;', (user_id,))
        user = cur.fetchone()
        if user is None:
            return {"error": "Пользователя с таким логином не существует"}
        if  status_sent!=2:
            user['telegram_tag'] = None
        if user['group'][0] == 'М':
            user['course'] -= 4
        if user['group'][0] == 'А':
            user['course'] -= 6
        user['course'] =  user['group'][0] + str(user['course'])
        cur.execute('SELECT fr.req_name \
                    FROM Fixed_requirement fr \
                    INNER JOIN Requirement r ON r.fixed_req_id = fr.fixed_req_id \
                    WHERE r.user_id = %s;', (user_id,))
        requirements = cur.fetchall()
        requirements_arr = []
        for i in range(len(requirements)):
            requirements_arr.append(requirements[i]['req_name'])
        cur.execute('SELECT fi.int_name \
                    FROM Fixed_interest fi \
                    INNER JOIN Interest i ON i.fixed_int_id = fi.fixed_int_id \
                    WHERE i.user_id = %s;', (user_id,))
        interests = cur.fetchall()
        interests_arr = []
        for i in range(len(interests)):
            interests_arr.append(interests[i]['int_name'])
        user['interests'] = interests_arr
        user['requirements'] = requirements_arr
        user['grade'] = float(user['grade'])
        if user:
            if user['last_name_is_hidden'] == True:
                del user['last_name']
            if user['middle_name_is_hidden'] == True:
                del user['middle_name']
            if user['age_is_hidden'] == True:
                del user['age']
            if user['height_is_hidden'] == True:
                del user['height']
            if user['is_smoking_is_hidden'] == True:
                del user['is_smoking_is_hidden']
            if user['is_drinking_is_hidden'] == True:
                del user['is_drinking']
            if user['zodiac_is_hidden'] == True:
                del user['zodiac']
            if user['fav_music_is_hidden'] == True:
                del user['fav_music']
            if user['fav_sports_is_hidden'] == True:
                del user['fav_sports']
            if user['grade_is_hidden'] == True:
                del user['grade']
            if user['group_is_hidden'] == True:
                del user['group']
            return user
        else:
            return {"error": "Пользователя с таким логином не существует"}
    except Exception as e: 
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

#Поулчение путей фоток пользователя
def get_user_images(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)      
        cur.execute('SELECT photo_id, photo_name FROM User_photo WHERE user_id = %s;', (user_id,))
        user_photos = cur.fetchall()
        user_photos.sort(key=lambda x: x['photo_id'])
        user_photos_path_arr = []
        for photo in user_photos:
            user_photos_path_arr.append(photo['photo_name'])
        user_photos_path_dict = {"user_photos": user_photos_path_arr}
        return user_photos_path_dict
    except Exception as e: 
        return {"error": str(e)}
    finally:
        cur.close()
        conn.close()

#Установка соединения с БД
def get_db_connection():
    try:
        conn = psycopg2.connect(
            host="127.0.0.1",
            database="Mephi_datings",
            user="postgres",
            password="Your_password"
        )
        return conn
    except Exception as e:
        logging.error(f"Ошибка подключения к базе данных: {e}")
        raise


#Сравнение хэшей паролей
@app.route('/api/users/login', methods=['POST'])
def get_password():
    user_data = request.json
    password_salt = user_data['password'] + user_data['login']  + 'dozen'
    password_bytes = password_salt.encode('utf-8')
    sha256 = hashlib.sha256()
    sha256.update(password_bytes)
    hashed_password = sha256.hexdigest()
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        cur.execute('SELECT user_id, password_hash FROM User_auth WHERE login = %s;', (user_data['login'],))
        user_bd_data =  cur.fetchone()
        user_id = user_bd_data['user_id']
        bd_passwd_hash = user_bd_data['password_hash']
        cur.execute('DELETE FROM "Match" WHERE user_liking_id = %s AND status is NULL;', (user_id,))
        conn.commit()
        if (hashed_password == bd_passwd_hash):
            access_token = create_access_token(identity=user_id)
            refresh_token = create_refresh_token(identity=user_id)
            return jsonify({
                "message": "Хэши паролей сошлись",
                "user_id": f"{user_id}",
                "access_token": access_token,
                "refresh_token": refresh_token
                }), 201
        return jsonify({"error": "Хэши паролей не сошлись"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

#Обновление access
@app.route('/api/token/refresh', methods=['GET'])
@jwt_required(refresh=True)
def refresh_token():
    current_user = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user)
    return jsonify({
        "access_token": new_access_token
    }), 200


#Проверка токена
@app.route('/api/token/validation_access_token/<user_id>', methods=['GET'])
@jwt_required()
def check_token(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        if user_id == 'null':
            return jsonify({"error": "Id is null"}), 400
        cur.execute('DELETE FROM "Match" WHERE user_liking_id = %s AND status is NULL;', (user_id,))
        conn.commit()
        current_user = get_jwt_identity() 
        return jsonify({"message": "Token is valid", "user": current_user}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()



#Начальная регистрация, парсинг группы, среднего балла
@app.route('/api/users/registration', methods=['POST'])
def post_reg():
    session = None 
    cur = None 
    conn = None 
    try:
        user_data = request.json
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        cur.execute('SELECT 1 FROM User_auth WHERE login = %s AND password_hash IS NOT NULL;', (user_data['login'],))
        user = cur.fetchone()
        
        if user:
            return jsonify({"error": "Пользователь с таким логином уже существует"}), 400
        cur.execute('SELECT 1 FROM User_auth WHERE login = %s AND password_hash IS NULL;', (user_data['login'],))
        user_reg_fin = cur.fetchone()
        if user_reg_fin:
            return jsonify({"error": "Пользователь не завершил регистрацию"}), 203
        session = requests.Session()
        session.headers.update({'User-Agent': f"{user_data['user_agent']}"})
        tgt_cookie = user_data['tgt']
        session.cookies.set('tgt', tgt_cookie)
        app.logger.info(tgt_cookie, user_data['user_agent'], user_data['login'])
        login_response_user = session.get("https://home.mephi.ru/users")
        profile_response = session.get("https://home.mephi.ru")

        if profile_response.ok and login_response_user.ok:
            profile_soup = BeautifulSoup(profile_response.content, 'html.parser')
            average_score_div = profile_soup.find('div', class_='panel panel-counter panel-mark')
            schedule_link = profile_soup.find_all('a', class_='btn btn-primary btn-outline', href=True)

            if average_score_div and schedule_link:
                average_score = average_score_div.find('h3', class_='count').text
                group = schedule_link[1].text.split('.')[0]
                now = datetime.now()
                current_year = now.year + (1 if now.month >= 9 else 0)
                course = current_year - 2000 - int(schedule_link[1].text.split('.')[0][1:3])
                if group[0] == 'М':
                    course += 4
                if group[0] == 'А':
                    course += 6
                user_id = str(uuid.uuid4())
                cur.execute('INSERT INTO User_auth (user_id, login) VALUES (%s, %s);',
                            (user_id, user_data['login']))
                cur.execute('INSERT INTO User_data (user_id, grade, "group", course) VALUES (%s, %s, %s, %s);',
                            (user_id, average_score, group, course))
                conn.commit()
                return jsonify({"message": "Пользователь успешно добавлен", "user_id": f"{user_id}"}), 201
        return jsonify({"error": "Произошла ошибка при извлечении данных"}), 500
    except Exception as e:
        logging.error(f"Ошибка при регистрации пользователя: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if session != None:
            session.close()
        cur.close()
        conn.close()


#Добавить в БД хэш пароля, телегам тэг
@app.route('/api/users/telegram', methods=['POST'])
def post_reg_telegram():
    try:
        user_data = request.json
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        cur.execute('SELECT login FROM User_auth WHERE user_id = %s;', (user_data['user_id'],))
        user = cur.fetchone()
        if user is None:
            return jsonify({"error": "Пользователя с таким логином не существует"}), 400
        password_salt = user_data['password'] + user['login']  + 'dozen'
        password_bytes = password_salt.encode('utf-8')
        sha256 = hashlib.sha256()
        sha256.update(password_bytes)
        hashed_password = sha256.hexdigest()
        cur.execute('UPDATE User_auth SET password_hash = %s WHERE user_id = %s;',
                    (hashed_password, user_data['user_id']))
    
        cur.execute('UPDATE User_data SET telegram_tag = %s WHERE user_id = %s;',
                    (user_data['telegram_tag'], user_data['user_id']))
        conn.commit()
        relative_folder_path = os.path.join(os.path.dirname(__file__), f"user_photos/{user_data['user_id']}")
        os.makedirs(relative_folder_path, exist_ok=True)
        return jsonify({"message": "Пользователь успешно зарегистрирован"}), 201
    except Exception as e:
        logging.error(f"Ошибка при регистрации пользователя: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


#Достать все данные пользователя кроме картинок
@app.route('/api/users/user_data/<user_id>', methods=['GET'])
@jwt_required()
def get_user_data_route(user_id):
    user = get_user_data(user_id, status_sent=2)
    try:
        if user:
            return jsonify(user), 200
        else:
            return jsonify({"error": "Пользователя с таким логином не существует"}), 400
    except Exception as e: 
        logging.error(f"Ошибка при получении пользователей: {e}")
        return jsonify({"error": str(e)}), 500

#Добавить все данные пользователя кроме картинок
@app.route('/api/users/user_data', methods=['POST']) #password_hash->login
@jwt_required()
def post_user_data():
    user_data = request.json
    app.logger.info(user_data)
    conn = None
    cur = None
    try:
        profanity_pattern = re.compile(r"""
        \b(
        ((у|[нз]а|(хитро|не)?вз?[ыьъ]|с[ьъ]|(и|ра)[зс]ъ?|(о[тб]|п[оа]д)[ьъ]?|(.\B)+?[оаеи-])-?)?(
        [её](б(?!о[рй]|рач)|п[уа](ц|тс))|
        и[пб][ае][тцд][ьъ]
        ).*?|

        ((н[иеа]|(ра|и)[зс]|[зд]?[ао](т|дн[оа])?|с(м[еи])?|а[пб]ч|в[ъы]?|пр[еи])-?)?ху([яйиеёю]|л+и(?!ган)).*?|

        бл([эя]|еа?)([дт][ьъ]?)?|

        \S*?(
        п(
            [иеё]зд|
            ид[аое]?р|
            ед(р(?!о)|[аое]р|ик)|
            охую
        )|
        бля([дбц]|тс)|
        [ое]ху[яйиеё]|
        хуйн
        ).*?|

        (о[тб]?|про|на|вы)?м(
        анд([ауеыи](л(и[сзщ])?[ауеиы])?|ой|[ао]в.*?|юк(ов|[ауи])?|е[нт]ь|ища)|
        уд([яаиое].+?|е?н([ьюия]|ей))|
        [ао]л[ао]ф[ьъ]([яиюе]|[еёо]й)
        )|

        елд[ауые].*?|
        ля[тд]ь|
        ([нз]а|по)х|
        су(ка|ч[ао]ра|чка|чище|ченыш)
        )\b
        """, re.VERBOSE | re.IGNORECASE)
        for key, value in user_data.items():
            if value == '' or value =='null':
                user_data[key] = None
        if user_data['bio'] and profanity_pattern.search(user_data['bio']) \
            or user_data['fav_music'] and profanity_pattern.search(user_data['fav_music']) \
            or user_data['fav_sports'] and profanity_pattern.search(user_data['fav_sports']) \
            or user_data['first_name'] and profanity_pattern.search(user_data['first_name']) \
            or user_data['middle_name'] and profanity_pattern.search(user_data['middle_name']) \
            or user_data['last_name'] and profanity_pattern.search(user_data['last_name']): 
            return jsonify({"message": "Ненормативная лексика"}), 406
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        if user_data['is_man'] == 'Мужской':
            user_data['is_man'] = 'true'
        else:
            user_data['is_man'] = 'false'
        cur.execute('UPDATE User_data SET telegram_tag = %s, last_name = %s, last_name_is_hidden = %s, \
                     first_name = %s, middle_name = %s, middle_name_is_hidden = %s,  grade_is_hidden = %s, \
                     is_man = %s, age = %s, age_is_hidden = %s, height = %s, height_is_hidden = %s, is_smoking = %s, \
                     is_smoking_is_hidden = %s, group_is_hidden = %s, is_drinking = %s, is_drinking_is_hidden = %s, \
                     zodiac = %s, zodiac_is_hidden = %s, fav_music = %s, fav_music_is_hidden = %s, fav_sports = %s, fav_sports_is_hidden = %s, bio = %s WHERE user_id = %s;',
            (user_data['telegram_tag'],
            user_data['last_name'],
            user_data['last_name_is_hidden'],
            user_data['first_name'],
            user_data['middle_name'],
            user_data['middle_name_is_hidden'],
            user_data['grade_is_hidden'],
            user_data['is_man'],
            user_data['age'],
            user_data['age_is_hidden'],
            user_data['height'],
            user_data['height_is_hidden'],
            user_data['is_smoking'],
            user_data['is_smoking_is_hidden'],
            user_data['group_is_hidden'],
            user_data['is_drinking'],
            user_data['is_drinking_is_hidden'],
            user_data['zodiac'],
            user_data['zodiac_is_hidden'],
            user_data['fav_music'],
            user_data['fav_music_is_hidden'],
            user_data['fav_sports'],
            user_data['fav_sports_is_hidden'],
            user_data['bio'], 
            user_data['user_id']))
        conn.commit()
        interests = tuple(user_data['interests']) if user_data['interests'] else ('',)
        interests_arr_id = []
        cur.execute('SELECT fixed_int_id \
                    FROM Fixed_interest \
                    WHERE int_name IN %s;', (interests,))
        interests = cur.fetchall()
        for i in range(len(interests)):
            interests_arr_id.append(interests[i]['fixed_int_id'])
        cur.execute('DELETE FROM Interest \
                 WHERE user_id = %s;',
                (user_data['user_id'],))
        for i in range(len(interests_arr_id)):
            cur.execute('INSERT INTO Interest \
                        VALUES (%s, %s) \
                        ON CONFLICT (fixed_int_id, user_id) DO NOTHING;',
                        (interests_arr_id[i], user_data['user_id']))
        conn.commit()

        requirements = tuple(user_data['requirements']) if user_data['requirements'] else ('',)
        requirements_arr_id = []
        cur.execute('SELECT fixed_req_id \
                    FROM Fixed_requirement \
                    WHERE req_name IN %s;', (requirements,))
        requirements = cur.fetchall()
        for i in range(len(requirements)):
            requirements_arr_id.append(requirements[i]['fixed_req_id'])
        cur.execute('DELETE FROM Requirement \
                 WHERE user_id = %s;',
                (user_data['user_id'],))
        for i in range(len(requirements_arr_id)):
            cur.execute('INSERT INTO Requirement \
                        VALUES (%s, %s) \
                        ON CONFLICT (fixed_req_id, user_id) DO NOTHING;',
                        (requirements_arr_id[i], user_data['user_id']))
        conn.commit()
        return jsonify({"message": "Данные успешно обновлены"}), 200
    except Exception as e: 
        logging.error(f"Ошибка при получении пользователей: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/users/users_unactioned/<user_id>', methods=['DELETE']) 
@jwt_required()
def delete_users_unactioned_route(user_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        cur.execute('DELETE FROM "Match" WHERE user_liking_id = %s AND status is NULL;', (user_id,))
        conn.commit()
        return jsonify({"message": "Записи без статуса удалены"}), 200
    except Exception as e: 
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
        cur.close()


#Получить несколько данных пользователей
@app.route('/api/users/users_data/<user_liking_id>', methods=['GET']) #Добавим рекомендации
@jwt_required()
def get_users_data_route(user_liking_id):
    course_start = request.args.get('course_start')
    course_end = request.args.get('course_end')
    gender_man = request.args.get('gender_man')
    gender_woman = request.args.get('gender_woman')
    limit = request.args.get('limit')
    if course_start == 'null':
        course_start = 1
    if course_end == 'null':
        course_end = 9
    if gender_man == 'null':
        gender_man = 'true'
    if gender_woman == 'null':
        gender_woman = 'true'
    if limit == 'null':
        limit = '5'
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        #cur.execute('SELECT user_liked_id FROM "Match" WHERE user_liking_id = %s;', (user_liking_id,))
        #user_liked_id_arr = cur.fetchall()
        #user_liked_ids = tuple(item["user_liked_id"] for item in user_liked_id_arr) + (user_liking_id,)
        gender_filter = ''
        if gender_man == 'true' and gender_woman == 'false':
            gender_filter = 'AND is_man = true'
        if gender_man == 'false' and gender_woman == 'true':
            gender_filter = 'AND is_man = false'
        query_recommendation = f'''
        WITH User_reqs AS (
            SELECT user_id, COUNT(*) AS req_count 
            FROM Requirement 
            WHERE fixed_req_id IN (
                SELECT fixed_req_id 
                FROM Requirement
                WHERE user_id = %s
            ) 
            GROUP BY user_id
        ),
        User_interests AS (
            SELECT user_id, COUNT(*) AS int_count 
            FROM Interest 
            WHERE fixed_int_id IN ( 
                SELECT fixed_int_id 
                FROM Interest 
                WHERE user_id = %s
            ) 
            GROUP BY user_id
        ),
        User_course_diff AS (
            SELECT user_id,
            ABS(course - (SELECT course FROM User_data WHERE user_id = %s)) AS course_diff 
            FROM User_data 
        ),
        Ranked_users AS (
            SELECT 
            u.user_id, 
            COALESCE(ur.req_count, 0) AS req_count, 
            COALESCE(ui.int_count, 0) AS int_count, 
            ucd.course_diff 
            FROM User_data u 
            LEFT JOIN User_reqs ur ON u.user_id = ur.user_id 
            LEFT JOIN User_interests ui ON u.user_id = ui.user_id 
            LEFT JOIN User_course_diff ucd ON u.user_id = ucd.user_id 
            WHERE u.user_id != %s 
            AND u.user_id NOT IN (
                SELECT user_liked_id  
                FROM "Match" 
                WHERE user_liking_id = %s
            ) 
            AND course >= %s AND course <= %s {gender_filter}
            AND first_name IS NOT NULL
        )
        SELECT user_id, req_count, int_count, course_diff 
        FROM Ranked_users 
        ORDER BY req_count DESC, int_count DESC, course_diff ASC 
        LIMIT %s;
        '''
        cur.execute(query_recommendation, (user_liking_id, user_liking_id, user_liking_id, user_liking_id, user_liking_id, course_start, course_end, limit))
        #cur.execute(f'SELECT user_id FROM User_data WHERE user_id NOT IN %s AND course >= %s AND course <= %s{gender_filter}', (user_liked_ids, course_start, course_end))
        user_nliked_id_arr = cur.fetchall()
        for i in range (len(user_nliked_id_arr)):
            cur.execute('INSERT INTO "Match"(user_liking_id, user_liked_id) VALUES (%s, %s);', (user_liking_id, user_nliked_id_arr[i]['user_id']))
            conn.commit()
        users_data_photo = {"users_data": [], "users_photos": []}
        for i in range(len(user_nliked_id_arr)):
            user_id = user_nliked_id_arr[i]['user_id']
            users_data_photo["users_data"].append(get_user_data(user_id))
            users_data_photo["users_data"][i]['user_id'] = user_id
            users_data_photo["users_photos"].append(get_user_images(user_id))

        return jsonify(users_data_photo), 200
    except Exception as e: 
        logging.error(f"Ошибка при получении пользователей: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()



#0-Дизлайк, 1-Мы лайкнули, 2-Взаимный лайк, засчитать действия пользователя
@app.route('/api/users/users_status', methods=['POST'])
@jwt_required()
def post_users_status_route():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        users_data = request.json
        user_liking_id = users_data['user_liking_id']
        user_liked_id = users_data['user_liked_id']
        status_sent = users_data['status']
        message = users_data['message']
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        #Проверка на то есть ли вообще такая связь, которую можно апдейтить
        cur.execute('SELECT * FROM "Match" WHERE user_liking_id = %s AND user_liked_id = %s;', (user_liking_id, user_liked_id))
        check_connectivity = cur.fetchone()
        cur.execute('SELECT * FROM "Match" WHERE user_liking_id = %s AND user_liked_id = %s;', (user_liked_id, user_liking_id))
        check_connectivity_reverse = cur.fetchone()
        if (status_sent == 1 or status_sent == 0) and check_connectivity is None and check_connectivity_reverse is None:
            return jsonify({"error": "No such connectivity"}), 400 #Нет такой связи
        if (status_sent == 2 or status_sent == 3) and check_connectivity is None and check_connectivity_reverse is None:
            return jsonify({"error": "No such connectivity"}), 400 #Нет такой связи
        cur.execute('SELECT status FROM "Match" WHERE user_liking_id = %s AND user_liked_id = %s;', (user_liked_id, user_liking_id))
        user_liked_is_mutual = cur.fetchone()
        app.logger.info(user_liked_is_mutual)
        if user_liked_is_mutual and user_liked_is_mutual['status'] == 1 and status_sent != 0:
            if message:
                cur.execute('UPDATE "Match" SET status = 2, message = %s WHERE user_liking_id = %s and user_liked_id = %s;', \
                             (message, user_liking_id, user_liked_id))
                cur.execute('UPDATE "Match" SET status = 2 WHERE user_liking_id = %s and user_liked_id = %s ;', \
                             (user_liked_id, user_liking_id))
            else:
                cur.execute('UPDATE "Match" SET status = 2 WHERE user_liking_id = %s and user_liked_id = %s;', \
                             (user_liking_id, user_liked_id))
                cur.execute('UPDATE "Match" SET status = 2 WHERE user_liking_id = %s and user_liked_id = %s;', \
                             (user_liked_id, user_liking_id))
            conn.commit()
        else:
            if message:
                cur.execute('UPDATE "Match" SET status = %s, message = %s WHERE user_liking_id = %s and user_liked_id = %s;', \
                            (status_sent, message, user_liking_id, user_liked_id))
            else:
                cur.execute('UPDATE "Match" SET status = %s WHERE user_liking_id = %s and user_liked_id = %s;', \
                            (status_sent, user_liking_id, user_liked_id))
            conn.commit()
        return jsonify({"message": "User action is registered"}), 200
    except Exception as e: 
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


#Получить дизлайки, наши лайки, взаимные лайки, кто нас лайкнул. 0-Дизлайк, 1-Мы лайкнули, 2-Взаимный лайк, 3-Нас лайкнули,
@app.route('/api/users/users_status/<user_liking_id>', methods=['GET'])
@jwt_required()
def get_users_match_route(user_liking_id):
    try:
        status_sent = request.args.get('status_sent')
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        users_data_photo = {"users_data": [], "users_photos": []}
        if status_sent == '3':
            cur.execute('SELECT user_liking_id, message FROM "Match" WHERE user_liked_id = %s AND status = 1;', (user_liking_id,))
            user_liked_us_id_arr = cur.fetchall() #лайкнули нас
            for i in range(len(user_liked_us_id_arr)):
                user_id = user_liked_us_id_arr[i]['user_liking_id']
                users_data_photo["users_data"].append(get_user_data(user_id))
                users_data_photo["users_data"][i]['user_id'] = user_id
                users_data_photo["users_data"][i]['message_liked'] = user_liked_us_id_arr[i]['message']
                users_data_photo["users_photos"].append(get_user_images(user_id))
        elif status_sent == '1':
            cur.execute('SELECT user_liked_id, message FROM "Match" WHERE user_liking_id = %s AND status = 1;', (user_liking_id,)) 
            user_we_liked_id_arr = cur.fetchall() #мы лайкнули или взаимный
            for i in range(len(user_we_liked_id_arr)):
                user_id = user_we_liked_id_arr[i]['user_liked_id']
                users_data_photo["users_data"].append(get_user_data(user_id, int(status_sent)))
                users_data_photo["users_data"][i]['user_id'] = user_id
                users_data_photo["users_data"][i]['message'] = user_we_liked_id_arr[i]['message']
                users_data_photo["users_photos"].append(get_user_images(user_id))
        elif status_sent == '0':
            cur.execute('SELECT user_liked_id FROM "Match" WHERE user_liking_id = %s AND status = 0;', (user_liking_id,)) 
            user_we_liked_id_arr = cur.fetchall()
            for i in range(len(user_we_liked_id_arr)):
                user_id = user_we_liked_id_arr[i]['user_liked_id']
                users_data_photo["users_data"].append(get_user_data(user_id, int(status_sent)))
                users_data_photo["users_data"][i]['user_id'] = user_id
                users_data_photo["users_photos"].append(get_user_images(user_id))
        elif status_sent == '2':
            cur.execute('SELECT user_liked_id, message FROM "Match" WHERE user_liking_id = %s AND status = 2;', (user_liking_id,)) 
            user_we_liked_id_arr = cur.fetchall() #мы лайкнули или взаимный
            for i in range(len(user_we_liked_id_arr)):
                cur.execute('SELECT message FROM "Match" WHERE user_liking_id = %s AND user_liked_id = %s AND status = 2;',  \
                            (user_we_liked_id_arr[i]['user_liked_id'], user_liking_id)) 
                user_liked_us = cur.fetchone() #мы лайкнули или взаимный
                user_id = user_we_liked_id_arr[i]['user_liked_id']
                users_data_photo["users_data"].append(get_user_data(user_id, int(status_sent)))
                users_data_photo["users_data"][i]['user_id'] = user_id
                users_data_photo["users_data"][i]['message'] = user_we_liked_id_arr[i]['message']
                users_data_photo["users_data"][i]['message_liked'] = user_liked_us['message']
                users_data_photo["users_photos"].append(get_user_images(user_id))
        return jsonify(users_data_photo), 200
    except Exception as e: 
        logging.error(f"Ошибка при получении пользователей: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


#Загрузка фоток и их путей
@app.route('/api/users/user_images', methods=['POST'])
@jwt_required()
def post_user_images():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        user_id = request.form.get('user_id')
        user_id = user_id.strip('"')
        photo_names = request.form.getlist('names')
        photo_names = [name.strip('"') for name in photo_names]
        photo_names_tuple = tuple(photo_names)
        check_existing = ''
        if photo_names_tuple:
            if len(photo_names_tuple) == 1:
                check_existing = f"AND photo_name != '{photo_names_tuple[0]}'"
            else:
                check_existing = f"AND photo_name NOT IN {photo_names_tuple}"
        relative_folder_path = os.path.join(os.path.dirname(__file__), f"user_photos/{user_id}")
        all_files = glob.glob(f"{relative_folder_path}/*")
        for f in all_files:
            file_name = os.path.basename(f)
    
            if file_name not in photo_names:
                os.remove(f)
        cur.execute(f'DELETE FROM User_photo \
                 WHERE user_id = %s {check_existing}',
                (user_id,))
        conn.commit()
        files = request.files.getlist('file')  # Получаем список всех файлов
        if not files:
            return jsonify({"message": "Нет фото для загрузки"}), 204
        cur.execute('SELECT photo_id FROM User_photo WHERE user_id = %s ORDER BY photo_id DESC LIMIT 1;', \
                    (user_id,))
        photo_last_id = cur.fetchone()
        if photo_last_id:
            count_photo = photo_last_id['photo_id']+1
        else:
            count_photo = 1
        file_name = ''
        if 'file' not in request.files:
            return "No file part", 400
        saved_files = []
        for file in files:
            if file.filename == '':
                continue  # Пропускаем пустые файлы
            file_name = str(count_photo) + file.filename
            cur.execute('INSERT INTO User_photo (user_id, photo_id, photo_directory_path, photo_name) \
                 VALUES (%s, %s, %s, %s);',
                (user_id, count_photo, relative_folder_path, file_name))
            conn.commit()
            os.makedirs(relative_folder_path, exist_ok=True) #убрать потом
            file.save(f"{relative_folder_path}/{file_name}")
            count_photo += 1
        return jsonify({"message": "Фотографии успешно загружены"}), 201
    except Exception as e:
        logging.error(f"Ошибка при загрузке фотографий: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

#Получение путей фоток
@app.route('/api/users/user_images/<user_id>', methods=['GET'])
@jwt_required()
def get_user_images_route(user_id):
    try:
        return jsonify(get_user_images(user_id)), 200
    except Exception as e: 
        return jsonify({"error": str(e)}), 500
    
@app.route('/images/<user_id>/<image_name>', methods=['GET'])
@jwt_required()
def get_image(user_id, image_name):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory = psycopg2.extras.RealDictCursor)
        cur.execute('SELECT photo_directory_path FROM User_photo WHERE user_id = %s and photo_name = %s;', (user_id, image_name))
        images_folder = cur.fetchone()['photo_directory_path']
        return send_from_directory(images_folder, image_name)
    except Exception as e: 
        logging.error(f"Ошибка при получении фотографии: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    app.config['JSON_AS_ASCII'] = False
    app.config['JWT_SECRET_KEY'] = 'dozen'
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)  
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = timedelta(days=30) 
    jwt = JWTManager(app)
    app.run(host='0.0.0.0', port=5002, debug=True)
    #Добавить UUID для фото доплнительно
