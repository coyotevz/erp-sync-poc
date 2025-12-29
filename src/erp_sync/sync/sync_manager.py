"""
Gestor de Sincronización Peer-to-Peer entre sucursales
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List
from sqlalchemy.orm import Session

from ..database.connection import DatabaseManager
from ..models import Product, Sale, SaleItem, StockBySite, Customer, AccountMovement
from ..config import DATABASE_CONFIGS, SYNC_INTERVAL_SECONDS

logger = logging.getLogger(__name__)


class SyncManager:
    """
    Gestor de sincronización asíncrona entre instancias
    
    Implementa sincronización bidireccional peer-to-peer
    """
    
    def __init__(self, local_instance_id: str, db_manager: DatabaseManager):
        self.local_instance_id = local_instance_id
        self.db_manager = db_manager
        self.remote_instances = [inst for inst in DATABASE_CONFIGS.keys() if inst != local_instance_id]
        self.connectivity_status: Dict[str, bool] = {}
        self._last_sync: Dict[str, datetime] = {}
        self._running = False
        
        logger.info(f"SyncManager inicializado para {local_instance_id}")
    
    async def check_connectivity(self) -> Dict[str, bool]:
        """Verifica conectividad con todas las instancias remotas"""
        status = {}
        
        for instance_id in self.remote_instances:
            is_connected = self.db_manager.check_connectivity(instance_id)
            status[instance_id] = is_connected
            
            previous_status = self.connectivity_status.get(instance_id)
            if previous_status is not None and previous_status != is_connected:
                if is_connected:
                    logger.info(f"✓ Reconectado con {instance_id}")
                else:
                    logger.warning(f"✗ Perdida conexión con {instance_id}")
        
        self.connectivity_status = status
        return status
    
    async def pull_changes(self, remote_instance_id: str) -> int:
        """Trae cambios desde una instancia remota"""
        if not self.connectivity_status.get(remote_instance_id, False):
            return 0
        
        local_session = self.db_manager.get_session(self.local_instance_id)
        remote_session = self.db_manager.get_session(remote_instance_id)
        
        total_synced = 0
        
        try:
            if DATABASE_CONFIGS[remote_instance_id]['is_master']:
                synced = self._sync_products(local_session, remote_session)
                total_synced += synced
                
                synced = self._sync_customers(local_session, remote_session)
                total_synced += synced
            
            synced = self._sync_sales(local_session, remote_session, remote_instance_id)
            total_synced += synced
            
            synced = self._sync_stock(local_session, remote_session, remote_instance_id)
            total_synced += synced
            
            synced = self._sync_account_movements(local_session, remote_session, remote_instance_id)
            total_synced += synced
            
            local_session.commit()
            
            if total_synced > 0:
                logger.info(f"← Pull de {remote_instance_id}: {total_synced} registros")
            
            self._last_sync[remote_instance_id] = datetime.utcnow()
            
        except Exception as e:
            local_session.rollback()
            logger.error(f"Error en pull desde {remote_instance_id}: {e}")
            raise
        finally:
            local_session.close()
            remote_session.close()
        
        return total_synced
    
    def _sync_products(self, local_session: Session, remote_session: Session) -> int:
        """Sincroniza productos desde instancia maestra"""
        remote_products = remote_session.query(Product).all()
        synced = 0
        
        for remote_prod in remote_products:
            local_prod = local_session.query(Product).filter_by(id=remote_prod.id).first()
            
            if not local_prod:
                new_prod = Product(
                    id=remote_prod.id,
                    code=remote_prod.code,
                    name=remote_prod.name,
                    description=remote_prod.description,
                    price=remote_prod.price,
                    master_instance=remote_prod.master_instance,
                    updated_at=remote_prod.updated_at,
                    sync_version=remote_prod.sync_version
                )
                local_session.add(new_prod)
                synced += 1
            elif remote_prod.sync_version > local_prod.sync_version:
                local_prod.code = remote_prod.code
                local_prod.name = remote_prod.name
                local_prod.description = remote_prod.description
                local_prod.price = remote_prod.price
                local_prod.updated_at = remote_prod.updated_at
                local_prod.sync_version = remote_prod.sync_version
                synced += 1
        
        return synced
    
    def _sync_customers(self, local_session: Session, remote_session: Session) -> int:
        """Sincroniza clientes desde instancia maestra"""
        remote_customers = remote_session.query(Customer).all()
        synced = 0
        
        for remote_cust in remote_customers:
            local_cust = local_session.query(Customer).filter_by(id=remote_cust.id).first()
            
            if not local_cust:
                new_cust = Customer(
                    id=remote_cust.id,
                    name=remote_cust.name,
                    email=remote_cust.email,
                    phone=remote_cust.phone,
                    master_instance=remote_cust.master_instance,
                    sync_version=remote_cust.sync_version,
                    created_at=remote_cust.created_at,
                    updated_at=remote_cust.updated_at
                )
                local_session.add(new_cust)
                synced += 1
            elif remote_cust.sync_version > local_cust.sync_version:
                local_cust.name = remote_cust.name
                local_cust.email = remote_cust.email
                local_cust.phone = remote_cust.phone
                local_cust.updated_at = remote_cust.updated_at
                local_cust.sync_version = remote_cust.sync_version
                synced += 1
        
        return synced
    
    def _sync_sales(self, local_session: Session, remote_session: Session, remote_instance_id: str) -> int:
        """Sincroniza ventas usando clave compuesta"""
        remote_sales = remote_session.query(Sale).filter(
            Sale.instance_id == remote_instance_id
        ).all()
        
        synced = 0
        
        for remote_sale in remote_sales:
            local_sale = local_session.query(Sale).filter_by(
                instance_id=remote_sale.instance_id,
                local_id=remote_sale.local_id
            ).first()
            
            if not local_sale:
                new_sale = Sale(
                    instance_id=remote_sale.instance_id,
                    local_id=remote_sale.local_id,
                    customer_id=remote_sale.customer_id,
                    total=remote_sale.total,
                    sale_date=remote_sale.sale_date,
                    delivery_instance=remote_sale.delivery_instance,
                    synced=True,
                    created_at=remote_sale.created_at
                )
                local_session.add(new_sale)
                
                remote_items = remote_session.query(SaleItem).filter_by(
                    instance_id=remote_sale.instance_id,
                    sale_id=remote_sale.local_id
                ).all()
                
                for remote_item in remote_items:
                    new_item = SaleItem(
                        instance_id=remote_item.instance_id,
                        sale_id=remote_item.sale_id,
                        line_number=remote_item.line_number,
                        product_id=remote_item.product_id,
                        quantity=remote_item.quantity,
                        unit_price=remote_item.unit_price,
                        subtotal=remote_item.subtotal
                    )
                    local_session.add(new_item)
                
                synced += 1
        
        return synced
    
    def _sync_stock(self, local_session: Session, remote_session: Session, remote_instance_id: str) -> int:
        """Sincroniza stock de la instancia remota"""
        remote_stock = remote_session.query(StockBySite).filter_by(
            instance_id=remote_instance_id
        ).all()
        
        synced = 0
        
        for remote_st in remote_stock:
            local_st = local_session.query(StockBySite).filter_by(
                product_id=remote_st.product_id,
                instance_id=remote_st.instance_id
            ).first()
            
            if not local_st:
                new_st = StockBySite(
                    product_id=remote_st.product_id,
                    instance_id=remote_st.instance_id,
                    quantity=remote_st.quantity,
                    reserved=remote_st.reserved,
                    updated_at=remote_st.updated_at,
                    sync_version=remote_st.sync_version
                )
                local_session.add(new_st)
                synced += 1
            elif remote_st.sync_version > local_st.sync_version:
                local_st.quantity = remote_st.quantity
                local_st.reserved = remote_st.reserved
                local_st.updated_at = remote_st.updated_at
                local_st.sync_version = remote_st.sync_version
                synced += 1
        
        return synced
    
    def _sync_account_movements(self, local_session: Session, remote_session: Session, remote_instance_id: str) -> int:
        """Sincroniza movimientos de cuenta corriente"""
        remote_movements = remote_session.query(AccountMovement).filter(
            AccountMovement.instance_id == remote_instance_id
        ).all()
        
        synced = 0
        
        for remote_mov in remote_movements:
            local_mov = local_session.query(AccountMovement).filter_by(
                instance_id=remote_mov.instance_id,
                local_id=remote_mov.local_id
            ).first()
            
            if not local_mov:
                new_mov = AccountMovement(
                    instance_id=remote_mov.instance_id,
                    local_id=remote_mov.local_id,
                    customer_id=remote_mov.customer_id,
                    movement_type=remote_mov.movement_type,
                    amount=remote_mov.amount,
                    reference_doc=remote_mov.reference_doc,
                    created_at=remote_mov.created_at,
                    synced=True,
                    conflict_flag=remote_mov.conflict_flag
                )
                local_session.add(new_mov)
                synced += 1
        
        return synced
    
    async def sync_bidirectional(self, run_once: bool = False):
        """Loop principal de sincronización bidireccional"""
        self._running = True
        logger.info(f"Iniciando sincronización bidireccional para {self.local_instance_id}")
        
        while self._running:
            try:
                await self.check_connectivity()
                
                for remote_id in self.remote_instances:
                    if self.connectivity_status.get(remote_id, False):
                        await self.pull_changes(remote_id)
                
                if run_once:
                    break
                
                await asyncio.sleep(SYNC_INTERVAL_SECONDS)
                
            except Exception as e:
                logger.error(f"Error en ciclo de sincronización: {e}")
                if run_once:
                    raise
                await asyncio.sleep(SYNC_INTERVAL_SECONDS)
    
    def get_sync_status(self) -> Dict:
        """Obtiene el estado actual de sincronización"""
        return {
            'local_instance': self.local_instance_id,
            'connectivity': self.connectivity_status,
            'last_sync': {k: v.isoformat() for k, v in self._last_sync.items()},
            'running': self._running
        }
    
    def stop(self):
        """Detiene el loop de sincronización"""
        self._running = False
