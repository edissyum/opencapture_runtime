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


class FindAdeli:
    def __init__(self, text, log, locale, ocr):
        self.date = ''
        self.Log = log
        self.ocr = ocr
        self.text = text
        self.Locale = locale

    @staticmethod
    def adeli_verification(value):
        if len(value) != 9:
            return False
        try:
            int(value)
        except ValueError:
            return False

        numero = value[:8]
        cle = value[8:]

        if numero == '00000000':
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
        _adelis_list = []
        if second:
            for item in self.ocr.OCRErrorsTable['NUMBERS']:
                pattern = r'[%s]' % self.ocr.OCRErrorsTable['NUMBERS'][item]
                line = re.sub(pattern, item, line)

        line = line.replace('/', '').replace(' ', '').replace('-', '')
        for _adeli in re.finditer(r"N(°|O)\s*(FIN(E|C)SS|AD(E|É)LI).*", line.upper()):
            adelis = re.split(r"(?:(?:N(?:°|O))\s*(?:FIN(?:E|C)SS|AD(?:E|É)LI))", _adeli.group(), flags=re.IGNORECASE)
            for _ad in adelis:
                if _ad:
                    _ad = re.sub(r"[|!,*)@#%(&$_?.^:\[\]]", '', _ad, flags=re.IGNORECASE)
                    for item in self.ocr.OCRErrorsTable['NUMBERS']:
                        pattern = r'[%s]' % self.ocr.OCRErrorsTable['NUMBERS'][item]
                        _ad = re.sub(pattern, item, _ad)
                    if _ad and self.adeli_verification(_ad):
                        _adelis_list.append(_ad.strip())

        if second:
            for _adeli in re.finditer(r"\d{9}", line):
                data = _adeli.group()
                if data and self.adeli_verification(data):
                    _adelis_list.append(data)
        return _adelis_list

    def run(self):
        for line in self.text:
            res = self.process(line['text'].upper())
            if res:
                self.Log.info('Adeli number found : ' + str(res))
                return res

        for line in self.text:
            res = self.process(line['text'].upper(), True)
            if res:
                self.Log.info('Adeli number found : ' + str(res))
                return res
