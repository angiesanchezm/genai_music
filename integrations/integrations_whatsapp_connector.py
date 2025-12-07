"""
Conector de WhatsApp Business API
"""
from typing import Dict, Optional
import httpx
from config.settings import settings
import structlog

logger = structlog.get_logger()

class WhatsAppConnector:
    """Conector para WhatsApp Business API"""
    
    def __init__(self):
        self.api_token = settings.whatsapp_api_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.api_version = settings.whatsapp_api_version
        self.base_url = f"https://graph.facebook.com/{self.api_version}/{self.phone_number_id}"
        
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
    
    async def send_message(
        self,
        to: str,
        message: str,
        message_type: str = "text"
    ) -> Dict:
        """
        Enviar mensaje de WhatsApp
        
        Args:
            to: Número de teléfono del destinatario (formato internacional)
            message: Contenido del mensaje
            message_type: Tipo de mensaje (text, template, etc.)
            
        Returns:
            Respuesta de la API
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": to,
                    "type": message_type,
                    message_type: {
                        "preview_url": False,
                        "body": message
                    }
                }
                
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                
                response.raise_for_status()
                result = response.json()
                
                logger.info(
                    "whatsapp_message_sent",
                    to=to,
                    message_id=result.get("messages", [{}])[0].get("id")
                )
                
                return result
                
        except httpx.HTTPStatusError as e:
            logger.error(
                "whatsapp_send_error",
                status=e.response.status_code,
                error=e.response.text
            )
            raise
        except Exception as e:
            logger.error("whatsapp_send_exception", error=str(e))
            raise
    
    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str = "es",
        components: Optional[list] = None
    ) -> Dict:
        """
        Enviar mensaje de template (para iniciar conversaciones)
        
        Args:
            to: Número de destinatario
            template_name: Nombre del template aprobado
            language_code: Código de idioma
            components: Parámetros del template
        """
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "template",
                    "template": {
                        "name": template_name,
                        "language": {
                            "code": language_code
                        }
                    }
                }
                
                if components:
                    payload["template"]["components"] = components
                
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                    timeout=30.0
                )
                
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            logger.error("whatsapp_template_error", error=str(e))
            raise
    
    async def mark_as_read(self, message_id: str) -> bool:
        """Marcar mensaje como leído"""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "messaging_product": "whatsapp",
                    "status": "read",
                    "message_id": message_id
                }
                
                response = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                    timeout=10.0
                )
                
                response.raise_for_status()
                return True
                
        except Exception as e:
            logger.error("whatsapp_mark_read_error", error=str(e))
            return False
    
    def parse_webhook_message(self, webhook_data: Dict) -> Optional[Dict]:
        """
        Parsear mensaje recibido del webhook
        
        Returns:
            {
                "from": str,
                "message_id": str,
                "timestamp": str,
                "text": str,
                "type": str
            }
        """
        try:
            entry = webhook_data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            
            messages = value.get("messages", [])
            if not messages:
                return None
            
            message = messages[0]
            
            # Extraer información del mensaje
            parsed = {
                "from": message.get("from"),
                "message_id": message.get("id"),
                "timestamp": message.get("timestamp"),
                "type": message.get("type"),
                "text": "",
                "name": value.get("contacts", [{}])[0].get("profile", {}).get("name")
            }
            
            # Extraer texto según tipo de mensaje
            if message.get("type") == "text":
                parsed["text"] = message.get("text", {}).get("body", "")
            elif message.get("type") == "button":
                parsed["text"] = message.get("button", {}).get("text", "")
            elif message.get("type") == "interactive":
                interactive = message.get("interactive", {})
                if interactive.get("type") == "button_reply":
                    parsed["text"] = interactive.get("button_reply", {}).get("title", "")
                elif interactive.get("type") == "list_reply":
                    parsed["text"] = interactive.get("list_reply", {}).get("title", "")
            
            logger.info(
                "webhook_message_parsed",
                from_number=parsed["from"],
                type=parsed["type"]
            )
            
            return parsed
            
        except Exception as e:
            logger.error("webhook_parse_error", error=str(e))
            return None
    
    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """
        Verificar webhook de WhatsApp
        
        Returns:
            Challenge string si es válido, None si no
        """
        verify_token = settings.whatsapp_verify_token
        
        if mode == "subscribe" and token == verify_token:
            logger.info("webhook_verified")
            return challenge
        
        logger.warning("webhook_verification_failed", provided_token=token)
        return None
