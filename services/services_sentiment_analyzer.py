"""
Análisis de sentimiento y detección de urgencia
"""
from typing import Dict, List
from openai import OpenAI
from config.settings import settings
import json
import structlog

logger = structlog.get_logger()

class SentimentAnalyzer:
    """Analizador de sentimiento usando GPT-5"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
    
    async def analyze(self, message: str, conversation_history: List[Dict] = None) -> Dict:
        """
        Analizar sentimiento y urgencia del mensaje
        
        Returns:
            {
                "sentiment": "positive|neutral|negative|very_negative",
                "urgency": "low|medium|high|critical",
                "frustration_level": 0-10,
                "confidence": 0-1
            }
        """
        try:
            # Construir contexto de conversación
            context = ""
            if conversation_history:
                context = "\n".join([
                    f"{msg['role']}: {msg['content']}" 
                    for msg in conversation_history[-3:]  # Últimos 3 mensajes
                ])
            
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Eres un analizador de sentimiento experto. Analiza el mensaje y retorna un JSON con:
{
  "sentiment": "positive|neutral|negative|very_negative",
  "urgency": "low|medium|high|critical",
  "frustration_level": 0-10,
  "confidence": 0-1,
  "indicators": ["lista de indicadores detectados"]
}

Considera:
- Palabras clave de urgencia: "urgente", "rápido", "ya", "ahora"
- Signos de frustración: repetición, mayúsculas, exclamaciones múltiples
- Tono emocional: quejas, insatisfacción, amenazas
- Contexto conversacional previo"""
                    },
                    {
                        "role": "user",
                        "content": f"Contexto previo:\n{context}\n\nMensaje actual:\n{message}"
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            
            logger.info(
                "sentiment_analyzed",
                sentiment=result.get("sentiment"),
                urgency=result.get("urgency"),
                frustration=result.get("frustration_level")
            )
            
            return result
            
        except Exception as e:
            logger.error("sentiment_analysis_error", error=str(e))
            # Retornar análisis neutral en caso de error
            return {
                "sentiment": "neutral",
                "urgency": "low",
                "frustration_level": 5,
                "confidence": 0.5,
                "indicators": []
            }
