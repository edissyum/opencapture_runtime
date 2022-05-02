import csv
import json
import redis

def timer(start_time, end_time):
    hours, rem = divmod(end_time - start_time, 3600)
    minutes, seconds = divmod(rem, 60)
    return "{:0>2}:{:0>2}:{:05.2f}".format(int(hours), int(minutes), seconds)


if __name__ == '__main__':
    file = '/home/nathan/Bureau/EXPORT_CBA/LISTE_PRENOMS.csv'
    names = []
    with open(file, 'r') as csv_file:
        for row in csv.reader(csv_file, delimiter=';'):
            if row[1].lower() not in names and len(row[1]) >= 5 and row[1].lower() not in ['paris', 'juste', 'avril', 'lucho', 'donna', 'nance']:
                names.append(row[1].lower())

    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    r.set('names', json.dumps(names))
