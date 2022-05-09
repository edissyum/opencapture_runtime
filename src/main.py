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
from classes.Config import Config
from process.FindNir import FindNir
from process.FindDate import FindDate
from process.FindRPPS import FindRPPS
from classes.Database import Database
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
                                                for _prescriber_name in re.finditer(r"((D|P|J)?O(C|S)TEUR(?!S)|DR\.).*", _patient, flags=re.IGNORECASE):
                                                    _patient = ''
                                        break

                            if _patient:
                                firstname = lastname = ''
                                if not _patient.isupper():
                                    splitted = _patient.split(' ')
                                    for cpt in range(0, len(splitted)):
                                        if re.compile('((MADAME|MADEMOISELLE|MLLE|MME|(M)?ONSIEUR)|NOM\s*:)', flags=re.IGNORECASE).search(splitted[cpt]):
                                            del splitted[cpt]
                                            break
                                    if len(splitted) > 2:
                                        for _cpt in range(0, len(splitted)):
                                            if prenom.lower() in splitted[_cpt].lower():
                                                print(splitted[_cpt])
                                                _patient = splitted[_cpt - 1] + ' '
                                                _patient += splitted[_cpt]
                                                if len(splitted) > _cpt + 1:
                                                    _patient = ' ' + splitted[_cpt + 1]

                                    if not _patient.isupper():
                                        splitted = _patient.split(' ')
                                        for cpt in range(0, len(splitted)):
                                            if re.compile('((MADAME|MADEMOISELLE|MLLE|MME|(M)?ONSIEUR)|NOM\s*:)', flags=re.IGNORECASE).search(splitted[cpt]):
                                                del splitted[cpt]
                                                break

                                        for data in splitted:
                                            if data.isupper():
                                                lastname += data.strip() + ' '
                                            else:
                                                firstname += data.strip().capitalize() + ' '
                                        firstname = firstname.strip()
                                        lastname = lastname.strip()
                                    else:
                                        splitted = _patient.split(' ')
                                        for cpt in range(0, len(splitted)):
                                            if re.compile('((MADAME|MADEMOISELLE|MLLE|MME|(M)?ONSIEUR)|NOM\s*:)', flags=re.IGNORECASE).search(splitted[cpt]):
                                                del splitted[cpt]
                                                break
                                        lastname = splitted[0].strip()
                                        firstname = splitted[1].strip() if len(splitted) > 1 else ''
                                else:
                                    splitted = _patient.split(' ')
                                    for cpt in range(0, len(splitted)):
                                        if re.compile('((MADAME|MADEMOISELLE|MLLE|MME|(M)?ONSIEUR)|NOM\s*:)', flags=re.IGNORECASE).search(splitted[cpt]):
                                            del splitted[cpt]
                                            break
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
                                        if fuzz.ratio(lastname.lower(), _patient['nom'].lower()) >= levenshtein_ratio:
                                            patient_found = True
                                            patients.append(_patient)
                                            break

    if not patient_found:
        if date_birth:
            try:
                date_birth = datetime.strptime(date_birth, '%d/%m/%Y').strftime('%Y%m%d')
            except ValueError:
                date_birth = None

        patients.append({
            'id': None,
            'prenom': firstname.strip(),
            'nom': lastname.strip(),
            'date_naissance': date_birth,
            'nir': nir
        })

    return patients


def find_prescribers(text_with_conf, log, locale, ocr, database, cabinet_id):
    ps_list = []
    prescribers = FindPrescriber(text_with_conf, log, locale, ocr).run()
    rpps_numbers = FindRPPS(text_with_conf, log, locale, ocr).run()
    levenshtein_ratio = '2'

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
                    info[0]['id_prescripteur'] = None
                    ps_list.append(info[0])
                    continue

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
                    info[0]['id_prescripteur'] = None
                    ps_list.append(info[0])
                    continue

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

            if firstname and lastname:
                info = database.select({
                    'select': ['id as id_praticien', 'nom', 'prenom', 'numero_adeli_cle', 'numero_rpps_cle'],
                    'table': ['application.praticien'],
                    'where': ['(LEVENSHTEIN(nom, %s) <= ' + levenshtein_ratio + ' AND LEVENSHTEIN(prenom, %s) <= ' + levenshtein_ratio + ') OR (LEVENSHTEIN(prenom, %s) <= ' + levenshtein_ratio + ' AND LEVENSHTEIN(nom, %s) <= ' + levenshtein_ratio + ')', 'cabinet_id = %s'],
                    'data': [lastname, firstname, lastname, firstname, cabinet_id],
                    'limit': 1
                })
                if info:
                    info[0]['id_prescripteur'] = None
                    ps_list.append(info[0])
                    continue
                else:
                    info = database.select({
                        'select': ['id as id_prescripteur', 'nom', 'prenom', 'numero_idfact_cle as numero_adeli_cle', 'numero_rpps_cle'],
                        'table': ['sesam.prescripteur'],
                        'where': ['(LEVENSHTEIN(nom, %s) <= ' + levenshtein_ratio + ' AND LEVENSHTEIN(prenom, %s) <= ' + levenshtein_ratio + ') OR (LEVENSHTEIN(prenom, %s) <= ' + levenshtein_ratio + ' AND LEVENSHTEIN(nom, %s) <= ' + levenshtein_ratio + ')'],
                        'data': [lastname, firstname, lastname, firstname],
                        'limit': 1
                    })
                    if info:
                        info[0]['id_praticien'] = None
                        ps_list.append(info[0])
                        continue
            ps_list.append({
                'id_praticien': '',
                'id_prescripteur': '',
                'prenom': firstname.strip(),
                'nom': lastname.strip(),
                'numero_adeli_cle': adeli_numbers[cpt] if adeli_numbers and cpt == len(adeli_numbers) - 1 else None,
                'numero_rpps_cle': rpps_numbers[cpt] if rpps_numbers and cpt == len(rpps_numbers) - 1 else None
            })
            continue
    else:
        prescriber_found = False
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
                    info[0]['id_prescripteur'] = None
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
                        info[0]['id_prescripteur'] = None
                        ps_list.append(info[0])
    return ps_list


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


if __name__ == '__main__':
    # Set up the global settings
    path = '/var/www/html/opencapture_runtime/'
    prescription_path = '/home/nathan/Bureau/EXPORT_CBA/ORDOS/'
    data_ordos = '/home/nathan/Bureau/EXPORT_CBA/ordo_in_v2.csv'
    csv_export = 'export.csv'
    log = Log(path + '/bin/log/CBA.log', None)
    ocr = PyTesseract('fra', log, path)
    locale = Locale(path)
    csv_file = open(csv_export, 'w')
    csv_writer = csv.writer(csv_file, delimiter=';')
    config = Config(path + '/config/modules/ordonnances/config.ini')
    database = Database(log, config.cfg['DATABASE'])
    prescription_time_delta = config.cfg['GLOBAL']['prescription_time_delta']
    date_process = FindDate('', log, locale, prescription_time_delta)
    # Write headers of the CSV
    csv_writer.writerow(['FILE', 'ADELI', 'RPPS', 'PRESCRIPTION_DATE', 'PRESCRIBER_FIRST_NAME',
                         'PRESCRIBER_LAST_NAME', 'PATIENT_BIRTH_DATE', 'PATIENT_SOCIALE_SECURITY',
                         'PATIENT_FIRST_NAME', 'PATIENT_LAST_NAME', 'PROCESS_TIME', 'PRESCRIBER_FIRST_NAME_PERCENTAGE',
                         'PRESCRIBER_LAST_NAME_PERCENTAGE', 'PATIENT_FIRST_NAME_PERCENTAGE', 'PATIENT_LAST_NAME_PERCENTAGE',
                         'ADELI_PERCENTAGE', 'RPPS_PERCENTAGE', 'DATE_PERCENTAGE', 'GLOBAL_PERCENTAGE', 'CABINET_ID', 'ID_PRESCRIBER', 'ID_PATIENT'])
    cpt = 1
    number_of_prescription = len(os.listdir(prescription_path))
    for prescription in os.listdir(prescription_path):
        if os.path.splitext(prescription)[1] == '.jpg':  # and prescription == '39 086 635.jpg':
            start = time.time()
            # Set up data about the prescription
            file = prescription_path + prescription
            image_content = Image.open(file)
            text_with_conf, char_count = ocr.image_to_text_with_conf(image_content)

            print(str(cpt) + '/' + str(number_of_prescription), prescription, 'char_count :', char_count)

            # Retrieve all the information
            with open(data_ordos, mode='r', encoding="ISO-8859-1") as csv_file:
                csv_reader = csv.DictReader(csv_file, delimiter=';')
                for row in csv_reader:
                    if row['id'].replace(' ', '') == os.path.splitext(prescription)[0].replace(' ', ''):
                        cabinet_id = row['cabinet_id']

            prescription_date, birth_date = find_date()
            prescribers = find_prescribers(text_with_conf, log, locale, ocr, database, cabinet_id)
            patients = find_patient(birth_date, text_with_conf, log, locale, ocr, image_content, cabinet_id, prescribers)
            if not patients:
                patients = [{'id': '', 'prenom': '', 'nom': '', 'nir': ''}]
            if not prescribers:
                prescribers = [{'id_praticien': '', 'id_prescripteur': '', 'prenom': '', 'nom': '', 'numero_rpps_cle': '', 'numero_adeli_cle': ''}]

            print('patients : ', patients)
            print('prescribers : ', prescribers)
            end = time.time()
            print(timer(start, end))
            with open(data_ordos, mode='r', encoding="ISO-8859-1") as csv_file:
                csv_reader = csv.DictReader(csv_file, delimiter=';')
                line_count = 0
                for row in csv_reader:
                    if line_count != 0:
                        number = 7
                        if row['id'].replace(' ', '') == os.path.splitext(prescription)[0].replace(' ', ''):
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
                            prescriber_firstname_percentage = 100 if prescribers[0]['id_prescripteur'] or prescribers[0]['id_praticien'] else fuzz.ratio(row['prenom'], prescribers[0]['prenom'])
                            prescriber_lastname_percentage = 100 if prescribers[0]['id_prescripteur'] or prescribers[0]['id_praticien'] else fuzz.ratio(row['nom'], prescribers[0]['nom'])
                            adeli_percentage = 100 if prescribers[0]['id_prescripteur'] or prescribers[0]['id_praticien'] else fuzz.ratio(row['numero_adeli_cle'], prescribers[0]['numero_adeli_cle'])
                            rpps_percentage = 100 if prescribers[0]['id_prescripteur'] or prescribers[0]['id_praticien'] else fuzz.ratio(row['numero_rpps_cle'], prescribers[0]['numero_rpps_cle'])
                            patient_firstname_percentage = 100 if patients[0]['id'] else fuzz.ratio(row['prenom_1'], patients[0]['prenom'])
                            patient_lastname_percentage = 100 if patients[0]['id'] else fuzz.ratio(row['nom_1'], patients[0]['nom'])
                            cabinet_id = row['cabinet_id']
                            global_percentage = (prescriber_lastname_percentage + prescriber_firstname_percentage + adeli_percentage + rpps_percentage + patient_lastname_percentage + patient_firstname_percentage) / number
                    line_count += 1

            # Get raw text from lines to store them in CSV
            # raw_content = ''
            # for line in text_with_conf:
            #     raw_content += line['text'] + "\n"

            # Write on the CSV file
            id_prescriber = prescribers[0]['id_prescripteur'] if prescribers[0]['id_prescripteur'] else (prescribers[0]['id_praticien'] if prescribers[0]['id_praticien'] else '')
            id_patient = patients[0]['id'] if patients[0]['id'] else ''
            csv_writer.writerow([file, prescribers[0]['numero_adeli_cle'], prescribers[0]['numero_rpps_cle'], prescription_date, prescribers[0]['prenom'],
                                 prescribers[0]['nom'], birth_date, patients[0]['nir'], patients[0]['prenom'],
                                 patients[0]['nom'], timer(start, end), int(prescriber_firstname_percentage), int(prescriber_lastname_percentage),
                                 int(patient_firstname_percentage), int(patient_lastname_percentage), int(adeli_percentage), int(rpps_percentage), int(date_prescription_percentage), int(global_percentage),
                                 cabinet_id, id_prescriber, id_patient])
            cpt = cpt + 1
    csv_file.close()
