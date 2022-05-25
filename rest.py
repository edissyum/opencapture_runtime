# This file is part of Open-Capture Runtime

# Open-Capture for Invoices is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Open-Capture is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Open-Capture for Invoices. If not, see <https://www.gnu.org/licenses/gpl-3.0.html>.

# @dev : Nathan Cheval <nathan.cheval@outlook.fr>

import os
import base64
import binascii
from PIL import Image
from src.classes.Log import Log
from flask import Flask, request, current_app
from src.classes.PyTesseract import PyTesseract
from src.auth import token_required, generate_token
from src.functions import is_dev, generate_tmp_filename

app = Flask(__name__)

# La clé corresponds à ce qui doit être envoyé lors de l'appel au WS '/oc/getDocumentInformations' dans la variable "module"
# La partie 'filename' contient le nom du fichier principal du module, qui doit se trouver dans le dossier src/modules/{{clé}}/
# La partie method contient le nom de la fonction qui sera appelé dans le WS get_document_informations pour appliquer le traitement spécifique
app.config['MODULES'] = {
    "ordonnances": {
        "filename": "main.py",
        "method": "run"
    }
}


@app.route('/auth/getToken', methods=['GET'])
@is_dev
def get_token():
    log = Log('/var/www/html/opencapture_runtime/auth.log', None)
    if 'Authorization' in request.headers:
        basic_auth = request.authorization
        if basic_auth:
            if os.path.isfile('/var/www/html/opencapture_runtime/.rest_auth'):
                user_exists = False
                with open('/var/www/html/opencapture_runtime/.rest_auth') as auth:
                    line = auth.read().split('\n')
                    for user in line:
                        user = user.split(':')
                        if len(user) == 2:
                            username = user[0]
                            password = user[1]
                            if username == basic_auth['username'] and password == basic_auth['password']:
                                user_exists = True
                if not user_exists:
                    log.error('Authentification error. IP Address : ' + request.remote_addr)
                    return {
                        'auth_token': "",
                        'days_before_exp': 0,
                        'errors': 'Authentification error'
                    }, 401
            else:
                log.error('Authorization file missing. IP Address : ' + request.remote_addr)
                return {
                    'auth_token': "",
                    'days_before_exp': 0,
                    'errors': 'Authorization file missing'
                }, 404
        else:
            log.error('Authorization headers error. IP Address : ' + request.remote_addr)
            return {
                'auth_token': "",
                'days_before_exp': 0,
                'errors': 'Authorization headers error'
            }, 500
    else:
        log.error('Authorization headers missing. IP Address : ' + request.remote_addr)
        return {
            'auth_token': "",
            'days_before_exp': 0,
            'errors': 'Authorization headers missing'
        }, 400
    days_before_exp = 1
    token = generate_token(days_before_exp)
    return {
        'auth_token': str(token),
        'days_before_exp': days_before_exp,
    }

@app.route('/oc/getRawDocument', methods=['POST'])
@is_dev
@token_required
def get_raw_document():
    args = request.get_json()
    if 'fileContent' not in args or not args['fileContent'] or 'lang' not in args or not args['lang']:
        return {'error': "Il manque une ou plusieurs donnée(s) obligatoire(s)"}, 400
    ocr = PyTesseract(args['lang'], None, './')
    path = current_app.config['PATH']
    file = path + '/' + generate_tmp_filename()

    try:
        with open(file, "wb") as _file:
            size = _file.write(base64.b64decode(args['fileContent'] * (-len(args['fileContent']) % 4)))
        if size == 0:
            with open(file, "wb") as _file:
                _file.write(base64.b64decode(args['fileContent']))
    except binascii.Error:
        with open(file, "wb") as _file:
            _file.write(base64.b64decode(args['fileContent']))
    image_content = Image.open(file)
    text_content = ocr.text_builder(image_content)
    os.remove(file)
    return {"data": text_content}

@app.route('/oc/getDocumentInformations', methods=['POST'])
@is_dev
@token_required
def get_document_informations():
    args = request.get_json()
    if 'data' in args and 'module' in args:
        if args['module'] in app.config['MODULES']:
            _module = app.config['MODULES']
            _filename = _module.get(args['module']).get('filename').replace('.py', '')
            _method = _module.get(args['module']).get('method')
            run_module = getattr(__import__('src.modules.' + args['module'] + '.' + _filename, fromlist=_method), _method)
            try:
                res = run_module(args['data'])
                if res[0]:
                    return {'data': res[1], 'error': None}, res[2]
                else:
                    return {'error': res[1]}, res[2]
            except Exception as _e:
                return {'error': str(_e)}, 500
        else:
            return {'error': "Module '" + args['module'] + "' non implémenté"}, 409
    else:
        return {'error': "Il manque une ou plusieurs donnée(s) obligatoire(s)"}, 400


if __name__ == "__main__":
    app.run()

