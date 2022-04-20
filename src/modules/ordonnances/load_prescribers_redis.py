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
    r.execute_command('config set proto-max-bulk-len 2147483648')
    list_cabinet = cursor.fetchall()
    prescribers = []
    for cabinet in list_cabinet:
        cabinet_name = 'prescriber_cabinet_' + str(cabinet['cabinet_id'])
        print(cabinet_name)
        cursor.execute("SELECT id, nom, prenom, numero_adeli_cle, numero_rpps_cle, cabinet_id, 'application.praticien' as source FROM application.praticien WHERE cabinet_id = " + str(cabinet['cabinet_id']))
        list_prescribers = cursor.fetchall()
        for _prescriber in list_prescribers:
            r.append('prescribers', json.dumps(_prescriber))
            # prescribers.append(_prescriber)

    cursor.execute("SELECT nom, prenom, numero_idfact_cle as numero_adeli_cle, numero_rpps_cle, 'sesam.prescripteur' as source FROM sesam.prescripteur")
    list_prescripteur_sesam = cursor.fetchall()
    for _prescriber in list_prescripteur_sesam:
        r.append('prescribers', json.dumps(_prescriber))
        # prescribers.append(_prescriber)

    # r.set('prescribers', json.dumps(prescribers))

    # for t in prescribers:
    #     if t['numero_rpps_cle'] == '10100232288':
    #         print(t)
        # r.set(cabinet_name, json.dumps(list_prescribers))
