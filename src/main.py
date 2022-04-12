##########################
#   POC EDISSYUM - CBA   #
#      Décembre 2021     #
#      Nathan CHEVAL     #
##########################

import os
import re
import csv
import time
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
    dateProcess.prescriptionDate = None
    dateProcess.timeDelta = prescription_time_delta
    log.info("Traitement de l'ordonnance " + prescription)
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


def find_patient(date_birth):
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


def find_prescriber(text_with_conf, log, locale, ocr):
    prescribers = FindPrescriber(text_with_conf, log, locale, ocr).run()
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
            return [lastname.strip(), firstname.strip()]
    return ['', '']


def find_adeli():
    data = FindAdeli(text_with_conf, log, locale, ocr).run()
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
    min_char_num = 280
    prescription_path = '/home/nathan/Bureau/ordo30k/'
    data_ordos = '/home/nathan/Bureau/dataordo30k-avec-cabinetid.csv'
    csv_export = 'export.csv'
    log = Log('../bin/log/CBA.log', None)
    ocr = PyTesseract('fra', log, '/var/www/html/opencapture_runtime/')
    locale = Locale('/var/www/html/opencapture_runtime/')
    prescription_time_delta = 2190  # 6 ans max pour les dates d'ordonnance
    dateProcess = FindDate('', log, locale, prescription_time_delta)
    csv_file = open(csv_export, 'w')
    csv_writer = csv.writer(csv_file, delimiter=';')

    # Write headers of the CSV
    csv_writer.writerow(['FILE', 'ADELI', 'RPPS', 'PRESCRIPTION_DATE', 'PRESCRIBER_FIRST_NAME',
                         'PRESCRIBER_LAST_NAME', 'PATIENT_BIRTH_DATE', 'PATIENT_SOCIALE_SECURITY',
                         'PATIENT_FIRST_NAME', 'PATIENT_LAST_NAME', 'PROCESS_TIME', 'PRESCRIBER_FIRST_NAME_PERCENTAGE',
                         'PRESCRIBER_LAST_NAME_PERCENTAGE', 'PATIENT_FIRST_NAME_PERCENTAGE', 'PATIENT_LAST_NAME_PERCENTAGE',
                         'ADELI_PERCENTAGE', 'RPPS_PERCENTAGE', 'GLOBAL_PERCENTAGE', 'CABINET_ID', 'RAW_CONTENT'])
    cpt = 1
    number_of_prescription = len(os.listdir(prescription_path))
    for prescription in os.listdir(prescription_path):
        if os.path.splitext(prescription)[1] == '.jpg':  # and prescription == '39 066 476.jpg':
            if cpt >= 23208:
                start = time.time()
                # Set up data about the prescription
                file = prescription_path + prescription
                image_content = Image.open(file)
                # text_lines = ocr.line_box_builder(image_content)
                text_with_conf = ocr.image_to_text_with_conf(image_content)
                char_count = 0
                for line in text_with_conf:
                    char_count += len(line['text'])

                if char_count > min_char_num:
                    cpt = cpt + 1
                else:
                    continue
                if char_count > min_char_num:
                    # Retrieve all the information
                    prescription_date, birth_date = find_date()
                    patient_lastname, patient_firstname = find_patient(birth_date)
                    prescriber_lastname, prescriber_firstname = find_prescriber(text_with_conf, log, locale, ocr)
                    adeli_number = find_adeli()
                    rpps_number = find_rpps()
                    sociale_security_number = find_sociale_security_number()

                    # Check the number of informations not found. if >= 7, do not write it on CSV
                    number_of_empty = 0
                    for t in [prescription_date, birth_date, patient_lastname, patient_firstname, prescriber_lastname, prescriber_firstname, adeli_number, rpps_number]:
                        if not t:
                            number_of_empty += 1
                    if number_of_empty < 7:
                        print(str(cpt) + '/' + str(number_of_prescription), char_count, prescription_date, birth_date, patient_lastname, patient_firstname, prescriber_lastname, prescriber_firstname, adeli_number, rpps_number, sociale_security_number)
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
                                        prescriber_firstname_percentage = fuzz.ratio(row['prenom'], prescriber_firstname)
                                        prescriber_lastname_percentage = fuzz.ratio(row['nom'], prescriber_lastname)
                                        adeli_percentage = fuzz.ratio(row['numero_adeli_cle'], adeli_number)
                                        rpps_percentage = fuzz.ratio(row['numero_rpps_cle'], rpps_number)
                                        patient_firstname_percentage = fuzz.ratio(row['prenom_1'], patient_firstname)
                                        patient_lastname_percentage = fuzz.ratio(row['nom_1'], patient_lastname)
                                        cabinet_id = row['cabinet_id']
                                        global_percentage = (prescriber_lastname_percentage + prescriber_firstname_percentage + adeli_percentage + rpps_percentage + patient_lastname_percentage + patient_firstname_percentage) / number
                                line_count += 1

                        # Get raw text from lines to store them in CSV
                        raw_content = ''
                        for line in text_with_conf:
                            raw_content += line['text'] + "\n"

                        # Write on the CSV file
                        end = time.time()
                        csv_writer.writerow([file, adeli_number, rpps_number, prescription_date, prescriber_lastname,
                                             prescriber_firstname, birth_date, sociale_security_number, patient_firstname,
                                             patient_lastname, timer(start, end), int(prescriber_firstname_percentage), int(prescriber_lastname_percentage),
                                             int(patient_firstname_percentage), int(patient_lastname_percentage), int(adeli_percentage), int(rpps_percentage), int(global_percentage),
                                             cabinet_id, raw_content])
            cpt = cpt + 1
    csv_file.close()
