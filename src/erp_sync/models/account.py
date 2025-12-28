"""
Modelos de Cuenta Corriente
Movimientos inmutables con detección de duplicados
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Boolean
from .base import Base

class Customer(Base):
    """
    Cliente - Tabla maestra
    
    Solo se modifica desde la instancia maestra (SUC001).
    Las demás sucursales reciben los cambios por sincronización.
    """
    __tablename__ = 'customers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    email = Column(String(100))
    phone = Column(String(50))
    master_instance = Column(String(20), default='SUC001', nullable=False)
    sync_version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<Customer(id={self.id}, name='{self.name}')>"


class AccountMovement(Base):
    """
    Movimiento de Cuenta Corriente - Log inmutable
    
    Estrategia: Movimientos inmutables con clave compuesta
    - Cada pago/compra es un registro independiente
    - El saldo se calcula, no se almacena
    - Sistema de detección de pagos duplicados para intervención manual
    """
    __tablename__ = 'account_movements'
    
    instance_id = Column(String(20), primary_key=True)
    local_id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, nullable=False, index=True)
    movement_type = Column(String(20), nullable=False)  # 'SALE', 'PAYMENT', 'ADJUSTMENT'
    amount = Column(Numeric(10, 2), nullable=False)  # Positivo = debe, Negativo = pago
    reference_doc = Column(String(100))  # Referencia a venta o recibo
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    synced = Column(Boolean, default=False, nullable=False)
    conflict_flag = Column(Boolean, default=False, nullable=False)  # Marca duplicados para revisión
    
    def __repr__(self):
        return f"<AccountMovement(instance={self.instance_id}, id={self.local_id}, customer={self.customer_id}, type={self.movement_type}, amount={self.amount})>"