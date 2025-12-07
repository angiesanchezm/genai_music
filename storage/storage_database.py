"""
Gestión de base de datos SQLite para persistencia
"""
import aiosqlite
import json
from datetime import datetime
from typing import Dict, List, Optional
import structlog

logger = structlog.get_logger()

class DatabaseManager:
    """Gestor de base de datos SQLite"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    async def initialize(self):
        """Inicializar esquema de base de datos"""
        async with aiosqlite.connect(self.db_path) as db:
            # Tabla de usuarios
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT UNIQUE NOT NULL,
                    name TEXT,
                    tier TEXT DEFAULT 'basic',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla de conversaciones
            await db.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    messages TEXT NOT NULL,
                    current_agent TEXT,
                    state TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            """)
            
            # Tabla de tickets
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tickets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    priority_score REAL,
                    status TEXT DEFAULT 'open',
                    assigned_to TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    resolved_at TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            """)
            
            # Tabla de analytics
            await db.execute("""
                CREATE TABLE IF NOT EXISTS analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    metadata TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info("database_initialized", db_path=self.db_path)
    
    async def get_or_create_user(self, phone: str, name: Optional[str] = None) -> int:
        """Obtener o crear usuario por teléfono"""
        async with aiosqlite.connect(self.db_path) as db:
            # Buscar usuario existente
            async with db.execute(
                "SELECT id FROM users WHERE phone = ?", (phone,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return row[0]
            
            # Crear nuevo usuario
            await db.execute(
                "INSERT INTO users (phone, name) VALUES (?, ?)",
                (phone, name)
            )
            await db.commit()
            
            async with db.execute(
                "SELECT id FROM users WHERE phone = ?", (phone,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]
    
    async def save_conversation(
        self, 
        user_id: int, 
        messages: List[Dict], 
        current_agent: str,
        state: Dict
    ) -> int:
        """Guardar o actualizar conversación"""
        async with aiosqlite.connect(self.db_path) as db:
            messages_json = json.dumps(messages)
            state_json = json.dumps(state)
            
            await db.execute("""
                INSERT INTO conversations (user_id, messages, current_agent, state, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, messages_json, current_agent, state_json, datetime.now()))
            
            await db.commit()
            
            async with db.execute(
                "SELECT last_insert_rowid()"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]
    
    async def create_ticket(
        self, 
        conversation_id: int, 
        priority_score: float
    ) -> int:
        """Crear ticket de soporte"""
        async with aiosqlite.connect(self.db_path) as db:
            status = "critical" if priority_score >= 9.0 else "high" if priority_score >= 7.0 else "medium"
            
            await db.execute("""
                INSERT INTO tickets (conversation_id, priority_score, status)
                VALUES (?, ?, ?)
            """, (conversation_id, priority_score, status))
            
            await db.commit()
            
            async with db.execute(
                "SELECT last_insert_rowid()"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0]
    
    async def log_event(self, event_type: str, metadata: Dict):
        """Registrar evento de analytics"""
        async with aiosqlite.connect(self.db_path) as db:
            metadata_json = json.dumps(metadata)
            await db.execute(
                "INSERT INTO analytics (event_type, metadata) VALUES (?, ?)",
                (event_type, metadata_json)
            )
            await db.commit()
