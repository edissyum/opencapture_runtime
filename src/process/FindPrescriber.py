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


class FindPrescriber:
    def __init__(self, text, log, locale, ocr):
        self.date = ''
        self.Log = log
        self.ocr = ocr
        self.text = text
        self.Locale = locale

    @staticmethod
    def process(line):
        line = line.replace('/', '').replace('‘', '').replace('!', '')
        for _prescriber_name in re.finditer(r"((D|P|J)?OCTEUR(?!S)|DR\.).*", line, flags=re.IGNORECASE):
            if _prescriber_name.group():
                prescriber_name = re.sub(r"((D|P|J)?OCTEUR(?!S)|DR\.)", '', _prescriber_name.group(), flags=re.IGNORECASE)
                prescriber_name = re.sub(r"[0-9]", '', prescriber_name, flags=re.IGNORECASE)
                prescriber_name = re.sub(r"[|!,*)@#%(&$_?.^:\[\]]", '', prescriber_name, flags=re.IGNORECASE)
                splitted = prescriber_name.strip().split(' ')
                if len(splitted) > 1:
                    prescriber_name = splitted[0] + ' ' + splitted[1]
                return prescriber_name.strip()
        return []

    def run(self):
        for line in self.text:
            res = self.process(line['text'])
            if res:
                self.Log.info('Prescriber name found : ' + res)
                return res
