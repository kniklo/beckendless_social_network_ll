import json
from io import BytesIO
from flask import Flask, render_template, request, redirect, session, send_file
import requests
import re


app = Flask(__name__)
app.secret_key = '12345678'

BACKENDLESS_APP_ID = 'A9937553-25E7-88A3-FF82-498004E4E300'
BACKENDLESS_API_KEY = 'DFA6D651-CF7D-48C9-A0E2-90CCA17AC6CF'
# BACKENDLESS_APP_ID = '65ACC275-3321-003B-FF37-6806F0DFEB00'
# BACKENDLESS_API_KEY = 'C5B5D642-958B-49EF-B5C0-812B8C210A23'

BACKENDLESS_BASE_URL = 'soaringelbow.backendless.app'
# BACKENDLESS_BASE_URL = 'winsomerobin.backendless.app'

REGISTER_URL = f'https://{BACKENDLESS_BASE_URL}/api/users/register'
LOGIN_URL = f'https://{BACKENDLESS_BASE_URL}/api/users/login'
CREATE_CONFIRMATION_URL = f'https://{BACKENDLESS_BASE_URL}/api/users/createEmailConfirmationURL/'
FOLDER_URL = f'https://{BACKENDLESS_BASE_URL}/api/files/users/'
LOGOUT_URL = f'https://{BACKENDLESS_BASE_URL}/api/users/logout'

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
    user_dir_url = f'{FOLDER_URL}{nickname}/shared_with_me'
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
            session['nickname'] = nickname  # Устанавливаем никнейм в сессии
            session['user-token'] = json.loads(response.text)['user-token']
            session['full_current_dir'] = f'{FOLDER_URL}{nickname}/shared_with_me'
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
        print(response.status_code, response.text)
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
        print(request.files)
        print(request.form)
        if 'file' not in request.files:
            print('No file part')
        else:
            file = request.files['file']
            current_dir = session['full_current_dir']
            upload_url = f'{current_dir}/{file.filename}?overwrite=true'

            headers = {
                # 'Content-Type': 'multipart/form-data',
                'user-token': session['user-token']
                    }
        #
            files = {'upload': file}
            # files = {'upload': (file.filename, file.stream, file.mimetype)}
            # files = {'file': (file.filename, file.read())}
        #
            response = requests.post(upload_url, headers=headers, files=files)
            print(response.status_code, response.text)
    #
    #     if response.status_code == 200:
    #         return 'File uploaded successfully!'
    #     else:
    #         return f'Failed to upload file: {response.text}'
    # else:
    return redirect('/')

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
        # label_folder = ''
        return render_template('personal.html', label_folder=label_folder, folders=folders, nickname=nickname)
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
            # если файл - скачиваем
            else:
                new_current_dir = full_current_dir
                # сохранение файла чет не работает
                response = requests.get(f'{full_current_dir}/{folder_name}')
                if response.status_code == 200:
                    return send_file(BytesIO(response.content), download_name=folder_name, as_attachment=True)

        session['full_current_dir'] = new_current_dir
        return redirect('/')
    else:
        return redirect('/login')

@app.route('/count_files/<folder_name>', methods=['GET'])
def count_files(folder_name):
    if 'nickname' in session:
        full_current_dir = session['full_current_dir']
        response = requests.get(f'{full_current_dir}/{folder_name}?action=count')
        print(response.status_code, response.text)
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

if __name__ == '__main__':
    app.run(debug=True)

