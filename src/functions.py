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

import uuid
import datetime


def generate_tmp_filename():
    now = datetime.datetime.now()
    year = str(now.year)
    day = str('%02d' % now.day)
    hour = str('%02d' % now.hour)
    month = str('%02d' % now.month)
    minute = str('%02d' % now.minute)
    seconds = str('%02d' % now.second)
    return 'bin/tmp/' + day + month + year + '_' + hour + minute + seconds + '_' + uuid.uuid4().hex + '.jpg'
