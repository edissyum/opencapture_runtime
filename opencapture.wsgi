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
import sys
import logging

logging.basicConfig(stream=sys.stderr)
sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))
from rest import app as application
application.config['PATH'] = os.path.dirname(os.path.realpath(__file__))

with open(application.config['PATH'] + '/config/secrets', 'r') as secret_file:
    application.config['SECRET_KEY'] = secret_file.read()
