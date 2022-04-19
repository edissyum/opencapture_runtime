import json
import redis
import psycopg2.extras
from src.classes.Config import Config


if __name__ == '__main__':
    config = Config('../../../config/modules/ordonnances/config.ini')
    conn = psycopg2.connect(
        "dbname     = " + config.cfg['DATABASE']['postgres_database'] +
        " user      = " + config.cfg['DATABASE']['postgres_user'] +
        " password  = " + config.cfg['DATABASE']['postgres_password'] +
        " host      = " + config.cfg['DATABASE']['postgres_host'] +
        " port      = " + config.cfg['DATABASE']['postgres_port'])

    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute("SELECT DISTINCT(cabinet_id) FROM application.praticien")
    r = redis.StrictRedis(host='localhost', port=6379, db=0)
    list_cabinet = cursor.fetchall()
    for cabinet in list_cabinet:
        cabinet_name = 'prescriber_cabinet_' + str(cabinet['cabinet_id'])
        print(cabinet_name)
        cursor.execute("SELECT id, nom, prenom, numero_adeli_cle, numero_rpps_cle, cabinet_id, 'application.praticien' as source FROM application.praticien WHERE cabinet_id = " + str(cabinet['cabinet_id']))
        list_prescribers = cursor.fetchall()
        r.set(cabinet_name, json.dumps(list_prescribers))
