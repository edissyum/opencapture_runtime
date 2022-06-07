import csv
import json
import redis

def timer(start_time, end_time):
    hours, rem = divmod(end_time - start_time, 3600)
    minutes, seconds = divmod(rem, 60)
    return "{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds)


if __name__ == '__main__':
    file = '/var/www/html/opencapture_runtime/src/modules/ordonnances/LISTE_PRENOMS.csv'
    names = []
    exclusions = ['paris', 'juste', 'avril', 'lucho', 'donna', 'nance', 'patient', 'georg', 'iness',
                  'issem', 'melan', 'aires', 'matine', 'erman', 'lance', 'amedi', 'hande', 'samed',
                  'randa', 'honora', 'honor', 'anique', 'ellie', 'adame', 'adam', 'ansam', 'amina',
                  'minas', 'levin']
    add = ['ANNAIK']

    for _a in add:
        names.append(_a.lower())

    with open(file, 'r') as csv_file:
        for row in csv.reader(csv_file, delimiter=';'):
            if row[1].lower() not in names and len(row[1]) >= 5 and row[1].lower() not in exclusions:
                names.append(row[1].lower())

    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    r.set('names', json.dumps(names))
