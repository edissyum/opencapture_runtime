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

import pyocr
import pytesseract
import pyocr.builders
import xml.etree.ElementTree as Et


class PyTesseract:
    def __init__(self, locale, log, path):
        self.Log = log
        self.path = path
        self.tool = ''
        self.text = ''
        self.lang = locale
        self.last_text = ''
        self.footer_text = ''
        self.header_text = ''
        self.OCRErrorsTable = {}
        self.footer_last_text = ''
        self.header_last_text = ''

        tools = pyocr.get_available_tools()
        self.tool = tools[0]
        self.get_ocr_errors_table()

    def text_builder(self, img):
        try:
            text = pytesseract.image_to_string(
                img,
                config='--psm 6',
                lang=self.lang
            )
            return text
        except pytesseract.pytesseract.TesseractError as t:
            self.Log.error('Tesseract ERROR : ' + str(t))

    def word_box_builder(self, img):
        try:
            return self.tool.image_to_string(
                img,
                lang=self.lang,
                builder=pyocr.builders.WordBoxBuilder(6)  # Argument is the choosen PSM
            )

        except pytesseract.pytesseract.TesseractError as t:
            self.Log.error('Tesseract ERROR : ' + str(t))

    def line_box_builder(self, img):
        try:
            return self.tool.image_to_string(
                img,
                lang=self.lang,
                builder=pyocr.builders.LineBoxBuilder(6)  # Argument is the choosen PSM
            )

        except pytesseract.pytesseract.TesseractError as t:
            self.Log.error('Tesseract ERROR : ' + str(t))

    @staticmethod
    def image_to_text_with_conf(img):
        # Retrieve data from image
        data = pytesseract.image_to_data(img, config='--psm 6', output_type='data.frame')
        data = data[data.conf > 0]
        data.head()

        # Transform words into line and get confidences for each
        lines = data.groupby(['page_num', 'block_num', 'par_num', 'line_num'])['text'].apply(lambda x: ' '.join(list(x.astype(str)))).tolist()
        confs = data.groupby(['page_num', 'block_num', 'par_num', 'line_num'])['conf'].mean().tolist()

        line_conf = []
        for i in range(len(lines)):
            if lines[i].strip():
                conf = round(confs[i], 2)
                if conf >= 50:
                    line_conf.append({'text': lines[i], 'conf': conf})
        return line_conf

    def get_ocr_errors_table(self):
        config_path = self.path + '/config/OCR_ERRORS.xml'
        root = Et.parse(config_path).getroot()

        for element in root:
            self.OCRErrorsTable[element.tag] = {}
            for child in element.findall('.//ELEMENT'):
                fix, misread = list(child)
                self.OCRErrorsTable[element.tag][fix.text] = misread.text
