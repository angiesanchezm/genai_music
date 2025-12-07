"""
Orquestador central - Router de mensajes y coordinación de agentes
"""
from typing import Dict, List, Optional
from datetime import datetime
from langgraph.graph import StateGraph, END
from openai import OpenAI
from config.settings import settings
from storage.state_manager import ConversationState, StateManager
from agents.sales_agent import SalesAgent
from agents.support_agent import SupportAgent
from services.rag_service import RAGService
from services.sentiment_analyzer import SentimentAnalyzer
from services.priority_scorer import PriorityScorer
import structlog

logger = structlog.get_logger()

class AgentOrchestrator:
    """Orquestador de agentes multi-agente"""
    
    def __init__(
        self,
        rag_service: RAGService,
        state_manager: StateManager
    ):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.rag_service = rag_service
        self.state_manager = state_manager
        
        # Inicializar agentes
        self.sales_agent = SalesAgent(rag_service)
        self.support_agent = SupportAgent(rag_service)
        
        # Servicios de análisis
        self.sentiment_analyzer = SentimentAnalyzer()
        self.priority_scorer = PriorityScorer()
        
        # Crear grafo de workflow
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Construir workflow de LangGraph"""
        workflow = StateGraph(ConversationState)
        
        # Nodos del grafo
        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("analyze_sentiment", self._analyze_sentiment)
        workflow.add_node("route_to_agent", self._route_to_agent)
        workflow.add_node("sales_agent", self._execute_sales_agent)
        workflow.add_node("support_agent", self._execute_support_agent)
        workflow.add_node("calculate_priority", self._calculate_priority)
        workflow.add_node("check_escalation", self._check_escalation)
        
        # Definir edges
        workflow.set_entry_point("classify_intent")
        workflow.add_edge("classify_intent", "retrieve_context")
        workflow.add_edge("retrieve_context", "analyze_sentiment")
        workflow.add_edge("analyze_sentiment", "route_to_agent")
        
        # Routing condicional
        workflow.add_conditional_edges(
            "route_to_agent",
            self._agent_router,
            {
                "sales": "sales_agent",
                "support": "support_agent"
            }
        )
        
        workflow.add_edge("sales_agent", "calculate_priority")
        workflow.add_edge("support_agent", "calculate_priority")
        workflow.add_edge("calculate_priority", "check_escalation")
        workflow.add_edge("check_escalation", END)
        
        return workflow.compile(checkpointer=self.state_manager.checkpointer)
    
    async def process_message(
        self,
        state: ConversationState
    ) -> ConversationState:
        """Procesar mensaje a través del workflow"""
        try:
            thread_id = f"user_{state['user_phone']}"
            config = {"configurable": {"thread_id": thread_id}}
            
            # Ejecutar workflow
            result = await self.workflow.ainvoke(state, config)
            
            logger.info(
                "message_processed",
                user=state["user_phone"],
                agent=result.get("current_agent")
            )
            
            return result
            
        except Exception as e:
            logger.error("orchestrator_error", error=str(e))
            raise
    
    async def _classify_intent(self, state: ConversationState) -> ConversationState:
        """Clasificar intención del mensaje"""
        last_message = state["messages"][-1]["content"]
        
        try:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Clasifica la intención del mensaje en UNA de estas categorías:

- SALES: Precios, planes, cotizaciones, contratar servicio, onboarding
- SUPPORT: Problemas técnicos, estado de lanzamiento, regalías, metadata, errores

Responde SOLO con: SALES o SUPPORT"""
                    },
                    {
                        "role": "user",
                        "content": last_message
                    }
                ],
                max_tokens=10,
                temperature=0.0
            )
            
            intent = response.choices[0].message.content.strip().upper()
            
            state["metadata"]["intent"] = intent
            logger.info("intent_classified", intent=intent)
            
        except Exception as e:
            logger.error("intent_classification_error", error=str(e))
            state["metadata"]["intent"] = "SUPPORT"  # Default
        
        return state
    
    async def _retrieve_context(self, state: ConversationState) -> ConversationState:
        """Recuperar contexto de RAG"""
        last_message = state["messages"][-1]["content"]
        
        try:
            # Query a Pinecone
            results = await self.rag_service.query_knowledge_base(
                query=last_message,
                top_k=3
            )
            
            # Construir contexto
            context = await self.rag_service.build_context_from_results(results)
            state["rag_context"] = context
            
            logger.info("rag_context_retrieved", results_count=len(results))
            
        except Exception as e:
            logger.error("rag_retrieval_error", error=str(e))
            state["rag_context"] = ""
        
        return state
    
    async def _analyze_sentiment(self, state: ConversationState) -> ConversationState:
        """Analizar sentimiento del mensaje"""
        last_message = state["messages"][-1]["content"]
        
        try:
            sentiment = await self.sentiment_analyzer.analyze(
                message=last_message,
                conversation_history=state["messages"]
            )
            
            state["sentiment_analysis"] = sentiment
            
        except Exception as e:
            logger.error("sentiment_analysis_error", error=str(e))
        
        return state
    
    def _agent_router(self, state: ConversationState) -> str:
        """Decidir qué agente debe manejar el mensaje"""
        intent = state["metadata"].get("intent", "SUPPORT")
        
        # Si hay agente actual y no hay necesidad de cambio, mantener
        if state.get("current_agent") and not state["metadata"].get("force_routing"):
            return state["current_agent"].replace("_agent", "")
        
        # Router basado en intent
        if intent == "SALES":
            return "sales"
        else:
            return "support"
    
    async def _execute_sales_agent(self, state: ConversationState) -> ConversationState:
        """Ejecutar agente de ventas"""
        last_message = state["messages"][-1]["content"]
        
        result = await self.sales_agent.process_message(
            message=last_message,
            conversation_history=state["messages"],
            rag_context=state.get("rag_context", ""),
            user_context=state.get("agent_context", {})
        )
        
        # Agregar respuesta al estado
        state["messages"].append({
            "role": "assistant",
            "content": result["response"],
            "agent": "sales_agent"
        })
        
        state["current_agent"] = "sales_agent"
        state["metadata"]["tool_calls"] = result.get("tool_calls", [])
        state["metadata"]["needs_handoff"] = result.get("needs_handoff", False)
        
        return state
    
    async def _execute_support_agent(self, state: ConversationState) -> ConversationState:
        """Ejecutar agente de soporte"""
        last_message = state["messages"][-1]["content"]
        
        result = await self.support_agent.process_message(
            message=last_message,
            conversation_history=state["messages"],
            rag_context=state.get("rag_context", ""),
            user_context=state.get("agent_context", {})
        )
        
        # Agregar respuesta
        state["messages"].append({
            "role": "assistant",
            "content": result["response"],
            "agent": "support_agent"
        })
        
        state["current_agent"] = "support_agent"
        state["metadata"]["tool_calls"] = result.get("tool_calls", [])
        state["metadata"]["needs_handoff"] = result.get("needs_handoff", False)
        
        return state
    
    async def _calculate_priority(self, state: ConversationState) -> ConversationState:
        """Calcular score de prioridad"""
        last_message = state["messages"][-1]["content"]
        sentiment = state.get("sentiment_analysis", {})
        
        try:
            priority = await self.priority_scorer.calculate_priority(
                message=last_message,
                sentiment_analysis=sentiment,
                conversation_history=state["messages"]
            )
            
            state["priority_score"] = priority["priority_score"]
            state["should_escalate"] = priority["should_escalate"]
            state["metadata"]["priority_details"] = priority
            
        except Exception as e:
            logger.error("priority_calculation_error", error=str(e))
        
        return state
    
    async def _check_escalation(self, state: ConversationState) -> ConversationState:
        """Verificar si se debe escalar a humano"""
        if state.get("should_escalate", False):
            escalation_msg = (
                "\n\n[NOTA INTERNA: Este caso ha sido marcado para escalamiento "
                "a un agente humano debido a su prioridad]"
            )
            
            # Agregar nota al último mensaje
            state["messages"][-1]["content"] += escalation_msg
            
            logger.warning(
                "case_escalated",
                user=state["user_phone"],
                priority=state.get("priority_score")
            )
        
        return state
