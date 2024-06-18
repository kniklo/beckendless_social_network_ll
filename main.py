import json
from io import BytesIO
from flask import Flask, render_template, request, redirect, session, send_file, jsonify
import requests
import re
import urllib
import datetime



app = Flask(__name__)
app.secret_key = '12345678'

BACKENDLESS_APP_ID = 'A9937553-25E7-88A3-FF82-498004E4E300'
BACKENDLESS_API_KEY = 'DFA6D651-CF7D-48C9-A0E2-90CCA17AC6CF'

BACKENDLESS_BASE_URL = 'soaringelbow.backendless.app'

USERS_URL = f'https://{BACKENDLESS_BASE_URL}/api/users/'
DATA_URL = f'https://{BACKENDLESS_BASE_URL}/api/data/'
REGISTER_URL = f'{USERS_URL}register'
LOGIN_URL = f'{USERS_URL}login'
LOGOUT_URL = f'{USERS_URL}logout'
CREATE_CONFIRMATION_URL = f'https://{BACKENDLESS_BASE_URL}/api/users/createEmailConfirmationURL/'
FOLDER_URL = f'https://{BACKENDLESS_BASE_URL}/api/files/users/'
WEB_FOLDER = f'https://{BACKENDLESS_BASE_URL}/api/files/web/'
SHARED_FOLDER = 'shared_with_me'

user_token = None

@app.route('/')
def index():
    user_token = session.get('user-token', None)
    if user_token:
        return redirect('/personal')
    else:
        return render_template('index.html')

def validate_email(email):
    # Простейшая валидация email с помощью регулярного выражения
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email)

def validate_age(age):
    # Проверка возраста, чтобы он был больше или равен 5
    return int(age) >= 5

def create_user_directories(nickname):
    user_dir_url = f'{FOLDER_URL}{nickname}/{SHARED_FOLDER}'
    response = requests.post(user_dir_url)
    if response.status_code == 200:
        return True
    else:
        return False

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        nickname = request.form['nickname']
        age = request.form['age']
        gender = request.form['gender']
        country = request.form['country']

        # Валидация почты
        if not validate_email(email):
            return 'Invalid email format.'

        # Проверка возраста
        if not validate_age(age):
            return 'Age must be 5 or older.'

        # Проверка уникальности никнейма
        response = requests.get(f'{REGISTER_URL}?where=nickname%3D%27{nickname}%27')
        if response.status_code == 200 and len(response.json()['data']) > 0:
            return 'Nickname is already taken. Please choose a different one.'

        data = {
            "email": email,
            "nickname": nickname,
            "password": password,
            "age": age,
            "gender": gender,
            "country": country
        }

        response = requests.post(REGISTER_URL, json=data)
        if response.status_code == 200:
            create_user_directories(nickname)  # создание каталога с именем пользователя а также подкаталога
            return 'Registration successful!'
        else:
            return 'Error registering user.'
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nickname = request.form['nickname']
        password = request.form['password']
        data = {"login": nickname, "password": password}
        headers = {'Content-Type': 'application/json'}
        response = requests.post(LOGIN_URL, headers=headers, json=data)
        if response.status_code == 200:
            resp_json = json.loads(response.text)
            session['nickname'] = nickname  # Устанавливаем никнейм в сессии
            session['user-token'] = resp_json['user-token']
            session['objectId'] = resp_json['objectId']
            session['full_current_dir'] = f'{FOLDER_URL}{nickname}/{SHARED_FOLDER}'
            return redirect('/')
        else:
            return response.text
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        nickname = request.form['nickname']

        RESTORE_PASSWORD_URL = f'https://{BACKENDLESS_BASE_URL}/api/users/restorepassword/{nickname}'

        response = requests.get(RESTORE_PASSWORD_URL)
        if response.status_code == 200:
            return 'Instructions for password reset have been sent to your email.'
        else:
            error_message = json.loads(response.text)['message']
            return f'Error: {error_message}'

    return render_template('forgot_password.html')

@app.route('/logout', methods=['POST'])
def logout():
    headers = {'user-token': session['user-token']}
    response = requests.get(LOGOUT_URL, headers=headers)
    if response.status_code == 200:
        session['user-token'] = None
        return redirect('/')
    else:
        return 'Failed to logout.'

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'nickname' in session:
        file = request.files['file']
        current_dir = session['full_current_dir']
        last_folder = current_dir.split("/")[-1]
        if last_folder == SHARED_FOLDER:
            return 'You can not upload files to shared folder.'
        else:
            upload_url = f'{current_dir}/{file.filename}?overwrite=true'
            headers = {
                'user-token': session['user-token']
                    }
            files = {'upload': file}
            response = requests.post(upload_url, headers=headers, files=files)
            return redirect('/')
    else:
        return redirect('/login')

@app.route('/personal')
def personal():

    def request_folders():
        url = session['full_current_dir']
        headers = {'user-token': session['user-token']}
        params = {}
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            resp_json = json.loads(response.text)
            _folders = [el['name'] for el in resp_json]
        else:
            _folders = []
        return _folders

    if 'nickname' in session:
        folders = request_folders()
        nickname = session['nickname']
        label_folder = str(session['full_current_dir']).replace(f'{FOLDER_URL}{nickname}', '')
        objectId = session.get('objectId', None)
        avatar = None
        if objectId:
            response = requests.get(f'{USERS_URL}{objectId}?props=avatar')
            if response.status_code == 200:
                json_resp = json.loads(response.text)
                avatar = json_resp.get('avatar')
        return render_template('personal.html', label_folder=label_folder, folders=folders, nickname=nickname, avatar=avatar)
    else:
        return redirect('/login')


@app.route('/create_folder/<folder_name>', methods=['GET'])
def create_folder(folder_name):
    if 'nickname' in session:
        full_current_dir = session['full_current_dir']
        user_dir_url = f'{full_current_dir}/{folder_name}'
        response = requests.post(user_dir_url)
        if response.status_code == 200:
            return redirect('/')
        elif response.status_code == 400:
            return json.loads(response.text)['message']
        else:
            return 'Failed to create folder.'
    else:
        return redirect('/login')

@app.route('/delete_folder/<folder_name>', methods=['GET'])
def delete_folder(folder_name):
    full_current_dir = session['full_current_dir']
    user_dir_url = f'{full_current_dir}/{folder_name}'
    response = requests.delete(user_dir_url)
    return redirect('/')

@app.route('/change_folder/<folder_name>', methods=['GET'])
def change_folder(folder_name):
    if 'nickname' in session:
        full_current_dir = session['full_current_dir']
        if folder_name == '...':
            new_current_dir = full_current_dir.replace('/' + full_current_dir.split("/")[-1], '')
        else:
            # проверка файл или папка
            response = requests.get(f'{full_current_dir}/{folder_name}?action=count')
            # если папка - заходим в нее
            if response.status_code == 200:
                new_current_dir = f'{full_current_dir}/{folder_name}'
            # если файл
            else:
                new_current_dir = full_current_dir
                response = requests.get(f'{full_current_dir}/{folder_name}')
                if response.status_code == 200:
                    # если файл в папке shared - достаем ссылку из него
                    current_dir = session['full_current_dir']
                    last_folder = current_dir.split("/")[-1]
                    if last_folder == SHARED_FOLDER:
                        return response.text
                    else:
                        return send_file(BytesIO(response.content), download_name=folder_name, as_attachment=True)
        #   Проверка на выход вверх из своей папки в users - этого делать нельзя
        if new_current_dir.split('/')[-1] != 'users':
            session['full_current_dir'] = new_current_dir
        return redirect('/')
    else:
        return redirect('/login')

@app.route('/count_files/<folder_name>', methods=['GET'])
def count_files(folder_name):
    if 'nickname' in session:
        full_current_dir = session['full_current_dir']
        response = requests.get(f'{full_current_dir}/{folder_name}?action=count')
        return redirect('/')
    else:
        return redirect('/login')

@app.route('/delete_file', methods=['POST'])
def delete_file():
    if 'nickname' in session:
        nickname = session['nickname']
        file_name = request.form['file_name']  # Получаем имя папки для удаления
        file_url = f'{FOLDER_URL}{nickname}/{file_name}'  # Формируем URL для удаления

        headers = {
            'user-token': session['user-token']  # Передаем user-token для авторизации
        }

        response = requests.delete(file_url, headers=headers)  # Отправляем DELETE запрос на удаление
        return redirect('/')
    else:
        return redirect('/login')

@app.route('/share', methods=['GET'])
def share():
    nickname = request.args.get('param1')
    filename = request.args.get('param2')
    url = f'https://{BACKENDLESS_BASE_URL}/api/data/Users?where=nickname%20%3D%20%27{nickname}%27'
    response = requests.get(url)
    if response.status_code == 200:
        user = json.loads(response.text)
        if len(user) == 0:
            return 'Нет такого пользователя'
        else:
            upload_url = f'{FOLDER_URL}{nickname}/{SHARED_FOLDER}/{filename}?overwrite=true'
            s = session['full_current_dir']
            file = json.dumps(f'{s}/{filename}')
            headers = {}
            files = {'upload': file}
            response = requests.post(upload_url, headers=headers, files=files)
    if 'nickname' in session:
        return redirect('/')
    else:
        return redirect('/login')

@app.route('/upload_avatar', methods=['POST'])
def upload_avatar():
    if 'avatar' not in request.files:
        return jsonify({'error': 'No file part'}), 400

    avatar = request.files['avatar']
    if avatar.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    ext = avatar.filename.split('.')[-1]
    nickname = session['nickname']
    upload_url = f'{WEB_FOLDER}{nickname}_avatar.{ext}?overwrite=true'

    headers = {
        'user-token': session['user-token']
    }
    files = {'upload': avatar}
    response = requests.post(upload_url, headers=headers, files=files)
    if response.status_code == 200:
        objectId = session.get('objectId', None)
        user_token = session['user-token']
        if objectId:
            args = {'avatar': f'{WEB_FOLDER}{nickname}_avatar.{ext}'}
            headers = {'user-token': user_token}
            response = requests.put(f'{USERS_URL}{objectId}', headers=headers, json=args)
    return redirect('/')

@app.route('/to_change_profile_info', methods=['GET', 'POST'])
def to_change_profile_info():
    if 'nickname' in session:
        nickname = session['nickname']
        objectId = session.get('objectId', None)
        if objectId:
            response = requests.get(f'{USERS_URL}{objectId}?props=email,age,gender,country')
            if response.status_code == 200:
                json_resp = json.loads(response.text)
                email = json_resp['email']
                age = json_resp['age']
                gender = json_resp['gender']
                country = json_resp['country']
                return render_template('change_personal_info.html', nickname=nickname, email=email, age=age, gender=gender, country=country)
            else:
                return redirect('/')
        else:
            return redirect('/')

@app.route('/change_profile_info', methods=['POST'])
def change_profile_info():
    objectId = session.get('objectId', None)
    user_token = session['user-token']
    if objectId:
        args = request.form.to_dict()
        headers = {'user-token': user_token}
        response = requests.put(f'{USERS_URL}{objectId}', headers=headers, json=args)
    return redirect('/to_change_profile_info')

@app.route('/geolocation', methods=['POST'])
def geolocation():
    data = request.json
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    point = {
        "type": "Point",
        "coordinates": [longitude, latitude]}
    objectId = session.get('objectId', None)
    if objectId:
        headers = {'user-token': user_token}
        args = {'myLocation': json.dumps(point)}
        print(args)
        response = requests.put(f'{USERS_URL}{objectId}', headers=headers, json=args)
    return redirect('/')

@app.route('/to_places', methods=['GET'])
def to_places():
    url = f'{DATA_URL}Place'
    headers = {
        'user-token': session['user-token']
    }
    response = requests.get(url, headers=headers)
    places = json.loads(response.text)
    sorted_places = sorted(places, key=lambda x: x['created'], reverse=True)
    return render_template('places.html', places=sorted_places)

@app.route('/add_place', methods=['POST'])
def add_place():
    description = request.form['description']
    categories = request.form['categories']
    lat = float(request.form['lat'])
    lng = float(request.form['lng'])
    point = json.dumps({
        "type": "Point",
        "coordinates": [lng, lat]})
    image = request.files['image']
    # загружаем файл в хранилище и получаем URL
    nickname = session['nickname']
    upload_url = f'{WEB_FOLDER}{nickname}_{image.filename}?overwrite=true'
    headers = {
        'user-token': session['user-token']
    }
    files = {'upload': image}
    response = requests.post(upload_url, headers=headers, files=files)
    fileurl = json.loads(response.text)['fileURL']

    url = f'{DATA_URL}Place/upsert'
    data = {'description': description,
            'hashtag': categories,
            'image': fileurl,
            'likes': 0,
            'point': point,
            'ownerId': nickname
            }
    response = requests.put(url, json=data)
    return redirect('/to_places')

@app.route('/delete_place', methods=['POST'])
def delete_place():
    place_objectId = request.form.get('place_objectId')
    url = f'{DATA_URL}Place/{place_objectId}'
    headers = {
        'user-token': session['user-token']
    }
    response = requests.delete(url, headers=headers)
    return redirect('/to_places')
    
@app.route('/search_places', methods=['GET'])
def search_places():
    if 'nickname' in session:
        name = request.args.get('name', '')
        category = request.args.get('category', '')
        radius = request.args.get('radius', '')
        coordinates = request.args.get('coordinates', '')

        query = f"owner != '{session['nickname']}'"  # Исключаем свои места

        if name:
            query += f" AND description LIKE '%{name}%'"
        if category:
            query += f" AND category = '{category}'"
        if radius and coordinates:
            lat, lon = map(float, coordinates.split(','))
            query += f" AND distanceOnSphere(coordinates, 'POINT({lon} {lat})') <= {radius}"

        response = requests.get(f'https://{BACKENDLESS_BASE_URL}/api/data/places?where={urllib.parse.quote(query)}')
        if response.status_code == 200:
            places = response.json()
            return jsonify(places)
        else:
            return jsonify({'status': 'error', 'message': response.text}), response.status_code
    else:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401
@app.route('/save_place/<place_id>', methods=['POST'])
def save_place(place_id):
    if 'nickname' in session:
        data = request.json
        description = data.get('description')
        coordinates = data.get('coordinates')
        hashtags = data.get('hashtags')
        image = data.get('image', '')
        category = data.get('category')

        place = {
            "description": description,
            "coordinates": coordinates,
            "hashtags": hashtags,
            "image": image,
            "category": category
        }

        response = requests.put(f'https://{BACKENDLESS_BASE_URL}/api/data/places/{place_id}', json=place)
        if response.status_code == 200:
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'error', 'message': response.text}), response.status_code
    else:
        return jsonify({'status': 'error', 'message': 'Unauthorized'}), 401


if __name__ == '__main__':
    app.run(debug=True)

