"""
Modelo de Stock distribuido por sucursal
Cada sucursal mantiene su propio stock
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, CheckConstraint
from .base import Base

class StockBySite(Base):
    """
    Stock por Sucursal - Cada sucursal tiene su propio inventario
    
    Estrategia: Stock separado por instancia
    - Cada sucursal solo modifica su propio stock
    - Con sincronización activa, se puede consultar stock remoto (read-only)
    - Sin sincronización, solo se puede vender del stock local
    """
    __tablename__ = 'stock_by_site'
    
    product_id = Column(Integer, primary_key=True)
    instance_id = Column(String(20), primary_key=True)
    quantity = Column(Integer, default=0, nullable=False)
    reserved = Column(Integer, default=0, nullable=False)  # Para ventas pendientes de entrega
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    sync_version = Column(Integer, default=1, nullable=False)
    
    __table_args__ = (
        CheckConstraint('quantity >= 0', name='check_positive_stock'),
        CheckConstraint('reserved >= 0', name='check_positive_reserved'),
    )
    
    @property
    def available(self):
        """Stock disponible para venta (total - reservado)"""
        return self.quantity - self.reserved
    
    def __repr__(self):
        return f"<StockBySite(product={self.product_id}, instance={self.instance_id}, qty={self.quantity}, reserved={self.reserved})>"