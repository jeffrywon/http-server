import multiprocessing

multiprocessing.set_start_method('spawn', force=True)

import os
import zipfile
import traceback
from datetime import datetime, timedelta
import pyperclip
import socket
import threading
import subprocess
import urllib.parse
import traceback
import chardet
import time
from flask import Flask, render_template, send_file, abort, request, jsonify, session, redirect, url_for

app = Flask(__name__)
app.secret_key = 'junmuncheng'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=10)
DIRECTORY = r"C:\Users\acer\Desktop\server\file share"
ERROR_LOG_FILE = "error_log.txt"
server_process = None  # 全局变量用于保存服务器进程
userpage= 'index.html'
loginpage= 'login.html'

@app.after_request
def add_no_cache_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Expires'] = '0'
    response.headers['Pragma'] = 'no-cache'
    return response

def get_folder_size(folder_path):
    total_size = 0
    for path, dirs, files in os.walk(folder_path):
        for f in files:
            fp = os.path.join(path, f)
            total_size += os.path.getsize(fp)
    return total_size

@app.route('/server_control', methods=['GET'])
def server_control():
    return render_template('server_control.html')

def restart_server():
    try:
        global server_process
        global server_paused

        server_paused = False
        if server_process is not None:
            server_process.terminate()  # 终止当前服务器进程

        # 启动新的服务器进程
        server_process = multiprocessing.Process(target=start_server)
        server_process.start()

        reset_session_timeout()

    except subprocess.CalledProcessError as e:
        error_message = "重启服务器时出错: {}".format(e)
        log_error(error_message)
        abort(500)


def shutdown_server():
    os.kill(os.getpid(), 9)

@app.route('/end_server', methods=['POST'])
def end_server():
    try:
        shutdown_server()

    except Exception as e:
        error_message = "An error occurred while stopping the server: {}".format(str(e))
        log_error(error_message)
        abort(500)


def start_server():
    ip_address = get_ip_address()
    server_address = 'http://' + ip_address + ':8040'
    threading.Thread(target=copy_to_clipboard, args=(server_address,)).start()

    # 重置会话超时时间为零
    reset_session_timeout()

    # 启动服务器
    app.run(host=ip_address, port=8040, debug=False)


# 在 '/execute_command' 路由中添加重启服务器操作的处理
@app.route('/execute_command', methods=['POST'])
def execute_command():
    try:
        command = request.json.get('command')
        if command == 'restart':
            restart_server()
            message = "Server restarted successfully"
        elif command == 'end':
            shutdown_server()
        elif command == 'pause':
            pause_server()
            message = "Server paused successfully"
        elif command == 'resume':
            resume_server()
            message = "Server resumed successfully"
        elif command == 'reset directory':
            reset_directory()
            message = "Directory reset successfully"
        else:
            message = "Unknown command"

        return jsonify({'message': message})

    except Exception as e:
        error_message = "An error occurred while executing command: {}".format(str(e))
        log_error(error_message)
        abort(500)


def format_size(size):
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return '{:.2f} {}'.format(size, units[i])

def log_error(error_message):
    now = datetime.now()
    formatted_date = now.strftime("%Y-%m-%d %H:%M:%S")
    error_message_with_timestamp = "[{}] {}".format(formatted_date, error_message)

    try:
        with open(ERROR_LOG_FILE, "a") as error_log:
            error_log.write(error_message_with_timestamp + "\n")
            error_log.write("-" * 80 + "\n")
    except FileNotFoundError:
        with open(ERROR_LOG_FILE, "w") as error_log:
            error_log.write(error_message_with_timestamp + "\n")
            error_log.write("-" * 80 + "\n")

def copy_to_clipboard(text):
    try:
        pyperclip.copy(text)
        print('Server address copied to clipboard:', text)
    except Exception as e:
        print('Error copying server address to clipboard:', str(e))

server_paused = False

@app.route('/pause_server', methods=['POST'])
def pause_server():
    try:
        global server_paused

        server_paused = True
        return jsonify({'message': 'Server paused successfully'})

    except Exception as e:
        error_message = "An error occurred while pausing server: {}".format(str(e))
        error_message += "\nRequest: POST /pause_server"
        error_message += "\n\n" + traceback.format_exc()
        log_error(error_message)
        abort(500)

@app.route('/resume_server', methods=['POST'])
def resume_server():
    try:
        global server_paused

        server_paused = False

        return jsonify({'message': 'Server resumed successfully'})

    except Exception as e:
        error_message = "An error occurred while resuming server: {}".format(str(e))
        error_message += "\nRequest: POST /resume_server"
        error_message += "\n\n" + traceback.format_exc()
        log_error(error_message)
        abort(500)



@app.route('/', methods=['GET', 'POST'])
def file_list():
    try:
        if server_paused:
            return render_template('serverpaused.html')
        
        if 'authenticated' not in session or not session['authenticated']:
            if request.method == 'POST':
                password = request.form['password']
                if password == '1111':
                    session['authenticated'] = True
                    session_timeout_str = request.form.get('session_timeout', '10')
                    session_timeout = int(session_timeout_str) if session_timeout_str.isdigit() else 10
                    print('Session timeout:', (session_timeout))
                    app.permanent_session_lifetime = timedelta(minutes=session_timeout)
                    return redirect(url_for('file_list'))
                else:
                    if password == '2111':
                        return redirect(url_for('server_control'))
                    else:
                        return render_template((loginpage), error_message='Incorrect password.')
                
            return render_template(loginpage)

        folder_path = os.path.abspath(DIRECTORY)
        entries = os.listdir(folder_path)
        files = []

        for entry in entries:
            entry_path = os.path.join(folder_path, entry)
            if os.path.isdir(entry_path):
                item_type = get_file_type(entry_path)  # 调用 get_item_type 函数获取类型
                folder_size = get_folder_size(entry_path)
                folder_size_formatted = format_size(folder_size)
                files.append({
                    'name': entry,
                    'size': folder_size_formatted,
                    'type': item_type
                })
            elif os.path.isfile(entry_path) and entry != 'selected_files.zip':
                file_size = os.path.getsize(entry_path)
                file_size_formatted = format_size(file_size)
                files.append({
                    'name': entry,
                    'size': file_size_formatted,
                    'type': 'file'
                })

        return render_template((userpage), files=files)
    
    except Exception as e:
        error_message = "An error occurred while retrieving file list: {}".format(str(e))
        error_message += "\nRequest: GET /"
        error_message += "\n\n" + traceback.format_exc()
        log_error(error_message)
        abort(500)

# Route for determining file or folder type
@app.route('/get_item_type/<path:path>', methods=['GET'])
def get_file_type(file_name):
    if os.path.isdir(file_name):
        return 'folder'
    else:
        return 'file'
    
@app.route('/delete_file', methods=['POST'])
def delete_file():
    try:
        file_path = request.json.get('file_path')
        if file_path is not None:
            abs_file_path = os.path.join(DIRECTORY, file_path)
            if os.path.exists(abs_file_path):
                os.remove(abs_file_path)
                return jsonify({'message': 'File deleted successfully'})
            else:
                return jsonify({'message': 'File not found'})
        else:
            return jsonify({'message': 'File path not provided'})

    except Exception as e:
        error_message = "An error occurred while deleting file: {}".format(str(e))
        log_error(error_message)
        abort(500)

    
@app.route('/download/<path:file_path>')
def download_file(file_path):
    try:
        folder_path = os.path.abspath(DIRECTORY)
        abs_file_path = os.path.join(folder_path, file_path)

        if os.path.isfile(abs_file_path):
            return send_file(abs_file_path, as_attachment=True)
        else:
            abort(404)

    except Exception as e:
        error_message = "An error occurred while downloading file: {}".format(str(e))
        error_message += "\nRequest: GET /download/{}".format(file_path)
        error_message += "\n\n" + traceback.format_exc()
        log_error(error_message)
        abort(500)

@app.route('/download_selected', methods=['POST'])
def download_selected():
    try:
        selected_files = request.get_json()
        folder_path = os.path.abspath(DIRECTORY)

        zip_file_path = os.path.join(folder_path, 'selected_files.zip')
        if os.path.exists(zip_file_path):
            os.remove(zip_file_path)

        with zipfile.ZipFile(zip_file_path, 'w') as zip_file:
            for file in selected_files:
                abs_file_path = os.path.join(folder_path, file)
                zip_file.write(abs_file_path, file)

        # Check if zip file was created successfully
        if os.path.exists(zip_file_path):
            download_link = urllib.parse.urljoin(request.url_root, 'download/selected_files.zip')
            js_code = f"{download_link}"

            return f"{js_code}"
        else:
            # Zip file creation failed
            return "Failed to create the zip file.", 500

    except Exception as e:
        error_message = "An error occurred while downloading selected files: {}".format(str(e))
        error_message += "\nRequest: POST /download_selected"
        error_message += "\n\n" + traceback.format_exc()
        log_error(error_message)
        abort(500)



@app.route('/upload', methods=['POST'])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({'message': 'No file selected'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'message': 'No file selected'})

        save_path = os.path.join(DIRECTORY, file.filename)
        file.save(save_path)

        return jsonify({'message': 'File uploaded successfully'})

    except Exception as e:
        error_message = "An error occurred while uploading file: {}".format(str(e))
        error_message += "\nRequest: POST /upload"
        error_message += "\n\n" + traceback.format_exc()
        log_error(error_message)
        abort(500)

import shutil


@app.route('/get_directory1', methods=['GET'])
def get_directory1():
    return jsonify({'directory': os.getcwd()})

@app.route('/get_file_path', methods=['POST'])
def get_file_path():
  try:
    file_name = request.json.get('file_name')
    file_path = os.path.join(DIRECTORY, file_name)
    session['file_path'] = file_path  # 将文件路径存储在会话中
    return jsonify({'message': 'File path retrieved successfully', 'file_path': file_path})
  except Exception as e:
    error_message = "An error occurred while getting file path: {}".format(str(e))
    log_error(error_message)
    abort(500)

@app.route('/move_file', methods=['POST'])
def move_file():
  try:
    current_directory = DIRECTORY
    file_path = session.get('file_path')  # 从会话中获取文件路径

    if file_path is not None:
      abs_file_path = file_path
      abs_destination = os.path.join(current_directory, os.path.basename(file_path))

      if os.path.exists(abs_file_path):
        if not os.path.exists(abs_destination):
          shutil.move(abs_file_path, abs_destination)
          session.pop('file_path')  # 移除会话中的文件路径
          return jsonify({'message': 'File moved successfully'})
        else:
          return jsonify({'message': 'A file with the same name already exists in the destination'})
      else:
        return jsonify({'message': 'File not found'})
    else:
      return jsonify({'message': 'File path not provided'})
  except Exception as e:
    error_message = "An error occurred while moving file: {}".format(str(e))
    log_error(error_message)
    abort(500)






@app.route('/preview/<path:file_path>')
def preview_file(file_path):
    try:
        folder_path = os.path.abspath(DIRECTORY)
        abs_file_path = os.path.join(folder_path, file_path)

        if os.path.isfile(abs_file_path):
            file_extension = os.path.splitext(file_path)[1].lower()
            if file_extension in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                return send_file(abs_file_path, mimetype='image/jpeg')
            elif file_extension in ['.mp4', '.avi', '.mov', '.wmv']:
                return send_file(abs_file_path, mimetype='video/mp4')
            elif file_extension == '.pdf':
                return send_file(abs_file_path, mimetype='application/pdf')
            elif file_extension == '.txt':
                return send_file(abs_file_path, mimetype='text/plain')
            elif file_extension == '.html':
                with open(abs_file_path, 'rb') as html_file:
                    raw_data = html_file.read()
                    encoding_result = chardet.detect(raw_data)
                    encoding = encoding_result['encoding']
                    html_content = raw_data.decode(encoding)
                    return html_content

        abort(404)

    except Exception as e:
        error_message = "An error occurred while previewing file: {}".format(str(e))
        error_message += "\nRequest: GET /preview/{}".format(file_path)
        error_message += "\n\n" + traceback.format_exc()
        log_error(error_message)
        abort(500)




def get_ip_address():
    hostname = socket.gethostname()
    ip_address = socket.gethostbyname(hostname)
    return ip_address
    

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('file_list'))

@app.route('/lock_session', methods=['POST'])
def lock_session():
    try:
        session.modified = True
        session['authenticated'] = False
        global DIRECTORY
        DIRECTORY = r"C:\Users\acer\Desktop\server\file share"
        return jsonify({'message': 'Session locked successfully'})

    except Exception as e:
        error_message = "An error occurred while locking the session: {}".format(str(e))
        error_message += "\nRequest: POST /lock_session"
        error_message += "\n\n" + traceback.format_exc()
        log_error(error_message)
        abort(500)

def reset_session_timeout():
    app.permanent_session_lifetime = timedelta(minutes=-1)

def reset_directory():
    global DIRECTORY
    DIRECTORY = r"C:\Users\acer\Desktop\server\file share"


@app.route('/change_directory', methods=['POST'])
def change_directory():
    try:
        directory = request.json.get('directory')
        if directory is not None:
            if os.path.isdir(directory):
                global DIRECTORY
                DIRECTORY = directory
                print('Directory changed to:',directory)
                return jsonify({'message': 'Directory changed successfully'})
            else:
                return jsonify({'message': 'Invalid directory'})
        else:
            return jsonify({'message': 'Directory not provided'})

    except Exception as e:
        error_message = "An error occurred while changing directory: {}".format(str(e))
        log_error(error_message)
        abort(500)


@app.route('/get_directory', methods=['GET'])
def get_directory():
    return jsonify({'directory': DIRECTORY})


@app.route('/password', methods=['POST'])
def validate_password():
    password = request.json.get('password')

    if password == '2111':
        return jsonify({'valid': True, 'redirect_url': '/server_control'})
    else:
        return jsonify({'valid': False})
    
@app.route('/rename_file', methods=['POST'])
def rename_file():
    try:
        file_path = request.json.get('file_path')
        new_name = request.json.get('new_name')

        if file_path is not None and new_name is not None:
            decoded_file_path = urllib.parse.unquote(file_path)
            abs_file_path = os.path.join(DIRECTORY, decoded_file_path)
            new_file_path = os.path.join(DIRECTORY, new_name)

            if os.path.exists(abs_file_path):
                os.rename(abs_file_path, new_file_path)
                return jsonify({'message': 'File renamed successfully'})
            else:
                return jsonify({'message': 'File not found'})
        else:
            return jsonify({'message': 'File path or new name not provided'})

    except Exception as e:
        error_message = "An error occurred while renaming file: {}".format(str(e))
        log_error(error_message)
        abort(500)


if __name__ == '__main__':
    start_server()