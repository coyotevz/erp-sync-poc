"""
Configuración del sistema ERP multi-sucursal
"""
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_CONFIGS = {
    'SUC001': {
        'url': os.getenv('DB_SUC001', 'postgresql://erp_user:erp_pass@localhost:5432/erp_suc001'),
        'instance_id': 'SUC001',
        'is_master': True,
        'name': 'Casa Central'
    },
    'SUC002': {
        'url': os.getenv('DB_SUC002', 'postgresql://erp_user:erp_pass@localhost:5433/erp_suc002'),
        'instance_id': 'SUC002',
        'is_master': False,
        'name': 'Sucursal Shopping'
    },
    'SUC003': {
        'url': os.getenv('DB_SUC003', 'postgresql://erp_user:erp_pass@localhost:5434/erp_suc003'),
        'instance_id': 'SUC003',
        'is_master': False,
        'name': 'Sucursal Centro'
    }
}

SYNC_INTERVAL_SECONDS = int(os.getenv('SYNC_INTERVAL', '5'))
CONNECTION_TIMEOUT_SECONDS = int(os.getenv('CONNECTION_TIMEOUT', '3'))
