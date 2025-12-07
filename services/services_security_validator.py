"""
Validación de seguridad y filtrado de contenido
"""
from typing import Dict, Tuple
import re
from openai import OpenAI
from config.settings import settings
import structlog

logger = structlog.get_logger()

class SecurityValidator:
    """Validador de seguridad para mensajes entrantes"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        
        # Patrones de contexto prohibido
        self.off_topic_patterns = [
            r'\b(invertir|inversión|acciones|bolsa|forex)\b',
            r'\b(almuerzo|comida|cena|desayuno|receta)\b',
            r'\b(clima|tiempo|pronóstico)\b',
            r'\b(deporte|fútbol|basketball)\b',
        ]
        
        # Patrones de prompt injection
        self.injection_patterns = [
            r'ignore\s+(previous|all)\s+instructions',
            r'system\s*:',
            r'<\s*system\s*>',
            r'olvida\s+(todo|las\s+instrucciones)',
            r'ignora\s+las\s+reglas',
        ]
    
    async def validate_message(self, message: str, user_phone: str) -> Tuple[bool, str]:
        """
        Validar mensaje entrante
        
        Returns:
            (is_valid, reason)
        """
        # 1. Verificar rate limiting (básico)
        if not await self._check_rate_limit(user_phone):
            return False, "rate_limit_exceeded"
        
        # 2. Detectar prompt injection
        if self._detect_prompt_injection(message):
            logger.warning("prompt_injection_detected", user=user_phone)
            return False, "prompt_injection"
        
        # 3. Validar contexto (fuera de scope)
        if not await self._validate_context(message):
            logger.info("off_topic_message", user=user_phone)
            return False, "off_topic"
        
        # 4. Detectar intencionalidad maliciosa
        if await self._detect_malicious_intent(message):
            logger.warning("malicious_intent_detected", user=user_phone)
            return False, "malicious_intent"
        
        return True, "valid"
    
    def _detect_prompt_injection(self, message: str) -> bool:
        """Detectar intentos de prompt injection"""
        message_lower = message.lower()
        
        for pattern in self.injection_patterns:
            if re.search(pattern, message_lower, re.IGNORECASE):
                return True
        
        return False
    
    async def _validate_context(self, message: str) -> bool:
        """Validar que el mensaje esté en contexto del negocio"""
        message_lower = message.lower()
        
        # Verificar patrones obvios fuera de contexto
        for pattern in self.off_topic_patterns:
            if re.search(pattern, message_lower):
                return False
        
        # Usar GPT-5 para clasificación semántica
        try:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Eres un clasificador de contexto. Determina si el mensaje está relacionado con:
- Distribución musical
- Regalías musicales
- Lanzamiento de música en plataformas
- Soporte técnico musical
- Servicios de disquera

Responde SOLO con 'SI' o 'NO'."""
                    },
                    {
                        "role": "user",
                        "content": f"¿Este mensaje está en contexto?: {message}"
                    }
                ],
                max_tokens=10,
                temperature=0.0
            )
            
            result = response.choices[0].message.content.strip().upper()
            return result == "SI"
            
        except Exception as e:
            logger.error("context_validation_error", error=str(e))
            # En caso de error, permitir el mensaje (fail-open)
            return True
    
    async def _detect_malicious_intent(self, message: str) -> bool:
        """Detectar intencionalidad maliciosa usando GPT-5"""
        try:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Analiza si el mensaje tiene intencionalidad maliciosa:
- Intentos de fraude
- Solicitudes inapropiadas
- Lenguaje abusivo u ofensivo
- Intentos de manipular el sistema

Responde SOLO con 'SI' o 'NO'."""
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                max_tokens=10,
                temperature=0.0
            )
            
            result = response.choices[0].message.content.strip().upper()
            return result == "SI"
            
        except Exception as e:
            logger.error("malicious_detection_error", error=str(e))
            return False
    
    async def _check_rate_limit(self, user_phone: str) -> bool:
        """Verificar límite de tasa (implementación básica)"""
        # TODO: Implementar con cache en memoria o SQLite
        # Por ahora, siempre permitir
        return True
    
    def get_rejection_message(self, reason: str) -> str:
        """Obtener mensaje de rechazo apropiado"""
        messages = {
            "rate_limit_exceeded": "Has enviado demasiados mensajes. Por favor espera un momento.",
            "prompt_injection": "Lo siento, no puedo procesar ese tipo de mensaje.",
            "off_topic": "Hola! Solo puedo ayudarte con temas relacionados a distribución musical, regalías y lanzamientos. ¿En qué puedo asistirte?",
            "malicious_intent": "Lo siento, no puedo ayudarte con eso. ¿Tienes alguna consulta sobre nuestros servicios musicales?"
        }
        
        return messages.get(reason, "Lo siento, no puedo procesar tu mensaje en este momento.")
