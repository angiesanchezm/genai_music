"""
Gestor de estado usando LangGraph
"""
from typing import Dict, List, Optional, TypedDict, Annotated
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from datetime import datetime
import operator
import structlog

logger = structlog.get_logger()

class ConversationState(TypedDict):
    """Estado de la conversación"""
    messages: Annotated[List[Dict], operator.add]
    user_phone: str
    user_id: int
    current_agent: Optional[str]
    agent_context: Dict
    rag_context: Optional[str]
    sentiment_analysis: Optional[Dict]
    priority_score: Optional[float]
    should_escalate: bool
    conversation_id: Optional[int]
    metadata: Dict

class StateManager:
    """Gestor de estado de conversaciones con LangGraph"""
    
    def __init__(self, db_path: str):
        self.checkpointer = SqliteSaver.from_conn_string(db_path)
    
    def create_initial_state(
        self,
        user_phone: str,
        user_id: int,
        initial_message: str
    ) -> ConversationState:
        """Crear estado inicial de conversación"""
        return ConversationState(
            messages=[{
                "role": "user",
                "content": initial_message,
                "timestamp": datetime.now().isoformat()
            }],
            user_phone=user_phone,
            user_id=user_id,
            current_agent=None,
            agent_context={},
            rag_context=None,
            sentiment_analysis=None,
            priority_score=None,
            should_escalate=False,
            conversation_id=None,
            metadata={}
        )
    
    def update_state(
        self,
        state: ConversationState,
        updates: Dict
    ) -> ConversationState:
        """Actualizar estado con nuevos valores"""
        return {**state, **updates}
    
    async def save_checkpoint(
        self,
        state: ConversationState,
        thread_id: str
    ):
        """Guardar checkpoint del estado"""
        try:
            config = {"configurable": {"thread_id": thread_id}}
            await self.checkpointer.aput(config, state)
            logger.info("checkpoint_saved", thread_id=thread_id)
        except Exception as e:
            logger.error("checkpoint_save_error", error=str(e))
    
    async def load_checkpoint(
        self,
        thread_id: str
    ) -> Optional[ConversationState]:
        """Cargar checkpoint del estado"""
        try:
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint = await self.checkpointer.aget(config)
            
            if checkpoint:
                logger.info("checkpoint_loaded", thread_id=thread_id)
                return checkpoint.state
            
            return None
        except Exception as e:
            logger.error("checkpoint_load_error", error=str(e))
            return None
