"""
Gestión de conexiones a las bases de datos de cada sucursal
"""
import logging
from typing import Dict, Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from ..config import DATABASE_CONFIGS, CONNECTION_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Gestor de conexiones a múltiples bases de datos (una por sucursal)
    
    Cada sucursal tiene su propia base de datos PostgreSQL.
    Este gestor mantiene pools de conexiones para acceso eficiente.
    """
    
    def __init__(self):
        self.engines: Dict[str, any] = {}
        self.session_makers: Dict[str, sessionmaker] = {}
        self._initialize_connections()
    
    def _initialize_connections(self):
        """Inicializa las conexiones a todas las bases de datos configuradas"""
        for instance_id, config in DATABASE_CONFIGS.items():
            try:
                # Crear engine con pool de conexiones
                engine = create_engine(
                    config['url'],
                    poolclass=QueuePool,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,  # Verifica conexiones antes de usarlas
                    pool_recycle=3600,   # Recicla conexiones cada hora
                    connect_args={'connect_timeout': CONNECTION_TIMEOUT_SECONDS}
                )
                
                self.engines[instance_id] = engine
                self.session_makers[instance_id] = sessionmaker(bind=engine)
                
                logger.info(f"✓ Conexión establecida con {instance_id} ({config['name']})")
                
            except Exception as e:
                logger.error(f"✗ Error conectando a {instance_id}: {e}")
                raise
    
    def get_session(self, instance_id: str) -> Session:
        """
        Obtiene una sesión de SQLAlchemy para una instancia específica
        
        Args:
            instance_id: ID de la sucursal (ej: 'SUC001')
            
        Returns:
            Session de SQLAlchemy
        """
        if instance_id not in self.session_makers:
            raise ValueError(f"Instancia no configurada: {instance_id}")
        
        return self.session_makers[instance_id]()
    
    def check_connectivity(self, instance_id: str) -> bool:
        """
        Verifica si hay conectividad con una instancia
        
        Args:
            instance_id: ID de la sucursal
            
        Returns:
            True si hay conexión, False en caso contrario
        """
        try:
            engine = self.engines.get(instance_id)
            if not engine:
                return False
            
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            return True
            
        except Exception as e:
            logger.debug(f"Sin conectividad con {instance_id}: {e}")
            return False
    
    def close_all(self):
        """Cierra todas las conexiones"""
        for instance_id, engine in self.engines.items():
            engine.dispose()
            logger.info(f"✓ Conexión cerrada con {instance_id}")
