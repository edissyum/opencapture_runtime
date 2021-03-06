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
import math


class FindRPPS:
    def __init__(self, text, log, locale, ocr):
        self.date = ''
        self.Log = log
        self.ocr = ocr
        self.text = text
        self.Locale = locale

    @staticmethod
    def rpps_verification(value):
        if len(value) != 11:
            return False
        try:
            int(value)
        except ValueError:
            return False

        numero = value[:10]
        cle = value[10:]

        if numero == '0000000000':
            return True

        pos = 1
        cletmp = 0
        for num in reversed(numero):
            num = int(num)
            if pos % 2 != 0:
                num *= 2

            pos = pos + 1
            if num >= 10:
                cletmp += math.floor(num / 10)
                cletmp += num % 10
            else:
                cletmp += num
        tmpCle = int(str(cletmp)[len(str(cletmp)) - 1])
        cleFinal = 10 - tmpCle
        if cleFinal == 10:
            cleFinal = 0

        if int(cleFinal) == int(cle):
            return True
        return False

    def process(self, line, second=False):
        _rrps = []
        for item in self.ocr.OCRErrorsTable['NUMBERS']:
            pattern = r'[%s]' % self.ocr.OCRErrorsTable['NUMBERS'][item]
            line = re.sub(pattern, item, line)

        line = line.replace('/', '').replace(' ', '').replace('-', '').replace('.', '')

        for rpps in re.finditer(r"(N(??|O)\s*)?(RPPS).*", line.upper()):
            rpps = re.split(r"(?:(?:N(?:??|O))\s*(?:(RPPS)))", rpps.group(), flags=re.IGNORECASE)
            for _r in rpps:
                if _r:
                    _r = re.sub(r"[|!,*)@#%(&$_?.^:;\[\]]", '', _r, flags=re.IGNORECASE)
                    _r = re.sub(r"(N(??|O)\s*)?(RPPS)", '', _r, flags=re.IGNORECASE)
                    for item in self.ocr.OCRErrorsTable['NUMBERS']:
                        pattern = r'[%s]' % self.ocr.OCRErrorsTable['NUMBERS'][item]
                        _ad = re.sub(pattern, item, _r)
                    if _r and self.rpps_verification(_r):
                        if _r.strip() not in _rrps:
                            _rrps.append(_r.strip())

        if second:
            for _rpps in re.finditer(r"\d{11}", line):
                data = _rpps.group()
                if data and self.rpps_verification(data):
                    if data not in _rrps:
                        _rrps.append(data)
        return _rrps

    def run(self):
        for line in self.text:
            res = self.process(line['text'].upper())
            if res:
                self.Log.info('RPPS number found : ' + str(res))
                return res

        for line in self.text:
            res = self.process(line['text'].upper(), True)
            if res:
                self.Log.info('RPPS number found : ' + str(res))
                return res
