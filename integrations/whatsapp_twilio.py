"""
Conector de WhatsApp usando Twilio API
"""
from typing import Dict, Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException
import structlog

logger = structlog.get_logger()

class WhatsAppTwilioConnector:
    """Conector para WhatsApp via Twilio"""
    
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
        
        logger.info(
            "twilio_connector_initialized",
            from_number=from_number
        )
    
    async def send_message(
        self,
        to: str,
        message: str
    ) -> Dict:
        """
        Enviar mensaje de WhatsApp vía Twilio
        
        Args:
            to: Número de teléfono del destinatario (formato: +1234567890)
            message: Contenido del mensaje
            
        Returns:
            Respuesta con el message_id
        """
        try:
            # Formatear números para WhatsApp
            if not to.startswith("whatsapp:"):
                to = f"whatsapp:{to}"
            
            from_number = self.from_number
            if not from_number.startswith("whatsapp:"):
                from_number = f"whatsapp:{from_number}"
            
            # Enviar mensaje
            result = self.client.messages.create(
                body=message,
                from_=from_number,
                to=to
            )
            
            logger.info(
                "twilio_message_sent",
                to=to,
                message_sid=result.sid,
                status=result.status
            )
            
            return {
                "status": "sent",
                "message_id": result.sid,
                "to": to
            }
            
        except TwilioRestException as e:
            logger.error(
                "twilio_send_error",
                error_code=e.code,
                error_message=e.msg,
                to=to
            )
            raise
        except Exception as e:
            logger.error("twilio_send_exception", error=str(e), to=to)
            raise
    
    def parse_webhook_message(self, form_data: Dict) -> Optional[Dict]:
        """
        Parsear mensaje recibido del webhook de Twilio
        
        Args:
            form_data: Datos del formulario enviados por Twilio
            
        Returns:
            {
                "from": str,
                "message_id": str,
                "timestamp": str,
                "text": str,
                "type": str,
                "name": str
            }
        """
        try:
            # Extraer número sin prefijo whatsapp:
            from_number = form_data.get("From", "").replace("whatsapp:", "")
            message_text = form_data.get("Body", "")
            message_sid = form_data.get("MessageSid", "")
            
            if not from_number or not message_text:
                logger.warning("invalid_webhook_data", form_data=form_data)
                return None
            
            parsed = {
                "from": from_number,
                "message_id": message_sid,
                "timestamp": form_data.get("Timestamp", ""),
                "text": message_text,
                "type": "text",
                "name": form_data.get("ProfileName", "Usuario")
            }
            
            logger.info(
                "webhook_message_parsed",
                from_number=parsed["from"],
                message_id=message_sid
            )
            
            return parsed
            
        except Exception as e:
            logger.error("webhook_parse_error", error=str(e))
            return None
    
    async def mark_as_read(self, message_id: str) -> bool:
        """
        Twilio no soporta marcar como leído nativamente
        Esta función existe solo para compatibilidad de interfaz
        """
        logger.debug("mark_as_read_not_supported", message_id=message_id)
        return True