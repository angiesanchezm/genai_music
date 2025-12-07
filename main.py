"""
Aplicación principal FastAPI
"""
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from config.settings import settings
from storage.database import DatabaseManager
from storage.state_manager import StateManager, ConversationState
from services.security_validator import SecurityValidator
from services.rag_service import RAGService
from orchestrator.router import AgentOrchestrator
from integrations.whatsapp_connector import WhatsAppConnector
import structlog
import json
from datetime import datetime

# Configurar logging
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ]
)

logger = structlog.get_logger()

# Dependencias globales
db_manager: DatabaseManager = None
state_manager: StateManager = None
security_validator: SecurityValidator = None
rag_service: RAGService = None
orchestrator: AgentOrchestrator = None
whatsapp: WhatsAppConnector = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle de la aplicación"""
    global db_manager, state_manager, security_validator
    global rag_service, orchestrator, whatsapp
    
    logger.info("application_starting")
    
    # Inicializar componentes
    db_manager = DatabaseManager(settings.database_path)
    await db_manager.initialize()
    
    state_manager = StateManager(settings.database_path)
    security_validator = SecurityValidator()
    rag_service = RAGService()
    orchestrator = AgentOrchestrator(rag_service, state_manager)
    whatsapp = WhatsAppConnector()
    
    # Cargar knowledge base inicial
    await load_initial_knowledge_base()
    
    logger.info("application_ready")
    
    yield
    
    logger.info("application_shutting_down")

app = FastAPI(
    title="Multi-Agent Music Distributor",
    description="Sistema de agentes autónomos para disquera digital",
    version="1.0.0",
    lifespan=lifespan
)

async def load_initial_knowledge_base():
    """Cargar documentos iniciales a Pinecone"""
    try:
        # Leer archivos de knowledge base
        documents = []
        
        kb_files = [
            "data/knowledge_base/distribucion_musical.txt",
            "data/knowledge_base/regalias.txt",
            "data/knowledge_base/faqs_tecnicas.txt"
        ]
        
        for i, file_path in enumerate(kb_files):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                    # Dividir en chunks si es muy largo
                    chunks = [content[j:j+1000] for j in range(0, len(content), 1000)]
                    
                    for j, chunk in enumerate(chunks):
                        documents.append({
                            "id": f"doc_{i}_{j}",
                            "text": chunk,
                            "metadata": {
                                "source": file_path.split('/')[-1],
                                "chunk": j
                            }
                        })
            except FileNotFoundError:
                logger.warning(f"knowledge_base_file_not_found", file=file_path)
        
        if documents:
            await rag_service.upsert_documents(documents)
            logger.info("knowledge_base_loaded", documents_count=len(documents))
        
    except Exception as e:
        logger.error("knowledge_base_load_error", error=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "database": "ok",
            "rag": "ok",
            "orchestrator": "ok"
        }
    }

@app.get("/webhook")
async def verify_webhook(
    request: Request,
    hub_mode: str = None,
    hub_verify_token: str = None,
    hub_challenge: str = None
):
    """
    Verificación de webhook de WhatsApp
    GET endpoint para validación inicial
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if not all([mode, token, challenge]):
        raise HTTPException(status_code=400, detail="Missing parameters")
    
    result = whatsapp.verify_webhook(mode, token, challenge)
    
    if result:
        return Response(content=result, media_type="text/plain")
    else:
        raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook")
async def receive_webhook(request: Request):
    """
    Recibir mensajes de WhatsApp
    POST endpoint para mensajes entrantes
    """
    try:
        body = await request.json()
        
        logger.info("webhook_received", body=body)
        
        # Parsear mensaje
        parsed_message = whatsapp.parse_webhook_message(body)
        
        if not parsed_message:
            return JSONResponse(content={"status": "no_message"})
        
        # Marcar como leído
        await whatsapp.mark_as_read(parsed_message["message_id"])
        
        # Procesar mensaje de forma asíncrona
        await process_incoming_message(parsed_message)
        
        return JSONResponse(content={"status": "success"})
        
    except Exception as e:
        logger.error("webhook_error", error=str(e))
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=200  # WhatsApp requiere 200 siempre
        )

async def process_incoming_message(message_data: Dict):
    """Procesar mensaje entrante"""
    try:
        user_phone = message_data["from"]
        message_text = message_data["text"]
        user_name = message_data.get("name")
        
        logger.info(
            "processing_message",
            user=user_phone,
            message=message_text[:50]
        )
        
        # 1. Validación de seguridad
        is_valid, reason = await security_validator.validate_message(
            message_text,
            user_phone
        )
        
        if not is_valid:
            rejection_msg = security_validator.get_rejection_message(reason)
            await whatsapp.send_message(user_phone, rejection_msg)
            
            logger.warning(
                "message_rejected",
                user=user_phone,
                reason=reason
            )
            return
        
        # 2. Obtener o crear usuario
        user_id = await db_manager.get_or_create_user(user_phone, user_name)
        
        # 3. Crear estado inicial
        state = state_manager.create_initial_state(
            user_phone=user_phone,
            user_id=user_id,
            initial_message=message_text
        )
        
        # 4. Procesar a través del orchestrator
        result_state = await orchestrator.process_message(state)
        
        # 5. Extraer respuesta del agente
        agent_response = result_state["messages"][-1]["content"]
        
        # Limpiar notas internas antes de enviar
        agent_response = agent_response.split("[NOTA INTERNA:")[0].strip()
        
        # 6. Enviar respuesta por WhatsApp
        await whatsapp.send_message(user_phone, agent_response)
        
        # 7. Guardar conversación
        conversation_id = await db_manager.save_conversation(
            user_id=user_id,
            messages=result_state["messages"],
            current_agent=result_state.get("current_agent"),
            state=result_state
        )
        
        # 8. Crear ticket si es necesario
        if result_state.get("should_escalate"):
            priority_score = result_state.get("priority_score", 5.0)
            ticket_id = await db_manager.create_ticket(
                conversation_id=conversation_id,
                priority_score=priority_score
            )
            
            logger.warning(
                "ticket_created",
                ticket_id=ticket_id,
                user=user_phone,
                priority=priority_score
            )
        
        # 9. Log analytics
        await db_manager.log_event(
            event_type="message_processed",
            metadata={
                "user_phone": user_phone,
                "agent": result_state.get("current_agent"),
                "priority_score": result_state.get("priority_score"),
                "sentiment": result_state.get("sentiment_analysis", {}).get("sentiment"),
                "escalated": result_state.get("should_escalate", False)
            }
        )
        
        logger.info(
            "message_processed_successfully",
            user=user_phone,
            agent=result_state.get("current_agent"),
            escalated=result_state.get("should_escalate", False)
        )
        
    except Exception as e:
        logger.error("message_processing_error", error=str(e), user=user_phone)
        
        # Enviar mensaje de error al usuario
        error_msg = (
            "Disculpa, tuve un problema procesando tu mensaje. "
            "Un agente humano te contactará pronto."
        )
        await whatsapp.send_message(user_phone, error_msg)

@app.post("/send-message")
async def send_manual_message(
    to: str,
    message: str
):
    """
    Endpoint para enviar mensajes manuales (testing)
    """
    try:
        result = await whatsapp.send_message(to, message)
        return JSONResponse(content={"status": "sent", "result": result})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Obtener estadísticas del sistema"""
    # TODO: Implementar estadísticas reales de la DB
    return {
        "total_conversations": 0,
        "active_tickets": 0,
        "avg_response_time": 0,
        "escalation_rate": 0
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
