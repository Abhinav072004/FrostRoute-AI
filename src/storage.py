"""Local demo telemetry and durable local audit events."""
import json
import os
import sqlite3
from functools import lru_cache
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine
from sqlglot import exp
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[1]
MAPPING = {'timestamp': 'Timestamp', 'vehicle_gps_latitude': 'Latitude',
           'vehicle_gps_longitude': 'Longitude', 'iot_temperature': 'Current_Temperature_C',
           'cargo_condition_status': 'Cargo_Condition_Code', 'risk_classification': 'Risk_Classification',
           'delay_probability': 'Delay_Probability', 'port_congestion_level': 'Port_Congestion_Level',
           'route_risk_level': 'Route_Risk_Index'}


@lru_cache(maxsize=1)
def demo_frame():
    frame = pd.read_csv(ROOT / 'data/raw/dynamic_supply_chain_logistics_dataset.csv')
    return frame[list(MAPPING)].rename(columns=MAPPING)


def execute_demo(tree):
    with sqlite3.connect(':memory:') as conn:
        demo_frame().to_sql('telemetry', conn, index=False)
        local = tree.copy()
        for table in local.find_all(exp.Table):
            table.set('db', None)
            table.set('this', exp.to_identifier('telemetry'))
        return pd.read_sql_query(local.sql(dialect='sqlite'), conn).to_dict('records')


@lru_cache(maxsize=1)
def sql_engine():
    password = os.getenv('SQL_AGENT_PASSWORD')
    if not password:
        raise ValueError('SQL_AGENT_PASSWORD is required.')
    url = URL.create('mssql+pyodbc', username=os.getenv('SQL_AGENT_USER', 'USR_FDE_RO'),
                     password=password, host=os.getenv('SQL_SERVER_HOST', 'localhost'),
                     port=int(os.getenv('SQL_SERVER_PORT', '1433')),
                     database=os.getenv('SQL_DATABASE', 'master'),
                     query={'driver': 'ODBC Driver 18 for SQL Server',
                            'Encrypt': os.getenv('SQL_ENCRYPT', 'yes'),
                            'TrustServerCertificate': os.getenv('SQL_TRUST_CERTIFICATE', 'no')})
    return create_engine(url, connect_args={'timeout': 8}, pool_pre_ping=True)


def audit(session, event, payload):
    directory = ROOT / '.runtime'
    directory.mkdir(exist_ok=True)
    with sqlite3.connect(directory / 'audit.sqlite3', timeout=10) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, time TEXT DEFAULT CURRENT_TIMESTAMP, session TEXT, event TEXT, payload TEXT)')
        conn.execute('INSERT INTO events(session,event,payload) VALUES (?,?,?)',
                     (session, event, json.dumps(payload, ensure_ascii=False, default=str)))


def read_audit():
    path = ROOT / '.runtime/audit.sqlite3'
    if not path.exists():
        return pd.DataFrame()
    with sqlite3.connect(path) as conn:
        return pd.read_sql_query('SELECT * FROM events ORDER BY id DESC LIMIT 200', conn)
