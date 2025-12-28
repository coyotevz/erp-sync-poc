"""
Modelo de Producto - Tabla Maestra
Solo modificable desde la instancia maestra (SUC001)
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Numeric, DateTime, CheckConstraint
from .base import Base

class Product(Base):
    """
    Producto - Tabla maestra que solo se actualiza desde casa central
    
    Esta tabla utiliza la estrategia Master-Only para evitar conflictos.
    Solo la instancia maestra (SUC001) puede crear o modificar productos.
    Las demás sucursales reciben los cambios mediante sincronización unidireccional.
    """
    __tablename__ = 'products'
    
    id = Column(Integer, primary_key=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    price = Column(Numeric(10, 2), nullable=False)
    master_instance = Column(String(20), default='SUC001', nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    sync_version = Column(Integer, default=1, nullable=False)
    
    __table_args__ = (
        CheckConstraint('price >= 0', name='check_positive_price'),
    )
    
    def __repr__(self):
        return f"<Product(id={self.id}, code='{self.code}', name='{self.name}', price={self.price})>"
