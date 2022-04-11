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

from flask import Flask, request
from src.functions import is_dev
from src.auth import token_required, generate_token

app = Flask(__name__)

# La clé corresponds à ce qui doit être envoyé lors de l'appel au WS '/oc/getDocumentInformations' dans la variable "module"
# La partie 'filename' contient le nom du fichier, qui doit se trouvé dans le dossier src/modules/
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
    days_before_exp = 1
    token = generate_token(days_before_exp)
    return {
        'auth_token': str(token),
        'days_before_exp': days_before_exp,
    }


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
            res = run_module(args['data'])
            if res[0]:
                return {'data': res[1], 'error': False}, res[2]
            else:
                return {'error': res[1]}, res[2]
        else:
            return {'error': "Module '" + args['module'] + "' non implémenté"}, 409
    else:
        return {'error': "Il manque une ou plusieurs donnée(s) obligatoire(s)"}, 400


if __name__ == "__main__":
    app.run()

