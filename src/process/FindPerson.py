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


class FindPerson:
    def __init__(self, text, log, locale, ocr):
        self.date = ''
        self.Log = log
        self.ocr = ocr
        self.text = text
        self.Locale = locale

    @staticmethod
    def process(line):
        line = line.replace('/', '').replace('-', '').replace('=', '')
        for _person_name in re.finditer(r"((MADAME|MADEMOISELLE|MLLE|(M)?ONSIEUR)|NOM\s*:).*", line, flags=re.IGNORECASE):
            if _person_name.group():
                person_name = re.sub(r"((MADAME|MADEMOISELLE|MLLE|MME|(M)?ONSIEUR)|NOM\s*:)", '', _person_name.group(), flags=re.IGNORECASE)
                person_name = re.sub(r"\d", '', person_name, flags=re.IGNORECASE)
                person_name = re.sub(r"[|!,*)@#%(&$_?.^:\[\]]", '', person_name, flags=re.IGNORECASE)
                person_name = re.sub(r"(N(É|E)(\(?E\)?)?\s*(L|1)E)|DATE\s*DE\s*NAISSANCE", '', person_name, flags=re.IGNORECASE)
                return person_name.strip()
        return []

    def run(self):
        for line in self.text:
            res = self.process(line['text'])
            if res:
                self.Log.info('Person found : ' + res)
                return res
