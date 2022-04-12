import json
import redis
import psycopg2.extras
from src.classes.Config import Config


if __name__ == '__main__':
    config = Config('../../../config/modules/ordonnances/config.ini')
    conn = psycopg2.connect(
        "dbname     = " + config.cfg['DATABASE']['postgresdatabase'] +
        " user      = " + config.cfg['DATABASE']['postgresuser'] +
        " password  = " + config.cfg['DATABASE']['postgrespassword'] +
        " host      = " + config.cfg['DATABASE']['postgreshost'] +
        " port      = " + config.cfg['DATABASE']['postgresport'])

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT DISTINCT(cabinet_id) FROM application.patient")
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    list_cabinet = cursor.fetchall()
    for cabinet in list_cabinet:
        cabinet_name = 'patient_cabinet_' + str(cabinet['cabinet_id'])
        cursor.execute("SELECT id, nom, prenom, nir, date_naissance FROM application.patient WHERE cabinet_id = " + str(cabinet['cabinet_id']))
        list_patients = cursor.fetchall()
        r.set(cabinet_name, json.dumps(list_patients))
