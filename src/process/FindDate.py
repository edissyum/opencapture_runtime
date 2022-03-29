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

import re
from datetime import datetime


class FindDate:
    def __init__(self, text, log, locale, time_delta):
        self.date = ''
        self.Log = log
        self.text = text
        self.Locale = locale
        self.timeDelta = time_delta
        self.prescriptionDate = None

    def format_date(self, date, convert=False):
        if date:
            date = date.replace('1er', '01')  # Replace some possible inconvenient char
            date = date.replace(',', ' ')  # Replace some possible inconvenient char
            date = date.replace('/', ' ')  # Replace some possible inconvenient char
            date = date.replace('-', ' ')  # Replace some possible inconvenient char
            date = date.replace('.', ' ')  # Replace some possible inconvenient char

            if convert:
                date_convert = self.Locale.arrayDate
                for key in date_convert:
                    for month in date_convert[key]:
                        if month.lower() in date.lower():
                            date = (date.lower().replace(month.lower(), key))
                            break
            try:
                # Fix to handle date with 2 digits year
                length_of_year = len(date.split(' ')[2])
                if length_of_year == 2:
                    regex = self.Locale.dateTimeFormat.replace('%Y', '%y')
                else:
                    regex = self.Locale.dateTimeFormat

                date = datetime.strptime(date, regex).strftime(self.Locale.formatDate)
                # Check if the date of the document isn't too old. 62 (default value) is equivalent of 2 months
                today = datetime.now()
                doc_date = datetime.strptime(date, self.Locale.formatDate)
                timedelta = today - doc_date

                if self.prescriptionDate is None:
                    if int(self.timeDelta) not in [-1, 0]:
                        if timedelta.days > int(self.timeDelta) or timedelta.days < 0:
                            date = False
                else:
                    if self.prescriptionDate == date:
                        date = False
                return date
            except (ValueError, IndexError):
                return False
        else:
            return False

    def process(self, line):
        line = line.replace(':', '/')
        for _date in re.finditer(r"" + self.Locale.dateRegex + "", line):
            date = self.format_date(_date.group(), True)
            if date:
                self.date = date
                return date
            return False

    def run(self):
        for line in self.text:
            res = self.process(line['text'].upper())
            if res:
                if self.prescriptionDate is None:
                    self.Log.info('Prescription date found : ' + res)
                else:
                    self.Log.info('Birth date found : ' + res)
                return res

        for line in self.text:
            res = self.process(re.sub(r'(\d)\s+(\d)', r'\1\2', line['text']))
            if not res:
                res = self.process(line['text'])
                if res:
                    return res
            else:
                return res
