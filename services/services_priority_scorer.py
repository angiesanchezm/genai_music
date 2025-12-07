"""
Sistema de scoring de prioridad multi-dimensional
"""
from typing import Dict, List
from openai import OpenAI
from config.settings import settings
import json
import structlog

logger = structlog.get_logger()

class PriorityScorer:
    """Calculador de score de prioridad para escalamiento"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
    
    async def calculate_priority(
        self,
        message: str,
        sentiment_analysis: Dict,
        conversation_history: List[Dict] = None
    ) -> Dict:
        """
        Calcular score de prioridad multi-dimensional
        
        Returns:
            {
                "priority_score": 0-10,
                "should_escalate": bool,
                "escalation_reason": str,
                "implications": {
                    "security": 0-10,
                    "financial": 0-10,
                    "legal": 0-10,
                    "operational": 0-10
                },
                "recommended_action": str
            }
        """
        try:
            # Detectar implicaciones críticas
            implications = await self._detect_critical_implications(message)
            
            # Calcular score base de sentimiento
            sentiment_score = self._sentiment_to_score(sentiment_analysis)
            
            # Calcular score de implicaciones
            implications_score = max(implications.values()) if implications else 0
            
            # Score final ponderado
            priority_score = (
                sentiment_score * 0.4 +  # 40% sentimiento
                implications_score * 0.6  # 60% implicaciones críticas
            )
            
            # Determinar si escalar
            should_escalate = (
                priority_score >= settings.priority_threshold_high or
                implications_score >= 8.0 or
                sentiment_analysis.get("urgency") == "critical"
            )
            
            # Generar razón de escalamiento
            escalation_reason = self._generate_escalation_reason(
                priority_score,
                sentiment_analysis,
                implications
            )
            
            # Acción recomendada
            recommended_action = self._get_recommended_action(priority_score)
            
            result = {
                "priority_score": round(priority_score, 2),
                "should_escalate": should_escalate,
                "escalation_reason": escalation_reason,
                "implications": implications,
                "recommended_action": recommended_action
            }
            
            logger.info(
                "priority_calculated",
                score=result["priority_score"],
                should_escalate=should_escalate
            )
            
            return result
            
        except Exception as e:
            logger.error("priority_calculation_error", error=str(e))
            return {
                "priority_score": 5.0,
                "should_escalate": False,
                "escalation_reason": "",
                "implications": {},
                "recommended_action": "respond"
            }
    
    async def _detect_critical_implications(self, message: str) -> Dict[str, float]:
        """Detectar implicaciones críticas usando GPT-5"""
        try:
            response = self.client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {
                        "role": "system",
                        "content": """Analiza el mensaje y evalúa implicaciones críticas (score 0-10):

{
  "security": 0-10,  // Fraude, acceso no autorizado, violación de seguridad
  "financial": 0-10, // Disputas de pago, problemas de facturación, pérdidas monetarias
  "legal": 0-10,     // Copyright, contratos, violaciones legales
  "operational": 0-10 // Lanzamientos bloqueados, servicios caídos, problemas técnicos críticos
}

Score alto (8-10) = Requiere atención inmediata
Score medio (5-7) = Importante pero no urgente
Score bajo (0-4) = Sin implicaciones críticas"""
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            return json.loads(response.choices[0].message.content)
            
        except Exception as e:
            logger.error("implications_detection_error", error=str(e))
            return {
                "security": 0,
                "financial": 0,
                "legal": 0,
                "operational": 0
            }
    
    def _sentiment_to_score(self, sentiment_analysis: Dict) -> float:
        """Convertir análisis de sentimiento a score numérico"""
        sentiment_scores = {
            "very_negative": 9.0,
            "negative": 7.0,
            "neutral": 5.0,
            "positive": 3.0
        }
        
        urgency_scores = {
            "critical": 10.0,
            "high": 8.0,
            "medium": 5.0,
            "low": 2.0
        }
        
        sentiment_score = sentiment_scores.get(
            sentiment_analysis.get("sentiment", "neutral"),
            5.0
        )
        
        urgency_score = urgency_scores.get(
            sentiment_analysis.get("urgency", "low"),
            2.0
        )
        
        frustration_score = sentiment_analysis.get("frustration_level", 5.0)
        
        # Promedio ponderado
        return (sentiment_score * 0.3 + urgency_score * 0.4 + frustration_score * 0.3)
    
    def _generate_escalation_reason(
        self,
        priority_score: float,
        sentiment_analysis: Dict,
        implications: Dict
    ) -> str:
        """Generar razón de escalamiento"""
        if priority_score < settings.priority_threshold_high:
            return ""
        
        reasons = []
        
        # Sentimiento
        if sentiment_analysis.get("sentiment") == "very_negative":
            reasons.append("cliente muy insatisfecho")
        
        if sentiment_analysis.get("urgency") == "critical":
            reasons.append("urgencia crítica")
        
        if sentiment_analysis.get("frustration_level", 0) >= 8:
            reasons.append("alta frustración")
        
        # Implicaciones
        for implication_type, score in implications.items():
            if score >= 8.0:
                reasons.append(f"implicación {implication_type} crítica")
        
        return ", ".join(reasons) if reasons else "score de prioridad alto"
    
    def _get_recommended_action(self, priority_score: float) -> str:
        """Determinar acción recomendada según score"""
        if priority_score >= settings.priority_threshold_critical:
            return "immediate_escalation"
        elif priority_score >= settings.priority_threshold_high:
            return "escalate_after_response"
        elif priority_score >= 5.0:
            return "respond_and_monitor"
        else:
            return "respond"
