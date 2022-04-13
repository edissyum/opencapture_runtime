##########################
#   POC EDISSYUM - CBA   #
#      Décembre 2021     #
#      Nathan CHEVAL     #
##########################
import json
import os
import re
import csv
import time

import redis
from PIL import Image
from thefuzz import fuzz
from datetime import date
from datetime import datetime
from classes.Log import Log
from classes.Locale import Locale
from process.FindDate import FindDate
from process.FindRPPS import FindRPPS
from process.FindNir import FindNir
from process.FindAdeli import FindAdeli
from process.FindPerson import FindPerson
from classes.PyTesseract import PyTesseract
from process.FindPrescriber import FindPrescriber
from src.classes.Config import Config
from src.classes.Database import Database


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
        # print(_line, zipCode['xTL'], _line['xTL'] - zipCode['xTL'], abs( _line['xTL'] - zipCode['xTL']))
        if abs(_line['xTL'] - zipCode['xTL']) <= rangeX and abs(_line['yTL'] - zipCode['yTL']) <= maxRangeY and _line['content'] != ' ':
            currentyTL = _line['yTL']
            currentxTL = _line['xTL']
            nearWord[currentyTL] = []
            for line2 in arrayOfLine:
                # Check the words on the same line
                # print(line2, currentyTL, line2['yTL'] - currentyTL, abs(line2['yTL'] - currentyTL))
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
    patient_name = re.sub(r"((MADAME|MADEMOISELLE|MLLE|MME|(M)?ONSIEUR)|NOM\s*:)", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"(0[1-9]|[12][0-9]|3[01])/(0[1-9]|1[0-2])/\d{4}", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"[=‘|!,*)@#%(&$_?.^:\[\]0-9]", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"N°-", '', patient_name, flags=re.IGNORECASE)
    patient_name = re.sub(r"((I|F)dentifica(t|l)ion)?\s*Du\s*Pa(ñ|T)(i)?ent", '', patient_name, flags=re.IGNORECASE)
    return patient_name.strip()


def search_patient_from_birth_date(date_birth, text_words):
    arrayOfLine = []
    for text in text_words:
        arrayOfLine.append({
            'xTL': text.position[0][0],
            'yTL': text.position[0][1],
            'xBR': text.position[1][0],
            'yBR': text.position[1][1],
            'content': text.content
        })
        text.content = text.content.replace(':', '/')
        if date_birth[0] in text.content:
            date_birth_data = {
                'xTL': text.position[0][0],
                'yTL': text.position[0][1],
                'xBR': text.position[1][0],
                'yBR': text.position[1][1],
                'content': text.content
            }
            res = get_near_words(arrayOfLine, date_birth_data)
            return res


def find_date():
    date_process.prescriptionDate = None
    date_process.timeDelta = prescription_time_delta
    log.info("Traitement de l'ordonnance " + prescription)
    date_process.text = text_with_conf
    _date = date_process.run()
    date_process.prescriptionDate = _date
    date_process.timeDelta = 0
    date_birth = date_process.run()

    if date_birth:
        if _date and datetime.strptime(date_birth, '%d/%m/%Y') > datetime.strptime(_date, '%d/%m/%Y'):
            date_birth = None
        else:
            today = date.today().strftime("%d/%m/%Y")
            if datetime.strptime(date_birth, '%d/%m/%Y') > datetime.strptime(today, '%d/%m/%Y'):
                date_birth = None
    return _date, date_birth


def find_patient(date_birth, text_with_conf, log, locale, ocr, image_content, cabinet_id):
    firstname, lastname = '', ''
    patients = []
    patient_found = False
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
                    lastname = data.strip()
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
                if (nir and nir == _patient['nir']) or \
                   ((date_birth and not nir and not lastname and not firstname) and date_birth == _patient['date_naissance']) or \
                   ((lastname and date_birth) and lastname.lower() == _patient['nom'] and date_birth == _patient['date_naissance']) or \
                   ((firstname and date_birth) and firstname.lower() == _patient['prenom'] and date_birth == _patient['date_naissance']) or \
                   ((lastname and nir) and lastname.lower() == _patient['nom'].lower() and nir == _patient['nir']) or \
                   ((firstname and nir) and firstname.lower() == _patient['prenom'].lower() and nir == _patient['nir']) or \
                   ((firstname and lastname) and firstname.lower() == _patient['prenom'].lower() and lastname.lower() == _patient['nom'].lower()):
                    patient_found = True
                    _patient['date_naissance'] = datetime.strptime(_patient['date_naissance'], '%Y%m%d').strftime('%d/%m/%Y')
                    patients.append({'id': _patient['id'], 'firstname': _patient['prenom'].strip(), 'lastname': _patient['nom'], 'birth_date': _patient['date_naissance'], 'nir': _patient['nir']})

        if not patient_found:
            patients.append({
                'id': None,
                'firstname': firstname,
                'lastname': lastname,
                'date_naissance': date_birth,
                'nir': nir
            })
    return patients


# def find_patient(date_birth):
#     firstname, lastname = '', ''
#     patient = FindPerson(text_with_conf, log, locale, ocr).run()
#     if date_birth and patient is None:
#         text_words = ocr.word_box_builder(image_content)
#         patient = search_patient_from_birth_date(date_birth, text_words)
#
#     if patient:
#         if not patient.isupper():
#             splitted = patient.split(' ')
#             for data in splitted:
#                 if data.isupper():
#                     lastname = data
#                 else:
#                     firstname += data.capitalize() + ' '
#         else:
#             splitted = patient.split(' ')
#             lastname = splitted[0]
#             firstname = splitted[1] if len(splitted) > 1 else ''
#     return [lastname.strip(), firstname.strip()]


def find_prescribers(text_with_conf, log, locale, ocr, database):
    ps_list = []
    prescriber_found = False
    prescribers = FindPrescriber(text_with_conf, log, locale, ocr).run()
    rpps_numbers = FindRPPS(text_with_conf, log, locale, ocr).run()
    adeli_numbers = FindAdeli(text_with_conf, log, locale, ocr).run()
    if prescribers:
        for cpt in range(0, len(prescribers)):
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

            if rpps_numbers and cpt == len(rpps_numbers) - 1 and rpps_numbers[cpt]:
                info = database.select({
                    'select': ['id', 'nom', 'prenom', 'numero_adeli_cle'],
                    'table': ['application.praticien'],
                    'where': ['numero_rpps_cle = %s'],
                    'data': [rpps_numbers[cpt]],
                    'limit': 1
                })
                if info:
                    prescriber_found = True
                    ps_list.append({'id': info[0]['id'], 'firstname': info[0]['prenom'].strip(), 'lastname': info[0]['nom'], 'rpps': rpps_numbers[cpt], 'adeli': info[0]['numero_adeli_cle']})

            if not prescriber_found and adeli_numbers and cpt == len(adeli_numbers) - 1 and adeli_numbers[cpt]:
                info = database.select({
                    'select': ['id', 'nom', 'prenom', 'numero_rpps_cle'],
                    'table': ['application.praticien'],
                    'where': ['numero_adeli_cle = %s'],
                    'data': [adeli_numbers[cpt]],
                    'limit': 1
                })
                if info:
                    prescriber_found = True
                    ps_list.append({'id': info[0]['id'], 'firstname': info[0]['prenom'].strip(), 'lastname': info[0]['nom'], 'rpps': info[0]['numero_rpps_cle'], 'adeli': adeli_numbers[cpt]})

            if not prescriber_found and firstname and lastname:
                info = database.select({
                    'select': ['id', 'nom', 'prenom', 'numero_idfact_cle', 'numero_rpps_cle'],
                    'table': ['sesam.prescripteur'],
                    'where': ['(nom ILIKE %s AND prenom ILIKE %s) OR (prenom ILIKE %s AND nom ILIKE %s)'],
                    'data': [lastname, firstname, lastname, firstname],
                    'limit': 1
                })
                if info:
                    prescriber_found = True
                    ps_list.append({'id': info[0]['id'], 'firstname': info[0]['prenom'].strip(), 'lastname': info[0]['nom'], 'rpps': info[0]['numero_rpps_cle'], 'adeli': info[0]['numero_idfact_cle']})

            if not prescriber_found:
                ps_list.append({'id': '', 'firstname': firstname.strip(), 'lastname': lastname.strip(), 'adeli': adeli_numbers[cpt] if adeli_numbers and cpt == len(adeli_numbers) - 1 else '', 'rpps': rpps_numbers[cpt] if rpps_numbers and cpt == len(rpps_numbers) - 1 else ''})
    return ps_list

# def find_prescriber(text_with_conf, log, locale, ocr):
#     prescribers = FindPrescriber(text_with_conf, log, locale, ocr).run()
#     if prescribers:
#         for cpt in range(0, len(prescribers)):
#             firstname = lastname = ''
#             if not prescribers[cpt].isupper():
#                 splitted = prescribers[cpt].split(' ')
#                 for data in splitted:
#                     if data.isupper():
#                         lastname = data
#                     else:
#                         firstname += data.capitalize() + ' '
#             else:
#                 splitted = prescribers[cpt].split(' ')
#                 lastname = splitted[0]
#                 firstname = splitted[1] if len(splitted) > 1 else ''
#             return [lastname.strip(), firstname.strip()]
#     return ['', '']


def find_adeli():
    data = FindAdeli(text_with_conf, log, locale, ocr).run()
    if data and len(data) >= 1:
        data = data[0]
    return data


def find_rpps():
    data = FindRPPS(text_with_conf, log, locale, ocr).run()
    if data and len(data) >= 1:
        data = data[0]
    return data


def find_sociale_security_number():
    data = FindNir(text_with_conf, log, locale, ocr).run()
    return data


if __name__ == '__main__':
    # Set up the global settings
    prescription_path = '/home/nathan/Bureau/EXPORT_CBA/ORDOS/'
    data_ordos = '/home/nathan/Bureau/EXPORT_CBA/ordo_in.csv'
    csv_export = 'export.csv'
    log = Log('../bin/log/CBA.log', None)
    ocr = PyTesseract('fra', log, '/var/www/html/opencapture_runtime/')
    locale = Locale('/var/www/html/opencapture_runtime/')
    csv_file = open(csv_export, 'w')
    csv_writer = csv.writer(csv_file, delimiter=';')
    config = Config('/var/www/html/opencapture_runtime/config/modules/ordonnances/config.ini')
    database = Database(log, config.cfg['DATABASE'])
    min_char = config.cfg['GLOBAL']['min_char']
    prescription_time_delta = config.cfg['GLOBAL']['prescription_time_delta']
    date_process = FindDate('', log, locale, prescription_time_delta)
    # Write headers of the CSV
    csv_writer.writerow(['FILE', 'ADELI', 'RPPS', 'PRESCRIPTION_DATE', 'PRESCRIBER_FIRST_NAME',
                         'PRESCRIBER_LAST_NAME', 'PATIENT_BIRTH_DATE', 'PATIENT_SOCIALE_SECURITY',
                         'PATIENT_FIRST_NAME', 'PATIENT_LAST_NAME', 'PROCESS_TIME', 'PRESCRIBER_FIRST_NAME_PERCENTAGE',
                         'PRESCRIBER_LAST_NAME_PERCENTAGE', 'PATIENT_FIRST_NAME_PERCENTAGE', 'PATIENT_LAST_NAME_PERCENTAGE',
                         'ADELI_PERCENTAGE', 'RPPS_PERCENTAGE', 'GLOBAL_PERCENTAGE', 'CABINET_ID'])
    cpt = 1
    number_of_prescription = len(os.listdir(prescription_path))
    for prescription in os.listdir(prescription_path):
        if os.path.splitext(prescription)[1] == '.jpg':  # and prescription == '32 820 065.jpg':
            start = time.time()
            print(prescription)
            # Set up data about the prescription
            file = prescription_path + prescription
            image_content = Image.open(file)
            # text_lines = ocr.line_box_builder(image_content)
            text_with_conf = ocr.image_to_text_with_conf(image_content)
            char_count = 0
            for line in text_with_conf:
                char_count += len(line['text'])

            if int(char_count) < int(min_char):
                continue

            if int(char_count) > int(min_char):
                # Retrieve all the information
                with open(data_ordos, mode='r', encoding="ISO-8859-1") as csv_file:
                    csv_reader = csv.DictReader(csv_file, delimiter=';')
                    for row in csv_reader:
                        if row['id'].replace(' ', '') == os.path.splitext(prescription)[0].replace(' ', ''):
                            cabinet_id = row['cabinet_id']

                prescription_date, birth_date = find_date()
                patients = find_patient(birth_date, text_with_conf, log, locale, ocr, image_content, cabinet_id)
                prescribers = find_prescribers(text_with_conf, log, locale, ocr, database)
                if not patients:
                    patients = [{'id': '', 'firstname': '', 'lastname': '', 'nir': ''}]
                if not prescribers:
                    prescribers = [{'id': '', 'firstname': '', 'lastname': '', 'rpps': '', 'adeli': ''}]
                print(cabinet_id)
                print('patients : ', patients)
                print('prescribers : ', prescribers)
                print(str(cpt) + '/' + str(number_of_prescription), char_count, prescription_date, birth_date, patients[0]['lastname'], patients[0]['firstname'], prescribers[0]['lastname'], prescribers[0]['firstname'], prescribers[0]['adeli'], prescribers[0]['rpps'], patients[0]['nir'])
                with open(data_ordos, mode='r', encoding="ISO-8859-1") as csv_file:
                    csv_reader = csv.DictReader(csv_file, delimiter=';')
                    line_count = 0
                    for row in csv_reader:
                        if line_count != 0:
                            number = 7
                            if row['id'].replace(' ', '') == os.path.splitext(prescription)[0].replace(' ', ''):
                                if not row['date_prescription']:
                                    number -= 1
                                if not row['prenom']:
                                    number -= 1
                                if not row['nom']:
                                    number -= 1
                                if not row['numero_adeli_cle']:
                                    number -= 1
                                if not row['numero_rpps_cle']:
                                    number -= 1
                                if not row['prenom_1']:
                                    number -= 1
                                if not row['nom_1']:
                                    number -= 1

                                date_prescription_percentage = fuzz.ratio(row['date_prescription'], prescription_date)
                                prescriber_firstname_percentage = fuzz.ratio(row['prenom'], prescribers[0]['firstname'])
                                prescriber_lastname_percentage = fuzz.ratio(row['nom'], prescribers[0]['lastname'])
                                adeli_percentage = fuzz.ratio(row['numero_adeli_cle'], prescribers[0]['adeli'])
                                rpps_percentage = fuzz.ratio(row['numero_rpps_cle'], prescribers[0]['rpps'])
                                patient_firstname_percentage = fuzz.ratio(row['prenom_1'], patients[0]['firstname'])
                                patient_lastname_percentage = fuzz.ratio(row['nom_1'], patients[0]['lastname'])
                                cabinet_id = row['cabinet_id']
                                global_percentage = (prescriber_lastname_percentage + prescriber_firstname_percentage + adeli_percentage + rpps_percentage + patient_lastname_percentage + patient_firstname_percentage) / number
                        line_count += 1

                # Get raw text from lines to store them in CSV
                # raw_content = ''
                # for line in text_with_conf:
                #     raw_content += line['text'] + "\n"

                # Write on the CSV file
                end = time.time()
                csv_writer.writerow([file, prescribers[0]['adeli'], prescribers[0]['rpps'], prescription_date, prescribers[0]['lastname'],
                                     prescribers[0]['firstname'], birth_date, patients[0]['nir'], patients[0]['firstname'],
                                     patients[0]['lastname'], timer(start, end), int(prescriber_firstname_percentage), int(prescriber_lastname_percentage),
                                     int(patient_firstname_percentage), int(patient_lastname_percentage), int(adeli_percentage), int(rpps_percentage), int(global_percentage),
                                     cabinet_id])
            cpt = cpt + 1
    csv_file.close()
