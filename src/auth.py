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

import jwt
import datetime
import functools
from flask import current_app, request, jsonify


def token_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split('Bearer')[1].lstrip()
            try:
                jwt.decode(str(token), current_app.config['SECRET_KEY'], algorithms=["HS256"])
            except (jwt.InvalidTokenError, jwt.InvalidAlgorithmError, jwt.InvalidSignatureError,
                    jwt.ExpiredSignatureError, jwt.exceptions.DecodeError) as e:
                return jsonify({"errors": "JWT_ERROR", "message": str(e)}), 500
        else:
            return jsonify({"errors": "JWT_ERROR", "message": "Valid token is mandatory"}), 500
        return view(**kwargs)
    return wrapped_view


def generate_token(days_before_exp):
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=days_before_exp, seconds=0),
        'iat': datetime.datetime.utcnow(),
        'sub': 'Open-Capture Runtime'
    }
    token = jwt.encode(
        payload,
        current_app.config.get('SECRET_KEY'),
        algorithm='HS256'
    )
    return token
