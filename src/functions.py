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
import uuid
import datetime
import functools
from flask import current_app


def is_dev(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'PATH' not in current_app.config:
            current_app.config['PATH'] = os.path.dirname(os.path.realpath(__file__)).replace('/src', '')
            with open(current_app.config['PATH'] + '/config/secrets', 'r') as secret_file:
                current_app.config['SECRET_KEY'] = secret_file.read()
        return view(**kwargs)
    return wrapped_view


def generate_tmp_filename():
    now = datetime.datetime.now()
    year = str(now.year)
    day = str('%02d' % now.day)
    hour = str('%02d' % now.hour)
    month = str('%02d' % now.month)
    minute = str('%02d' % now.minute)
    seconds = str('%02d' % now.second)
    return 'bin/tmp/' + day + month + year + '_' + hour + minute + seconds + '_' + uuid.uuid4().hex + '.jpg'
