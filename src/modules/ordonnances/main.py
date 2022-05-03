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
import json
import redis
import base64
from PIL import Image
from thefuzz import fuzz
from datetime import date
from flask import current_app
from datetime import datetime
from src.classes.Log import Log
from src.classes.SMTP import SMTP
from src.classes.Config import Config
from src.classes.Locale import Locale
from src.process.FindNir import FindNir
from src.classes.Database import Database
from src.process.FindDate import FindDate
from src.process.FindRPPS import FindRPPS
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
    patient_name = re.sub(r"((MADAME|MADEMOISELLE|MLLE|MME|(M)?ONSIEUR)|NOM\s*:)", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"\s+le\s+", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/\d{4}", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"[/=‘|!,*)@#%(&$_?.^:\[\]0-9]", '', patient_name, flags=re.IGNORECASE)
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
    if _date:
        _date = datetime.strptime(_date, '%d/%m/%Y').strftime('%Y%m%d')
    return _date, date_birth


def find_patient(date_birth, text_with_conf, log, locale, ocr, image_content, cabinet_id, prescribers, patient=None):
    firstname, lastname = '', ''
    patients_cabinet = None
    patients = []
    patient_found = False
    levenshtein_ratio = 80

    if patient is None:
        patient = FindPerson(text_with_conf, log, locale, ocr).run()
    nir = FindNir(text_with_conf, log, locale, ocr).run()

    if date_birth and patient is None:
        text_words = ocr.word_box_builder(image_content)
        patient = search_patient_from_birth_date(date_birth, text_words)
    if patient:
        if not patient.isupper():
            splitted = patient.split(' ')
            for data in splitted:
                if data.isupper():
                    lastname += data.strip() + ' '
                else:
                    firstname += data.strip().capitalize() + ' '
            firstname = firstname.strip()
            lastname = lastname.strip()
        else:
            splitted = patient.split(' ')
            lastname = splitted[0].strip()
            firstname = splitted[1].strip() if len(splitted) > 1 else ''
    if nir or (lastname and firstname) or date_birth:
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        patients_cabinet = r.get('patient_cabinet_' + str(cabinet_id))
        if patients_cabinet:
            if date_birth:
                date_birth = datetime.strptime(date_birth, '%d/%m/%Y').strftime('%Y%m%d')
            for _patient in json.loads(patients_cabinet):
                if date_birth and lastname and firstname and nir:
                    if date_birth == _patient['date_naissance'] and fuzz.ratio(lastname.lower(), _patient['nom'].lower()) >= levenshtein_ratio and fuzz.ratio(firstname.lower(), _patient['prenom'].lower()) >= levenshtein_ratio and nir == _patient['nir']:
                        patient_found = True
                        patients.append(_patient)
                        break

                if date_birth and nir:
                    if date_birth == _patient['date_naissance'] and nir == _patient['nir']:
                        patient_found = True
                        patients.append(_patient)
                        break

                if date_birth and lastname and firstname:
                    if date_birth == _patient['date_naissance'] and fuzz.ratio(lastname.lower(), _patient['nom'].lower()) >= levenshtein_ratio and fuzz.ratio(firstname.lower(), _patient['prenom'].lower()) >= levenshtein_ratio:
                        patient_found = True
                        patients.append(_patient)
                        break

                if date_birth and lastname:
                    if date_birth == _patient['date_naissance'] and fuzz.ratio(lastname.lower(), _patient['nom'].lower()) >= levenshtein_ratio:
                        patient_found = True
                        patients.append(_patient)
                        break

                if nir:
                    if nir == _patient['nir']:
                        patient_found = True
                        patients.append(_patient)
                        break

                if lastname and firstname:
                    if fuzz.ratio(lastname.lower(), _patient['nom'].lower()) >= levenshtein_ratio and fuzz.ratio(firstname.lower(), _patient['prenom'].lower()) >= levenshtein_ratio:
                        patient_found = True
                        patients.append(_patient)
                        break
                    if fuzz.ratio(lastname.lower(), _patient['prenom'].lower()) >= levenshtein_ratio and fuzz.ratio(firstname.lower(), _patient['nom'].lower()) >= levenshtein_ratio:
                        patient_found = True
                        patients.append(_patient)
                        break

                if date_birth:
                    if date_birth == _patient['date_naissance']:
                        patient_found = True
                        patients.append(_patient)
                        break

            if patient_found:
                for _p in patients:
                    if _p['date_naissance']:
                        _p['date_naissance'] = datetime.strptime(_p['date_naissance'], '%Y%m%d').strftime('%d/%m/%Y')

    if not patient_found:
        r = redis.StrictRedis(host='localhost', port=6379, db=0)
        list_names = json.loads(r.get('names'))

        if list_names:
            for text in text_with_conf:
                found_in_line = False
                _patient = prenom = ''
                if not found_in_line:
                    for name in list_names:
                        if name.lower() in text['text'].lower() and not found_in_line:
                            if prescribers:
                                for prescriber in prescribers:
                                    if prescriber['nom'].lower() not in text['text'].lower() and text['conf'] > 65:
                                        for word in text['text'].split(' '):
                                            if fuzz.ratio(name.lower(), word.lower()) >= 85:
                                                _patient = text['text']
                                                found_in_line = True
                                                prenom = name
                                                for _prescriber_name in re.finditer(r"((D|P|J)?OCTEUR(?!S)|DR\.).*", _patient, flags=re.IGNORECASE):
                                                    _patient = ''
                                        break

                            if _patient:
                                firstname = lastname = ''
                                if not _patient.isupper():
                                    splitted = _patient.split(' ')
                                    if len(splitted) > 2:
                                        for _cpt in range(0, len(splitted)):
                                            if prenom.lower() in splitted[_cpt].lower():
                                                _patient = splitted[_cpt - 1] + ' '
                                                _patient += splitted[_cpt]
                                                if len(splitted) > _cpt + 1:
                                                    _patient = ' ' + splitted[_cpt + 1]
                                    if not _patient.isupper():
                                        splitted = _patient.split(' ')
                                        if splitted[0] == 'M':
                                            del splitted[0]
                                        for data in splitted:
                                            if data.isupper():
                                                lastname += data.strip() + ' '
                                            else:
                                                firstname += data.strip().capitalize() + ' '
                                        firstname = firstname.strip()
                                        lastname = lastname.strip()
                                    else:
                                        splitted = _patient.split(' ')
                                        if splitted[0] == 'M':
                                            del splitted[0]
                                        lastname = splitted[0].strip()
                                        firstname = splitted[1].strip() if len(splitted) > 1 else ''
                                else:
                                    splitted = _patient.split(' ')
                                    if splitted[0] == 'M':
                                        del splitted[0]
                                    lastname = splitted[0].strip()
                                    firstname = splitted[1].strip() if len(splitted) > 1 else ''

                                if not patients_cabinet:
                                    r = redis.StrictRedis(host='localhost', port=6379, db=0)
                                    patients_cabinet = r.get('patient_cabinet_' + str(cabinet_id))
                                for _patient in json.loads(patients_cabinet):
                                    if lastname and firstname:
                                        if fuzz.ratio(lastname.lower(), _patient['nom'].lower()) >= levenshtein_ratio and fuzz.ratio(firstname.lower(), _patient['prenom'].lower()) >= levenshtein_ratio:
                                            patient_found = True
                                            patients.append(_patient)
                                            break
                                        if fuzz.ratio(lastname.lower(), _patient['prenom'].lower()) >= levenshtein_ratio and fuzz.ratio(firstname.lower(), _patient['nom'].lower()) >= levenshtein_ratio:
                                            patient_found = True
                                            patients.append(_patient)
                                            break
                                    elif lastname and not firstname:
                                        print('here')
                                        if fuzz.ratio(lastname.lower(), _patient['nom'].lower()) >= levenshtein_ratio:
                                            patient_found = True
                                            patients.append(_patient)
                                            break

    if not patient_found:
        if date_birth:
            try:
                date_birth = datetime.strptime(date_birth, '%d/%m/%Y').strftime('%Y%m%d')
            except ValueError:
                date_birth = ''

        patients.append({
            'id': '',
            'prenom': firstname.strip(),
            'nom': lastname.strip(),
            'date_naissance': date_birth,
            'nir': nir
        })

    return patients


def find_prescribers(text_with_conf, log, locale, ocr, database, cabinet_id):
    ps_list = []
    prescriber_found = False
    prescribers = FindPrescriber(text_with_conf, log, locale, ocr).run()
    rpps_numbers = FindRPPS(text_with_conf, log, locale, ocr).run()
    adeli_numbers = []
    levenshtein_ratio = '2'
    # for t in text_with_conf:
    #     print(t['text'])
    if prescribers:
        for cpt in range(0, len(prescribers)):
            if rpps_numbers and cpt <= len(rpps_numbers) - 1 and rpps_numbers[cpt]:
                info = database.select({
                    'select': ['id as id_praticien', 'nom', 'prenom', 'numero_adeli_cle', 'numero_rpps_cle'],
                    'table': ['application.praticien'],
                    'where': ['numero_rpps_cle = %s', 'cabinet_id = %s'],
                    'data': [rpps_numbers[cpt], cabinet_id],
                    'limit': 1
                })

                if info:
                    prescriber_found = True
                    info[0]['id_prescripteur'] = ''
                    ps_list.append(info[0])

            if not prescriber_found:
                adeli_numbers = FindAdeli(text_with_conf, log, locale, ocr).run()
                if adeli_numbers and cpt <= len(adeli_numbers) - 1 and adeli_numbers[cpt]:
                    info = database.select({
                        'select': ['id as id_praticien', 'nom', 'prenom', 'numero_rpps_cle', 'numero_adeli_cle'],
                        'table': ['application.praticien'],
                        'where': ['numero_adeli_cle = %s', 'cabinet_id = %s'],
                        'data': [adeli_numbers[cpt], cabinet_id],
                        'limit': 1
                    })
                    if info:
                        prescriber_found = True
                        info[0]['id_prescripteur'] = ''
                        ps_list.append(info[0])

            firstname = lastname = ''
            if not prescribers[cpt].isupper():
                splitted = prescribers[cpt].split(' ')
                for data in splitted:
                    if data.isupper():
                        lastname = data.strip()
                    else:
                        firstname += data.strip().capitalize() + ' '
                firstname = firstname.strip()
                lastname = lastname.strip()
            else:
                splitted = prescribers[cpt].split(' ')
                lastname = splitted[0].strip()
                firstname = splitted[1].strip() if len(splitted) > 1 else ''

            if not prescriber_found and firstname and lastname:
                info = database.select({
                    'select': ['id as id_praticien', 'nom', 'prenom', 'numero_adeli_cle', 'numero_rpps_cle'],
                    'table': ['application.praticien'],
                    'where': ['(LEVENSHTEIN(nom, %s) <= ' + levenshtein_ratio + ' AND LEVENSHTEIN(prenom, %s) <= ' + levenshtein_ratio + ') OR (LEVENSHTEIN(prenom, %s) <= ' + levenshtein_ratio + ' AND LEVENSHTEIN(nom, %s) <= ' + levenshtein_ratio + ')', 'cabinet_id = %s'],
                    'data': [lastname, firstname, lastname, firstname, cabinet_id],
                    'limit': 1
                })
                if info:
                    prescriber_found = True
                    info[0]['id_prescripteur'] = ''
                    ps_list.append(info[0])
                else:
                    info = database.select({
                        'select': ['id as id_prescripteur', 'nom', 'prenom', 'numero_idfact_cle as numero_adeli_cle', 'numero_rpps_cle'],
                        'table': ['sesam.prescripteur'],
                        'where': ['(LEVENSHTEIN(nom, %s) <= ' + levenshtein_ratio + ' AND LEVENSHTEIN(prenom, %s) <= ' + levenshtein_ratio + ') OR (LEVENSHTEIN(prenom, %s) <= ' + levenshtein_ratio + ' AND LEVENSHTEIN(nom, %s) <= ' + levenshtein_ratio + ')'],
                        'data': [lastname, firstname, lastname, firstname],
                        'limit': 1
                    })
                    if info:
                        prescriber_found = True
                        info[0]['id_praticien'] = ''
                        ps_list.append(info[0])

            if not prescriber_found:
                ps_list.append({
                    'id_praticien': '',
                    'id_prescripteur': '',
                    'prenom': firstname.strip(),
                    'nom': lastname.strip(),
                    'numero_adeli_cle': adeli_numbers[cpt] if adeli_numbers and cpt == len(adeli_numbers) - 1 else '',
                    'numero_rpps_cle': rpps_numbers[cpt] if rpps_numbers and cpt == len(rpps_numbers) - 1 else ''
                })
    else:
        if rpps_numbers:
            for rpps in rpps_numbers:
                info = database.select({
                    'select': ['id as id_praticien', 'nom', 'prenom', 'numero_adeli_cle', 'numero_rpps_cle'],
                    'table': ['application.praticien'],
                    'where': ['numero_rpps_cle = %s', 'cabinet_id = %s'],
                    'data': [rpps, cabinet_id],
                    'limit': 1
                })
                if info:
                    prescriber_found = True
                    info[0]['id_prescripteur'] = ''
                    ps_list.append(info[0])

        if not prescriber_found:
            adeli_numbers = FindAdeli(text_with_conf, log, locale, ocr).run()
            if adeli_numbers:
                for adeli in adeli_numbers:
                    info = database.select({
                        'select': ['id as id_praticien', 'nom', 'prenom', 'numero_adeli_cle', 'numero_rpps_cle'],
                        'table': ['application.praticien'],
                        'where': ['numero_adeli_cle = %s', 'cabinet_id = %s'],
                        'data': [adeli, cabinet_id],
                        'limit': 1
                    })
                    if info:
                        info[0]['id_prescripteur'] = ''
                        ps_list.append(info[0])

    return ps_list


def run(args):
    if 'fileContent' not in args or 'cabinetId' not in args:
        return False, "Il manque une ou plusieurs donnée(s) obligatoire(s)", 400

    cabinet_id = args['cabinetId']
    file_content = args['fileContent']

    path = current_app.config['PATH']
    file = path + '/' + generate_tmp_filename()
    with open(file, "wb") as _file:
        _file.write(base64.b64decode(file_content))

    # Set up the global settings
    _ret = _data = _http_code = None
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
    prescription_time_delta = config.cfg['GLOBAL']['prescription_time_delta']
    min_char = config.cfg['GLOBAL']['min_char']
    date_process = FindDate('', log, locale, prescription_time_delta)

    if os.path.splitext(file)[1] == '.jpg':
        start = time.time()
        # Set up data about the prescription
        image_content = Image.open(file)
        text_with_conf, char_count = ocr.image_to_text_with_conf(image_content)

        if int(char_count) > int(min_char):
            prescription_date, birth_date = find_date(date_process, text_with_conf, prescription_time_delta)
            prescribers = find_prescribers(text_with_conf, log, locale, ocr, database, cabinet_id)
            patients = find_patient(birth_date, text_with_conf, log, locale, ocr, image_content, cabinet_id, prescribers)
            if not patients:
                patients = [{'id': '', 'prenom': '', 'nom': '', 'nir': ''}]
            if not prescribers:
                prescribers = [{'id_praticien': '', 'id_prescripteur': '', 'prenom': '', 'nom': '', 'numero_rpps_cle': '', 'numero_adeli_cle': ''}]

            _data = {
                'patients': patients,
                'prescripteurs': prescribers,
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
