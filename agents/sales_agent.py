

"""
Agente de Ventas - Maneja consultas comerciales y onboarding
"""
from typing import Dict, List
from openai import OpenAI
from config.settings import settings
import json
import structlog

logger = structlog.get_logger()

class SalesAgent:
    """Agente especializado en ventas y onboarding"""
    
    def __init__(self, rag_service):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.rag_service = rag_service
        self.name = "sales_agent"
        
        self.system_prompt = """Eres un agente de ventas experto de una disquera digital. Tu misión es:

**RESPONSABILIDADES:**
1. Explicar servicios de distribución musical a plataformas (Spotify, Apple Music, etc.)
2. Consultar y presentar precios de forma clara
3. Generar cotizaciones personalizadas
4. Guiar el proceso de onboarding de nuevos artistas
5. Calificar leads y detectar oportunidades de venta
6. Responder dudas sobre planes y paquetes

**HERRAMIENTAS DISPONIBLES:**
- get_pricing: Consultar precios de servicios
- generate_quote: Generar cotización personalizada
- escalate_to_human: Transferir a agente humano

**ESTILO DE COMUNICACIÓN:**
- Amigable y profesional
- Conciso (máximo 3-4 oraciones por respuesta)
- Enfocado en valor y beneficios
- Proactivo en sugerir próximos pasos

**IMPORTANTE:**
- SIEMPRE debes dar una respuesta en texto, incluso si usas herramientas
- Primero usa las herramientas necesarias, luego explica al cliente lo que encontraste
- Nunca dejes un mensaje vacío

**CUÁNDO ESCALAR A HUMANO:**
- Negociaciones de contratos especiales
- Clientes enterprise o de alto valor
- Solicitudes de descuentos significativos
- Dudas técnicas muy específicas que no puedes resolver
- Cliente pide hablar con un humano

**CONTEXTO RAG:**
Usa el contexto proporcionado para dar respuestas precisas y actualizadas sobre servicios y precios.

Recuerda: Tu objetivo es convertir leads en clientes, pero siempre con transparencia y honestidad."""
    
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
            
            # Agregar contexto RAG si existe
            if rag_context:
                messages.append({
                    "role": "system",
                    "content": f"**CONTEXTO DE KNOWLEDGE BASE:**\n{rag_context}"
                })
            
            # Agregar historial de conversación (últimos 5 mensajes)
            for msg in conversation_history[-5:]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Agregar mensaje actual
            messages.append({
                "role": "user",
                "content": message
            })
            
            # Definir tools disponibles
            tools = self._get_tools()
            
            # Llamar a GPT
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            
            # Procesar respuesta
            assistant_message = response.choices[0].message
            
            # Ejecutar tools si existen
            tool_calls = []
            tool_results = []
            if assistant_message.tool_calls:
                tool_calls = await self._execute_tools(assistant_message.tool_calls)
                tool_results = tool_calls
            
            # Generar respuesta final
            final_response = assistant_message.content
            
            # Si solo hay tool calls sin contenido, generar respuesta basada en tools
            if not final_response and tool_calls:
                final_response = await self._generate_response_from_tools(
                    message,
                    tool_calls,
                    messages
                )
            
            # Si aún no hay respuesta, usar fallback
            if not final_response:
                final_response = "¡Hola! Estoy aquí para ayudarte con nuestros servicios de distribución musical. ¿En qué puedo asistirte?"
            
            # Detectar necesidad de handoff
            needs_handoff = self._detect_handoff_need(
                final_response,
                tool_calls
            )
            
            result = {
                "response": final_response,
                "needs_handoff": needs_handoff,
                "handoff_to": "support_agent" if needs_handoff else None,
                "tool_calls": tool_calls
            }
            
            logger.info(
                "sales_agent_processed",
                needs_handoff=needs_handoff,
                tools_used=len(tool_calls),
                response_length=len(final_response)
            )
            
            return result
            
        except Exception as e:
            logger.error("sales_agent_error", error=str(e))
            return {
                "response": "Disculpa, tuve un problema procesando tu consulta. ¿Podrías reformularla?",
                "needs_handoff": False,
                "handoff_to": None,
                "tool_calls": []
            }
    
    async def _generate_response_from_tools(
        self,
        original_message: str,
        tool_calls: List[Dict],
        conversation_messages: List[Dict]
    ) -> str:
        """Generar respuesta en lenguaje natural basada en resultados de tools"""
        try:
            # Construir resumen de tool results
            tools_summary = "\n".join([
                f"- {tc['tool']}: {json.dumps(tc['result'], ensure_ascii=False)}"
                for tc in tool_calls
            ])
            
            # Segunda llamada a GPT para generar respuesta natural
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=conversation_messages + [
                    {
                        "role": "system",
                        "content": f"""Basándote en los resultados de las herramientas ejecutadas:

{tools_summary}

Genera una respuesta amigable y profesional para el cliente que explique la información de manera clara y concisa (máximo 3-4 oraciones)."""
                    },
                    {
                        "role": "user",
                        "content": "Por favor, resume esta información de forma clara para el cliente."
                    }
                ],
            )
            
            return response.choices[0].message.content or "Gracias por tu consulta. He revisado la información y estoy listo para ayudarte."
            
        except Exception as e:
            logger.error("generate_response_from_tools_error", error=str(e))
            return "He consultado la información solicitada. ¿En qué más puedo ayudarte?"
    
    def _get_tools(self) -> List[Dict]:
        """Definir herramientas disponibles para el agente"""
        return [
            {
                "type": "function",
                "function": {
                    "name": "get_pricing",
                    "description": "Consultar precios de servicios de distribución",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_type": {
                                "type": "string",
                                "enum": ["basic", "professional", "premium", "enterprise"],
                                "description": "Tipo de servicio a consultar"
                            }
                        },
                        "required": ["service_type"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_quote",
                    "description": "Generar cotización personalizada",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "service_type": {
                                "type": "string",
                                "description": "Tipo de servicio"
                            },
                            "num_releases": {
                                "type": "integer",
                                "description": "Número de lanzamientos al año"
                            },
                            "artist_name": {
                                "type": "string",
                                "description": "Nombre del artista"
                            }
                        },
                        "required": ["service_type", "num_releases"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "escalate_to_human",
                    "description": "Transferir conversación a agente humano",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Razón de la transferencia"
                            }
                        },
                        "required": ["reason"]
                    }
                }
            }
        ]
    
    async def _execute_tools(self, tool_calls) -> List[Dict]:
        """Ejecutar llamadas a herramientas"""
        results = []
        
        for tool_call in tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            if function_name == "get_pricing":
                result = await self._get_pricing(arguments["service_type"])
            elif function_name == "generate_quote":
                result = await self._generate_quote(arguments)
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
    
    async def _get_pricing(self, service_type: str) -> Dict:
        """Consultar precios (mock implementation)"""
        pricing = {
            "basic": {
                "monthly": 19.99,
                "yearly": 199.99,
                "features": ["Distribución ilimitada", "Análisis básico", "Soporte email"]
            },
            "professional": {
                "monthly": 49.99,
                "yearly": 499.99,
                "features": ["Todo de Basic", "Pre-saves", "Análisis avanzado", "Soporte prioritario"]
            },
            "premium": {
                "monthly": 99.99,
                "yearly": 999.99,
                "features": ["Todo de Pro", "Marketing tools", "Splits automáticos", "Manager dedicado"]
            }
        }
        
        return pricing.get(service_type, {})
    
    async def _generate_quote(self, params: Dict) -> Dict:
        """Generar cotización personalizada"""
        base_prices = {
            "basic": 19.99,
            "professional": 49.99,
            "premium": 99.99
        }
        
        base_price = base_prices.get(params["service_type"], 19.99)
        num_releases = params.get("num_releases", 12)
        
        # Descuento por volumen
        discount = 0
        if num_releases > 20:
            discount = 0.15
        elif num_releases > 10:
            discount = 0.10
        
        total = base_price * (1 - discount)
        
        return {
            "service": params["service_type"],
            "monthly_price": round(total, 2),
            "yearly_price": round(total * 12 * 0.9, 2),  # 10% descuento anual
            "discount_applied": discount * 100,
            "num_releases": num_releases
        }
    
    def _detect_handoff_need(self, response: str, tool_calls: List[Dict]) -> bool:
        """Detectar si se necesita transferir a otro agente"""
        # Si se llamó a escalate_to_human
        if any(tc["tool"] == "escalate_to_human" for tc in tool_calls):
            return True
        
        # Palabras clave que indican necesidad de soporte técnico
        support_keywords = [
            "lanzamiento bloqueado",
            "problema técnico",
            "error",
            "no funciona",
            "regalías",
            "metadata"
        ]
        
        response_lower = response.lower() if response else ""
        if any(keyword in response_lower for keyword in support_keywords):
            return True
        
        return False