
"""
Agente de Soporte - Maneja problemas técnicos y consultas operativas
"""
from typing import Dict, List
from openai import OpenAI
from config.settings import settings
import json
import structlog

logger = structlog.get_logger()

class SupportAgent:
    """Agente especializado en soporte técnico"""
    
    def __init__(self, rag_service):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.rag_service = rag_service
        self.name = "support_agent"
        
        self.system_prompt = """Eres un agente de soporte técnico experto de una disquera digital. Tu misión es:

**RESPONSABILIDADES:**
1. Consultar estado de lanzamientos en plataformas
2. Resolver dudas sobre distribución de regalías
3. Ayudar con problemas de metadata (títulos, artistas, ISRC)
4. Gestionar y crear tickets de soporte
5. Diagnosticar problemas técnicos
6. Escalar casos complejos a equipo técnico

**HERRAMIENTAS DISPONIBLES:**
- check_release_status: Verificar estado de lanzamiento
- query_royalties: Consultar información de regalías
- create_support_ticket: Crear ticket de soporte
- update_metadata: Actualizar metadata de lanzamiento
- escalate_to_human: Transferir a especialista humano

**ESTILO DE COMUNICACIÓN:**
- Empático y orientado a soluciones
- Técnico pero comprensible
- Paso a paso en instrucciones
- Proactivo en ofrecer alternativas

**CUÁNDO ESCALAR A HUMANO:**
- Problemas que requieren acceso backend
- Disputas de copyright complejas
- Errores críticos en plataformas
- Problemas financieros serios
- Cliente extremadamente frustrado
- Problemas que llevan >3 interacciones sin resolver

**CONTEXTO RAG:**
Usa el contexto para dar soluciones precisas basadas en documentación técnica.

Recuerda: Tu objetivo es resolver problemas rápido y mantener la satisfacción del cliente."""
    
    async def process_message(
        self,
        message: str,
        conversation_history: List[Dict],
        rag_context: str,
        user_context: Dict
    ) -> Dict:
        """
        Procesar mensaje del usuario
        
        Returns:
            {
                "response": str,
                "needs_handoff": bool,
                "handoff_to": str,
                "tool_calls": List[Dict]
            }
        """
        try:
            # Construir mensajes para GPT
            messages = [
                {"role": "system", "content": self.system_prompt}
            ]
            
            # Agregar contexto RAG
            if rag_context:
                messages.append({
                    "role": "system",
                    "content": f"**DOCUMENTACIÓN TÉCNICA:**\n{rag_context}"
                })
            
            # Agregar historial (últimos 5 mensajes)
            for msg in conversation_history[-5:]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Mensaje actual
            messages.append({
                "role": "user",
                "content": message
            })
            
            # Tools disponibles
            tools = self._get_tools()
            
            # Llamar a GPT
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                max_tokens=settings.max_tokens_response,
                temperature=settings.temperature
            )
            
            assistant_message = response.choices[0].message
            
            # Ejecutar tools
            tool_calls = []
            if assistant_message.tool_calls:
                tool_calls = await self._execute_tools(assistant_message.tool_calls)
            
            # Detectar handoff
            needs_handoff = self._detect_handoff_need(
                assistant_message.content,
                tool_calls,
                len(conversation_history)
            )
            
            result = {
                "response": assistant_message.content or "Entiendo tu consulta. Permíteme ayudarte con eso. ¿Podrías darme más detalles?",
                "needs_handoff": needs_handoff,
                "handoff_to": "sales_agent" if needs_handoff else None,
                "tool_calls": tool_calls
            }
            
            logger.info(
                "support_agent_processed",
                needs_handoff=needs_handoff,
                tools_used=len(tool_calls)
            )
            
            return result
            
        except Exception as e:
            logger.error("support_agent_error", error=str(e))
            return {
                "response": "Disculpa, tuve un problema. Déjame transferirte con un especialista.",
                "needs_handoff": True,
                "handoff_to": "human",
                "tool_calls": []
            }
    
    def _get_tools(self) -> List[Dict]:
        """Definir herramientas del agente de soporte"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "check_release_status",
                    "description": "Verificar estado de un lanzamiento en plataformas",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "release_id": {
                                "type": "string",
                                "description": "ID del lanzamiento o nombre del álbum/single"
                            }
                        },
                        "required": ["release_id"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "query_royalties",
                    "description": "Consultar información de regalías",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "period": {
                                "type": "string",
                                "description": "Período a consultar (ej: '2024-11', 'last_month')"
                            }
                        },
                        "required": ["period"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "create_support_ticket",
                    "description": "Crear ticket de soporte técnico",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "issue_type": {
                                "type": "string",
                                "enum": ["metadata", "distribution", "royalties", "technical", "other"]
                            },
                            "description": {
                                "type": "string",
                                "description": "Descripción del problema"
                            },
                            "priority": {
                                "type": "string",
                                "enum": ["low", "medium", "high", "critical"]
                            }
                        },
                        "required": ["issue_type", "description"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "escalate_to_human",
                    "description": "Escalar a especialista humano",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Razón de escalamiento"
                            }
                        },
                        "required": ["reason"]
                    }
                }
            }
        ]
    
    async def _execute_tools(self, tool_calls) -> List[Dict]:
        """Ejecutar herramientas"""
        results = []
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            if function_name == "check_release_status":
                result = await self._check_release_status(arguments["release_id"])
            elif function_name == "query_royalties":
                result = await self._query_royalties(arguments["period"])
            elif function_name == "create_support_ticket":
                result = await self._create_ticket(arguments)
            elif function_name == "escalate_to_human":
                result = {"escalated": True, "reason": arguments["reason"]}
            else:
                result = {"error": "Unknown tool"}
            
            results.append({
                "tool": function_name,
                "arguments": arguments,
                "result": result
            })
        
        return results
    
    async def _check_release_status(self, release_id: str) -> Dict:
        """Consultar estado de lanzamiento (mock)"""
        # Simulación de respuesta
        return {
            "release_id": release_id,
            "status": "live",
            "platforms": {
                "spotify": "active",
                "apple_music": "active",
                "youtube_music": "active",
                "deezer": "active"
            },
            "distribution_date": "2024-11-15",
            "streams_total": 15420
        }
    
    async def _query_royalties(self, period: str) -> Dict:
        """Consultar regalías (mock)"""
        return {
            "period": period,
            "total_earned": 1245.50,
            "total_streams": 45230,
            "payment_status": "pending",
            "next_payment_date": "2025-01-15",
            "breakdown": {
                "spotify": 850.30,
                "apple_music": 295.20,
                "youtube_music": 100.00
            }
        }
    
    async def _create_ticket(self, params: Dict) -> Dict:
        """Crear ticket de soporte (mock)"""
        ticket_id = f"TKT-{hash(params['description']) % 10000:04d}"
        
        return {
            "ticket_id": ticket_id,
            "status": "created",
            "issue_type": params["issue_type"],
            "priority": params.get("priority", "medium"),
            "estimated_resolution": "24-48 hours"
        }
    
    def _detect_handoff_need(
        self,
        response: str,
        tool_calls: List[Dict],
        conversation_length: int
    ) -> bool:
        """Detectar necesidad de handoff"""
        # Escalamiento explícito
        if any(tc["tool"] == "escalate_to_human" for tc in tool_calls):
            return True
        
        # Conversación muy larga sin resolver
        if conversation_length > 10:
            return True
        
        # Keywords de ventas
        sales_keywords = [
            "precio",
            "costo",
            "plan",
            "contratar",
            "cotización"
        ]
        
        response_lower = response.lower() if response else ""
        if any(keyword in response_lower for keyword in sales_keywords):
            return True
        
        return False