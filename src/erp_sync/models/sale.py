"""
Modelos de Venta con clave compuesta
Cada sucursal genera sus propias ventas sin conflictos
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base

class Sale(Base):
    """
    Venta - Utiliza clave compuesta (instance_id + local_id)
    
    Cada sucursal genera sus propias ventas con IDs locales.
    La combinación instance_id + local_id garantiza unicidad global.
    Permite sincronización bidireccional sin conflictos.
    """
    __tablename__ = 'sales'
    
    instance_id = Column(String(20), primary_key=True)
    local_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, nullable=False)
    total = Column(Numeric(10, 2), nullable=False)
    sale_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    delivery_instance = Column(String(20))  # Sucursal donde retira el cliente
    synced = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relación con items de venta
    items = relationship("SaleItem", back_populates="sale", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Sale(instance={self.instance_id}, id={self.local_id}, total={self.total})>"


class SaleItem(Base):
    """
    Item de Venta - Líneas de detalle de cada venta
    
    También utiliza clave compuesta extendida con line_number
    """
    __tablename__ = 'sale_items'
    
    instance_id = Column(String(20), primary_key=True)
    sale_id = Column(Integer, primary_key=True)
    line_number = Column(Integer, primary_key=True)
    product_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    
    # Relación con venta
    sale = relationship("Sale", back_populates="items")
    
    def __repr__(self):
        return f"<SaleItem(sale={self.instance_id}-{self.sale_id}, line={self.line_number}, product={self.product_id})>"