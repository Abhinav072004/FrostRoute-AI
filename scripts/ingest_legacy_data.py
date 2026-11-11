"""Explicitly load the bundled sample into SQL Server; refuses overwrite by default."""
import argparse
import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
MAPPING = {'timestamp': 'TS_UTC', 'vehicle_gps_latitude': 'V_LAT',
           'vehicle_gps_longitude': 'V_LON', 'iot_temperature': 'IOT_TEMP_VAL_C',
           'cargo_condition_status': 'CGO_COND_CD', 'risk_classification': 'RISK_CLS_TXT',
           'delay_probability': 'DELAY_PROB_DEC', 'port_congestion_level': 'PRT_CNG_LVL',
           'route_risk_level': 'RT_RSK_IDX'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--replace', action='store_true', help='Explicitly replace the existing sample table')
    args = parser.parse_args()
    load_dotenv(ROOT / '.env')
    if not os.getenv('SQL_ADMIN_USER') or not os.getenv('SQL_ADMIN_PASSWORD'):
        raise ValueError('Provision an ingestion account and set SQL_ADMIN_USER / SQL_ADMIN_PASSWORD.')
    url = URL.create('mssql+pyodbc', username=os.environ['SQL_ADMIN_USER'],
                     password=os.environ['SQL_ADMIN_PASSWORD'],
                     host=os.getenv('SQL_SERVER_HOST', 'localhost'),
                     port=int(os.getenv('SQL_SERVER_PORT', '1433')),
                     database=os.getenv('SQL_DATABASE', 'master'),
                     query={'driver': 'ODBC Driver 18 for SQL Server',
                            'Encrypt': os.getenv('SQL_ENCRYPT', 'yes'),
                            'TrustServerCertificate': os.getenv('SQL_TRUST_CERTIFICATE', 'no')})
    engine = create_engine(url, connect_args={'timeout': 10})
    frame = pd.read_csv(ROOT / 'data/raw/dynamic_supply_chain_logistics_dataset.csv')
    legacy = frame[list(MAPPING)].rename(columns=MAPPING)
    try:
        with engine.begin() as conn:
            legacy.to_sql('TBL_SC_FLEET_HIST_RAW', conn, schema='dbo', index=False,
                          if_exists='replace' if args.replace else 'fail', chunksize=200)
    finally:
        engine.dispose()
    print(f'Imported {len(legacy)} historical observations. These are not active shipments.')


if __name__ == '__main__':
    main()
