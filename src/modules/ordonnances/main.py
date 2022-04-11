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
import re
import time
import base64
from PIL import Image
from datetime import date
from flask import current_app
from datetime import datetime
from src.classes.Log import Log
from src.classes.SMTP import SMTP
from src.classes.Config import Config
from src.classes.Locale import Locale
from src.classes.Database import Database
from src.process.FindDate import FindDate
from src.process.FindRPPS import FindRPPS
from src.process.FindSecu import FindSecu
from src.process.FindAdeli import FindAdeli
from src.process.FindPerson import FindPerson
from src.classes.PyTesseract import PyTesseract
from src.functions import generate_tmp_filename
from src.process.FindPrescriber import FindPrescriber


def timer(start_time, end_time):
    hours, rem = divmod(end_time - start_time, 3600)
    minutes, seconds = divmod(rem, 60)
    return "{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds)


def get_near_words(arrayOfLine, zipCode, rangeX=20, rangeY=29, maxRangeX=200, maxRangeY=50):
    nearWord = {}
    currentyTL = zipCode['yTL']
    nearWord[currentyTL] = []
    for _line in arrayOfLine:
        # Check words on the same column and keep the coordonnates to check the word in the same line
        if abs(_line['xTL'] - zipCode['xTL']) <= rangeX and abs(_line['yTL'] - zipCode['yTL']) <= maxRangeY and _line['content'] != ' ':
            currentyTL = _line['yTL']
            currentxTL = _line['xTL']
            nearWord[currentyTL] = []
            for line2 in arrayOfLine:
                # Check the words on the same line
                if abs(line2['yTL'] - currentyTL) <= rangeY and abs(line2['xTL'] - currentxTL) <= maxRangeX and line2['content'] != ' ':
                    nearWord[currentyTL].append({
                        'xTL': line2['xTL'],
                        'yTL': line2['yTL'],
                        'xBR': line2['xBR'],
                        'yBR': line2['yBR'],
                        'content': line2['content'].replace(':', '/')
                    })
                    currentxTL = line2['xTL']
    patientText = ''
    for pos in sorted(nearWord):
        for word in nearWord[pos]:
            patientText += str(word['content']) + ' '
        patientText += '\n'
    patient = list(filter(None, patientText.split('\n')))
    patient_name = None
    if len(patient) > 1:
        patient_name = patient[len(patient) - 2].strip()
    if len(patient) == 1:
        patient_name = patient[0]

    patient_name = re.sub(r"(N(É|E|Ê|é|ê)(T)?(\(?E\)?)?\s*((L|1)E)?)|DATE\s*DE\s*NAISSANCE", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"\s+le\s+", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/\d{4}", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"[=‘|!,*)@#%(&$_?.^:\[\]0-9]", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"N°-", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"((I|F)dentifica(t|l)ion)?\s*Du\s*Pa(ñ|T)(i)?ent", '', patient_name, flags=re.IGNORECASE)
    return patient_name.strip()


def search_patient_from_birth_date(date_birth, text_words):
    arrayOfLine = []
    for t in text_words:
        arrayOfLine.append({
            'xTL': t.position[0][0],
            'yTL': t.position[0][1],
            'xBR': t.position[1][0],
            'yBR': t.position[1][1],
            'content': t.content
        })
        t.content = t.content.replace(':', '/')
        if date_birth[0] in t.content:
            date_birth_data = {
                'xTL': t.position[0][0],
                'yTL': t.position[0][1],
                'xBR': t.position[1][0],
                'yBR': t.position[1][1],
                'content': t.content
            }
            res = get_near_words(arrayOfLine, date_birth_data)
            return res


def find_date(dateProcess, text_with_conf, prescription_time_delta):
    dateProcess.prescriptionDate = None
    dateProcess.timeDelta = prescription_time_delta
    dateProcess.text = text_with_conf
    _date = dateProcess.run()
    dateProcess.prescriptionDate = _date
    dateProcess.timeDelta = 0
    date_birth = dateProcess.run()

    if date_birth:
        if _date and datetime.strptime(date_birth, '%d/%m/%Y') > datetime.strptime(_date, '%d/%m/%Y'):
            date_birth = None
        else:
            today = date.today().strftime("%d/%m/%Y")
            if datetime.strptime(date_birth, '%d/%m/%Y') > datetime.strptime(today, '%d/%m/%Y'):
                date_birth = None
    return _date, date_birth


def find_patient(date_birth, text_with_conf, log, locale, ocr, image_content):
    firstname, lastname = '', ''
    patient = FindPerson(text_with_conf, log, locale, ocr).run()
    if date_birth and patient is None:
        text_words = ocr.word_box_builder(image_content)
        patient = search_patient_from_birth_date(date_birth, text_words)

    if patient:
        if not patient.isupper():
            splitted = patient.split(' ')
            for data in splitted:
                if data.isupper():
                    lastname = data
                else:
                    firstname += data.capitalize() + ' '
        else:
            splitted = patient.split(' ')
            lastname = splitted[0]
            firstname = splitted[1] if len(splitted) > 1 else ''
    return [lastname.strip(), firstname.strip()]


def find_prescribers(text_with_conf, log, locale, ocr, database):
    ps_list = []
    prescribers = FindPrescriber(text_with_conf, log, locale, ocr).run()
    rpps_numbers = FindRPPS(text_with_conf, log, locale, ocr).run()

    if prescribers:
        for cpt in range(0, len(prescribers)):
            firstname = lastname = ''
            if not prescribers[cpt].isupper():
                splitted = prescribers[cpt].split(' ')
                for data in splitted:
                    if data.isupper():
                        lastname = data
                    else:
                        firstname += data.capitalize() + ' '
            else:
                splitted = prescribers[cpt].split(' ')
                lastname = splitted[0]
                firstname = splitted[1] if len(splitted) > 1 else ''

            if rpps_numbers[cpt]:
                info = database.select({
                    'select': ['id', 'nom', 'prenom', 'numero_adeli_cle'],
                    'table': ['application.praticien'],
                    'where': ['numero_rpps_cle = %s'],
                    'data': [rpps_numbers[cpt]],
                    'limit': 1
                })
                if info:
                    ps_list.append({'id': info[0]['id'], 'firstname': info[0]['prenom'].strip(), 'lastname': info[0]['nom'], 'rpps': rpps_numbers[cpt], 'adeli': info[0]['numero_adeli_cle']})
                else:
                    ps_list.append({'id': None, 'firstname': firstname.strip(), 'lastname': lastname.strip(), 'rpps': rpps_numbers[cpt]})
            else:
                ps_list.append({'id': None, 'firstname': firstname.strip(), 'lastname': lastname.strip(), 'rpps': rpps_numbers[cpt]})
    return ps_list


def find_adeli(text_with_conf, log, locale, ocr):
    data = FindAdeli(text_with_conf, log, locale, ocr).run()
    return data


def find_sociale_security_number(text_with_conf, log, locale, ocr):
    data = FindSecu(text_with_conf, log, locale, ocr).run()
    return data


def run(args):
    if 'fileContent' not in args or 'cabinetId' not in args:
        return False, "Il manque une ou plusieurs donnée(s) obligatoire(s)", 400

    file_content = args['fileContent']
    cabinet_id = args['cabinetId']

    path = current_app.config['PATH']
    file = path + '/' + generate_tmp_filename()
    with open(file, "wb") as _file:
        _file.write(base64.b64decode(file_content))

    # Set up the global settings
    _ret = _data = _http_code = None
    min_char_num = 280
    locale = Locale(path)
    config_mail = Config(path + '/config/mail.ini')
    config = Config(path + '/config/modules/ordonnances/config.ini')
    smtp = SMTP(
        config_mail.cfg['GLOBAL']['smtp_notif_on_error'],
        config_mail.cfg['GLOBAL']['smtp_host'],
        config_mail.cfg['GLOBAL']['smtp_port'],
        config_mail.cfg['GLOBAL']['smtp_login'],
        config_mail.cfg['GLOBAL']['smtp_pwd'],
        config_mail.cfg['GLOBAL']['smtp_ssl'],
        config_mail.cfg['GLOBAL']['smtp_starttls'],
        config_mail.cfg['GLOBAL']['smtp_dest_admin_mail'],
        config_mail.cfg['GLOBAL']['smtp_delay'],
        config_mail.cfg['GLOBAL']['smtp_auth'],
        config_mail.cfg['GLOBAL']['smtp_from_mail'],
    )
    log = Log(path + '/bin/log/OCRunTime.log', smtp)
    database = Database(log, config.cfg['DATABASE'])
    ocr = PyTesseract('fra', log, path)
    prescription_time_delta = 2190  # 6 ans max pour les dates d'ordonnance
    dateProcess = FindDate('', log, locale, prescription_time_delta)

    if os.path.splitext(file)[1] == '.jpg':
        start = time.time()
        # Set up data about the prescription
        image_content = Image.open(file)
        text_with_conf = ocr.image_to_text_with_conf(image_content)

        char_count = 0
        for line in text_with_conf:
            char_count += len(line['text'])

        if char_count > min_char_num:
            prescription_date, birth_date = find_date(dateProcess, text_with_conf, prescription_time_delta)
            patient_lastname, patient_firstname = find_patient(birth_date, text_with_conf, log, locale, ocr, image_content)
            prescribers = find_prescribers(text_with_conf, log, locale, ocr, database)
            adeli_number = find_adeli(text_with_conf, log, locale, ocr)
            sociale_security_number = find_sociale_security_number(text_with_conf, log, locale, ocr)

            patients_list = database.select({
                'select': ['nom', 'prenom', 'date_naissance', 'nir'],
                'table': ['application.patient'],
                'where': ['cabinet_id = %s'],
                'data': [cabinet_id]
            })

            _data = {
                'patients': [
                    {
                        'patient_id': 1,
                        'patient_nir': sociale_security_number,
                        'patient_birth_date': birth_date,
                        'patient_lastname': patient_lastname,
                        'patient_firstname': patient_firstname,
                    }
                ],
                'prescribers': prescribers,
                'acte': None,
                'description': None,
                'prescription_date': prescription_date,
            }

            end = time.time()
            _data.update({'process_time': timer(start, end)})
            _ret = True
            _http_code = 200
        else:
            _data = ''
            _ret = False
            _http_code = 204
    else:
        _ret = False
        _http_code = 404
        _data = "Document introuvable " + str(file)

    os.remove(file)
    return _ret, _data, _http_code
