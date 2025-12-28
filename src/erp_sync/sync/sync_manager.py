"""Gestor de sincronización bidireccional entre instancias."""

import asyncio
import logging
from typing import Dict, Optional, List
from datetime import datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import Session

from ..models import (
    Product, Customer, Sale, SaleItem, Stock,
    AccountMovement, SyncLog, Instance
)
from ..database import DatabaseManager

logger = logging.getLogger(__name__)


class SyncManager:
    """Gestiona la sincronización bidireccional entre instancias."""

    def __init__(self, local_instance_id: str, db_manager: DatabaseManager):
        """Inicializa el gestor de sincronización.
        
        Args:
            local_instance_id: ID de la instancia local
            db_manager: Gestor de base de datos
        """
        self.local_instance_id = local_instance_id
        self.db_manager = db_manager
        self._running = False
        self._sync_interval = 60  # segundos
        logger.info(f"SyncManager inicializado para instancia: {local_instance_id}")

    async def check_connectivity(self) -> Dict[str, bool]:
        """Verifica la conectividad con las instancias remotas.
        
        Returns:
            Diccionario con el estado de conectividad por instancia
        """
        connectivity = {}
        
        with self.db_manager.get_session() as session:
            instances = session.query(Instance).filter(
                Instance.instance_id != self.local_instance_id
            ).all()
            
            for instance in instances:
                try:
                    # Intentar conectar a la instancia remota
                    remote_engine = self.db_manager.create_remote_engine(
                        instance.connection_string
                    )
                    # Test de conexión simple
                    with remote_engine.connect() as conn:
                        conn.execute(select(1))
                    connectivity[instance.instance_id] = True
                    logger.info(f"Conectividad OK con {instance.instance_id}")
                except Exception as e:
                    connectivity[instance.instance_id] = False
                    logger.error(f"Error conectando a {instance.instance_id}: {e}")
        
        return connectivity

    async def pull_changes(self, remote_instance_id: str) -> None:
        """Obtiene cambios desde una instancia remota.
        
        Args:
            remote_instance_id: ID de la instancia remota
        """
        logger.info(f"Iniciando pull desde {remote_instance_id}")
        
        with self.db_manager.get_session() as local_session:
            # Obtener información de la instancia remota
            remote_instance = local_session.query(Instance).filter_by(
                instance_id=remote_instance_id
            ).first()
            
            if not remote_instance:
                logger.error(f"Instancia remota no encontrada: {remote_instance_id}")
                return
            
            try:
                remote_engine = self.db_manager.create_remote_engine(
                    remote_instance.connection_string
                )
                
                with Session(remote_engine) as remote_session:
                    # Sincronizar en orden de dependencias
                    if remote_instance.is_master:
                        await self._sync_products(local_session, remote_session)
                        await self._sync_customers(local_session, remote_session)
                    
                    await self._sync_sales(local_session, remote_session, remote_instance_id)
                    await self._sync_stock(local_session, remote_session, remote_instance_id)
                    await self._sync_account_movements(local_session, remote_session, remote_instance_id)
                    
                    local_session.commit()
                    logger.info(f"Pull completado desde {remote_instance_id}")
                    
            except Exception as e:
                local_session.rollback()
                logger.error(f"Error en pull desde {remote_instance_id}: {e}")
                raise

    async def _sync_products(self, local_session: Session, remote_session: Session) -> None:
        """Sincroniza productos desde el master."""
        logger.info("Sincronizando productos desde master")
        
        # Obtener última versión sincronizada
        last_sync = local_session.query(SyncLog).filter_by(
            entity_type='Product'
        ).order_by(SyncLog.sync_timestamp.desc()).first()
        
        last_version = last_sync.last_sync_version if last_sync else 0
        
        # Obtener productos actualizados desde el master
        remote_products = remote_session.query(Product).filter(
            Product.sync_version > last_version
        ).all()
        
        for remote_product in remote_products:
            local_product = local_session.query(Product).filter_by(
                product_id=remote_product.product_id
            ).first()
            
            if local_product:
                # Actualizar producto existente
                local_product.name = remote_product.name
                local_product.description = remote_product.description
                local_product.price = remote_product.price
                local_product.sync_version = remote_product.sync_version
                local_product.updated_at = datetime.utcnow()
                logger.debug(f"Producto actualizado: {remote_product.product_id}")
            else:
                # Crear nuevo producto
                new_product = Product(
                    product_id=remote_product.product_id,
                    name=remote_product.name,
                    description=remote_product.description,
                    price=remote_product.price,
                    sync_version=remote_product.sync_version
                )
                local_session.add(new_product)
                logger.debug(f"Producto creado: {remote_product.product_id}")
        
        # Registrar sincronización
        if remote_products:
            max_version = max(p.sync_version for p in remote_products)
            sync_log = SyncLog(
                entity_type='Product',
                sync_timestamp=datetime.utcnow(),
                last_sync_version=max_version,
                records_synced=len(remote_products)
            )
            local_session.add(sync_log)
            logger.info(f"Sincronizados {len(remote_products)} productos")

    async def _sync_customers(self, local_session: Session, remote_session: Session) -> None:
        """Sincroniza clientes desde el master."""
        logger.info("Sincronizando clientes desde master")
        
        last_sync = local_session.query(SyncLog).filter_by(
            entity_type='Customer'
        ).order_by(SyncLog.sync_timestamp.desc()).first()
        
        last_version = last_sync.last_sync_version if last_sync else 0
        
        remote_customers = remote_session.query(Customer).filter(
            Customer.sync_version > last_version
        ).all()
        
        for remote_customer in remote_customers:
            local_customer = local_session.query(Customer).filter_by(
                customer_id=remote_customer.customer_id
            ).first()
            
            if local_customer:
                local_customer.name = remote_customer.name
                local_customer.email = remote_customer.email
                local_customer.phone = remote_customer.phone
                local_customer.sync_version = remote_customer.sync_version
                local_customer.updated_at = datetime.utcnow()
                logger.debug(f"Cliente actualizado: {remote_customer.customer_id}")
            else:
                new_customer = Customer(
                    customer_id=remote_customer.customer_id,
                    name=remote_customer.name,
                    email=remote_customer.email,
                    phone=remote_customer.phone,
                    sync_version=remote_customer.sync_version
                )
                local_session.add(new_customer)
                logger.debug(f"Cliente creado: {remote_customer.customer_id}")
        
        if remote_customers:
            max_version = max(c.sync_version for c in remote_customers)
            sync_log = SyncLog(
                entity_type='Customer',
                sync_timestamp=datetime.utcnow(),
                last_sync_version=max_version,
                records_synced=len(remote_customers)
            )
            local_session.add(sync_log)
            logger.info(f"Sincronizados {len(remote_customers)} clientes")

    async def _sync_sales(self, local_session: Session, remote_session: Session, 
                         remote_instance_id: str) -> None:
        """Sincroniza ventas usando claves compuestas."""
        logger.info(f"Sincronizando ventas con {remote_instance_id}")
        
        last_sync = local_session.query(SyncLog).filter_by(
            entity_type='Sale',
            remote_instance_id=remote_instance_id
        ).order_by(SyncLog.sync_timestamp.desc()).first()
        
        last_version = last_sync.last_sync_version if last_sync else 0
        
        # Obtener ventas actualizadas desde remoto
        remote_sales = remote_session.query(Sale).filter(
            Sale.sync_version > last_version
        ).all()
        
        for remote_sale in remote_sales:
            local_sale = local_session.query(Sale).filter_by(
                sale_id=remote_sale.sale_id,
                instance_id=remote_sale.instance_id
            ).first()
            
            if local_sale:
                # Resolver conflictos: last-write-wins
                if remote_sale.sync_version > local_sale.sync_version:
                    local_sale.customer_id = remote_sale.customer_id
                    local_sale.total_amount = remote_sale.total_amount
                    local_sale.status = remote_sale.status
                    local_sale.sync_version = remote_sale.sync_version
                    local_sale.updated_at = datetime.utcnow()
                    
                    # Sincronizar items de venta
                    local_session.query(SaleItem).filter_by(
                        sale_id=local_sale.sale_id,
                        instance_id=local_sale.instance_id
                    ).delete()
                    
                    remote_items = remote_session.query(SaleItem).filter_by(
                        sale_id=remote_sale.sale_id,
                        instance_id=remote_sale.instance_id
                    ).all()
                    
                    for remote_item in remote_items:
                        new_item = SaleItem(
                            sale_id=remote_item.sale_id,
                            instance_id=remote_item.instance_id,
                            product_id=remote_item.product_id,
                            quantity=remote_item.quantity,
                            unit_price=remote_item.unit_price,
                            subtotal=remote_item.subtotal
                        )
                        local_session.add(new_item)
                    
                    logger.debug(f"Venta actualizada: {remote_sale.sale_id}")
            else:
                # Crear nueva venta
                new_sale = Sale(
                    sale_id=remote_sale.sale_id,
                    instance_id=remote_sale.instance_id,
                    customer_id=remote_sale.customer_id,
                    total_amount=remote_sale.total_amount,
                    status=remote_sale.status,
                    sync_version=remote_sale.sync_version,
                    created_at=remote_sale.created_at
                )
                local_session.add(new_sale)
                
                # Agregar items
                remote_items = remote_session.query(SaleItem).filter_by(
                    sale_id=remote_sale.sale_id,
                    instance_id=remote_sale.instance_id
                ).all()
                
                for remote_item in remote_items:
                    new_item = SaleItem(
                        sale_id=remote_item.sale_id,
                        instance_id=remote_item.instance_id,
                        product_id=remote_item.product_id,
                        quantity=remote_item.quantity,
                        unit_price=remote_item.unit_price,
                        subtotal=remote_item.subtotal
                    )
                    local_session.add(new_item)
                
                logger.debug(f"Venta creada: {remote_sale.sale_id}")
        
        if remote_sales:
            max_version = max(s.sync_version for s in remote_sales)
            sync_log = SyncLog(
                entity_type='Sale',
                remote_instance_id=remote_instance_id,
                sync_timestamp=datetime.utcnow(),
                last_sync_version=max_version,
                records_synced=len(remote_sales)
            )
            local_session.add(sync_log)
            logger.info(f"Sincronizadas {len(remote_sales)} ventas")

    async def _sync_stock(self, local_session: Session, remote_session: Session,
                         remote_instance_id: str) -> None:
        """Sincroniza stock por sitio."""
        logger.info(f"Sincronizando stock con {remote_instance_id}")
        
        last_sync = local_session.query(SyncLog).filter_by(
            entity_type='Stock',
            remote_instance_id=remote_instance_id
        ).order_by(SyncLog.sync_timestamp.desc()).first()
        
        last_version = last_sync.last_sync_version if last_sync else 0
        
        # Solo sincronizar stock del sitio remoto
        remote_stocks = remote_session.query(Stock).filter(
            and_(
                Stock.instance_id == remote_instance_id,
                Stock.sync_version > last_version
            )
        ).all()
        
        for remote_stock in remote_stocks:
            local_stock = local_session.query(Stock).filter_by(
                product_id=remote_stock.product_id,
                instance_id=remote_stock.instance_id
            ).first()
            
            if local_stock:
                if remote_stock.sync_version > local_stock.sync_version:
                    local_stock.quantity = remote_stock.quantity
                    local_stock.sync_version = remote_stock.sync_version
                    local_stock.updated_at = datetime.utcnow()
                    logger.debug(f"Stock actualizado: {remote_stock.product_id}@{remote_stock.instance_id}")
            else:
                new_stock = Stock(
                    product_id=remote_stock.product_id,
                    instance_id=remote_stock.instance_id,
                    quantity=remote_stock.quantity,
                    sync_version=remote_stock.sync_version
                )
                local_session.add(new_stock)
                logger.debug(f"Stock creado: {remote_stock.product_id}@{remote_stock.instance_id}")
        
        if remote_stocks:
            max_version = max(s.sync_version for s in remote_stocks)
            sync_log = SyncLog(
                entity_type='Stock',
                remote_instance_id=remote_instance_id,
                sync_timestamp=datetime.utcnow(),
                last_sync_version=max_version,
                records_synced=len(remote_stocks)
            )
            local_session.add(sync_log)
            logger.info(f"Sincronizados {len(remote_stocks)} registros de stock")

    async def _sync_account_movements(self, local_session: Session, remote_session: Session,
                                     remote_instance_id: str) -> None:
        """Sincroniza movimientos de cuenta de forma bidireccional."""
        logger.info(f"Sincronizando movimientos de cuenta con {remote_instance_id}")
        
        last_sync = local_session.query(SyncLog).filter_by(
            entity_type='AccountMovement',
            remote_instance_id=remote_instance_id
        ).order_by(SyncLog.sync_timestamp.desc()).first()
        
        last_version = last_sync.last_sync_version if last_sync else 0
        
        remote_movements = remote_session.query(AccountMovement).filter(
            AccountMovement.sync_version > last_version
        ).all()
        
        for remote_movement in remote_movements:
            local_movement = local_session.query(AccountMovement).filter_by(
                movement_id=remote_movement.movement_id,
                instance_id=remote_movement.instance_id
            ).first()
            
            if local_movement:
                if remote_movement.sync_version > local_movement.sync_version:
                    local_movement.customer_id = remote_movement.customer_id
                    local_movement.amount = remote_movement.amount
                    local_movement.movement_type = remote_movement.movement_type
                    local_movement.description = remote_movement.description
                    local_movement.sync_version = remote_movement.sync_version
                    local_movement.updated_at = datetime.utcnow()
                    logger.debug(f"Movimiento actualizado: {remote_movement.movement_id}")
            else:
                new_movement = AccountMovement(
                    movement_id=remote_movement.movement_id,
                    instance_id=remote_movement.instance_id,
                    customer_id=remote_movement.customer_id,
                    amount=remote_movement.amount,
                    movement_type=remote_movement.movement_type,
                    description=remote_movement.description,
                    sync_version=remote_movement.sync_version,
                    created_at=remote_movement.created_at
                )
                local_session.add(new_movement)
                logger.debug(f"Movimiento creado: {remote_movement.movement_id}")
        
        if remote_movements:
            max_version = max(m.sync_version for m in remote_movements)
            sync_log = SyncLog(
                entity_type='AccountMovement',
                remote_instance_id=remote_instance_id,
                sync_timestamp=datetime.utcnow(),
                last_sync_version=max_version,
                records_synced=len(remote_movements)
            )
            local_session.add(sync_log)
            logger.info(f"Sincronizados {len(remote_movements)} movimientos de cuenta")

    async def push_changes(self, remote_instance_id: str) -> None:
        """Envía cambios locales a una instancia remota.
        
        Args:
            remote_instance_id: ID de la instancia remota
        """
        logger.info(f"Iniciando push hacia {remote_instance_id}")
        
        with self.db_manager.get_session() as local_session:
            remote_instance = local_session.query(Instance).filter_by(
                instance_id=remote_instance_id
            ).first()
            
            if not remote_instance:
                logger.error(f"Instancia remota no encontrada: {remote_instance_id}")
                return
            
            try:
                remote_engine = self.db_manager.create_remote_engine(
                    remote_instance.connection_string
                )
                
                with Session(remote_engine) as remote_session:
                    # Push en orden inverso (desde local a remoto)
                    await self._sync_sales(remote_session, local_session, self.local_instance_id)
                    await self._sync_stock(remote_session, local_session, self.local_instance_id)
                    await self._sync_account_movements(remote_session, local_session, self.local_instance_id)
                    
                    remote_session.commit()
                    logger.info(f"Push completado hacia {remote_instance_id}")
                    
            except Exception as e:
                logger.error(f"Error en push hacia {remote_instance_id}: {e}")
                raise

    async def sync_bidirectional(self, run_once: bool = False) -> None:
        """Ejecuta el ciclo principal de sincronización bidireccional.
        
        Args:
            run_once: Si es True, ejecuta solo una vez y termina
        """
        self._running = True
        logger.info("Iniciando ciclo de sincronización bidireccional")
        
        while self._running:
            try:
                # Verificar conectividad
                connectivity = await self.check_connectivity()
                
                with self.db_manager.get_session() as session:
                    instances = session.query(Instance).filter(
                        Instance.instance_id != self.local_instance_id
                    ).all()
                    
                    for instance in instances:
                        if connectivity.get(instance.instance_id, False):
                            try:
                                # Pull primero
                                await self.pull_changes(instance.instance_id)
                                
                                # Luego push
                                await self.push_changes(instance.instance_id)
                                
                            except Exception as e:
                                logger.error(f"Error sincronizando con {instance.instance_id}: {e}")
                                continue
                        else:
                            logger.warning(f"Sin conectividad con {instance.instance_id}, omitiendo")
                
                if run_once:
                    logger.info("Sincronización única completada")
                    break
                
                # Esperar antes del siguiente ciclo
                logger.info(f"Esperando {self._sync_interval} segundos hasta el próximo ciclo")
                await asyncio.sleep(self._sync_interval)
                
            except Exception as e:
                logger.error(f"Error en ciclo de sincronización: {e}")
                if run_once:
                    raise
                await asyncio.sleep(self._sync_interval)
        
        logger.info("Ciclo de sincronización finalizado")

    def get_sync_status(self) -> Dict:
        """Obtiene el estado actual de sincronización.
        
        Returns:
            Diccionario con información del estado de sincronización
        """
        status = {
            'local_instance_id': self.local_instance_id,
            'running': self._running,
            'sync_interval': self._sync_interval,
            'last_syncs': []
        }
        
        with self.db_manager.get_session() as session:
            recent_syncs = session.query(SyncLog).order_by(
                SyncLog.sync_timestamp.desc()
            ).limit(10).all()
            
            for sync in recent_syncs:
                status['last_syncs'].append({
                    'entity_type': sync.entity_type,
                    'remote_instance_id': sync.remote_instance_id,
                    'timestamp': sync.sync_timestamp.isoformat(),
                    'records_synced': sync.records_synced
                })
        
        return status

    def stop(self) -> None:
        """Detiene el ciclo de sincronización."""
        logger.info("Deteniendo sincronización")
        self._running = False
