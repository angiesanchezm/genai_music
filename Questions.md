# 📋 Respuestas a Preguntas Clave del Caso Técnico

## Sobre Arquitectura

### 1. ¿Qué stack tecnológico propones y por qué?

#### Stack Elegido

| Componente | Tecnología | Justificación |
|------------|------------|---------------|
| Backend | FastAPI | Alto rendimiento, async nativo |
| Orquestación | LangGraph | State management robusto para multi-agente |
| LLM | GPT-4o | Balance calidad/costo |
| Vector DB | Pinecone | Escalable, serverless |
| WhatsApp | Twilio | Setup rápido, confiable |
| Base de datos | SQLite | Simple para MVP, fácil migrar a PostgreSQL |
| Containerización | Docker | Consistencia entre ambientes |


---

### 2. ¿Cómo manejarías la memoria y el contexto?

#### Memoria en 3 Capas

El agente consultaría capas en este orden:
Capa 1 → contexto inmediato (respuestas rápidas)
Capa 2 → contexto extendido de la conversación
Capa 3 → información estable del cliente

**Capa 1: Sesión Activa (Redis, TTL 24h)**
  - Últimos 10 mensajes
  - Estado actual del agente
  - Metadata temporal (prioridad, sentimiento)
  - Acceso muy rápido (<1 ms)

**Capa 2: Historial Conversacional (Redis, TTL 7 días)**
  - Historial completo de mensajes
  - Handoffs entre agentes
  - Resoluciones previas
  - Acceso rápido (<5 ms)

**Capa 3: Perfil de Cliente (PostgreSQL, persistente)**
  - Datos del cliente (nombre, plan)
  - Historial de releases
  - Tickets cerrados
  - Preferencias
  - Acceso ~10 ms


**. Contexto compartido entre agentes**

Estado completo compartido entre todos los agentes.
Ej:
→ Sales Agent procesa
→ Usuario pregunta algo técnico → Handoff
→ Support Agent ve TODO el state
Responde contextualmente: "Veo que te interesa Premium..."
Info compartida: Historial completo, plan de interés, problemas reportados, sentiment, tool calls.

**Dónde se almacena**
| Dato | Storage | Duración | Velocidad |
|------|---------|----------|-----------|
| Mensajes actuales | LangGraph State (RAM) | Sesión | Instantáneo |
| Checkpoints | MemorySaver (RAM) | App running | <1ms |
| Historial | SQLite | Permanente | 5-10ms |
| Knowledge base | Pinecone | Permanente | 50-100ms |


### 3. ¿Cómo funciona el handoff entre agentes?

#### **Router de 2 etapas:**
**Etapa 1: Clasificación de Intención (GPT-4o)**
- **SALES**: precio, plan, contratar, cotización, onboarding
- **SUPPORT**: error, problema, lanzamiento, regalías, metadata
**Etapa 2: Routing Condicional (LangGraph)**
    # Mantener agente si no hay cambio de contexto
    # Nuevo routing

#### **¿Cuándo se transfiere?**
**Triggers de handoff:**
1. **Explícito**: Agent llama `escalate_to_human()` tool
2. **Implícito**: Detección de keywords técnicos en respuesta
3. **Por prioridad**: `priority_score >= 9.0` → escalar a humano

#### **¿Cómo se transfiere el contexto?**
**State completo se pasa sin modificación:**
    Support recibe state IDÉNTICO
    Puede ver: historial, plan de interés, sentiment, todo

**Ejemplo mensaje de transición**:
```
Sales: "Te transfiero con soporte especializado..."
Support: "Entiendo que tienes un problema. 
         Veo que estabas interesado en Premium. 
         Déjame ayudarte..."
```

---

## Sobre Escalabilidad

### 4. Si mañana el cliente quiere agregar Instagram y Telegram, ¿qué cambia?

#### Cambios Necesarios: MÍNIMOS

**Arquitectura Actual (Preparada para Multicanal)**

```python
# El sistema es independienre al canal de origen
# Todos los canales convergen

┌──────────┐
│ WhatsApp │──┐
└──────────┘  │
              │                           ┌──────────────┐
┌──────────┐  ├──conversation_id+message─►│ Orchestrator │
│ Telegram │──┤                           └──────────────┘
└──────────┘  │                
              │                                   │
┌──────────┐  │                                   ▼
│Instagram │──┤                           ┌──────────────┐
└──────────┘  │                           │    Agents    │
┌──────────┐  │                           └──────────────┘
│   API    │──┘
└──────────┘
```


Solo cambia: 
   - Input adapter (webhook específico)
   - Output adapter (API específica)
   - Formato de conversation_id
```

**Abstracción: Conversation ID**

- Cada canal tiene su formato de conversation_id
- Pero todos convergen al mismo sistema
- El orchestrator no sabe (ni le importa) de dónde viene

---

### 5. Si el volumen de mensajes se multiplica por 10, ¿qué se rompe primero?

#### Cuellos de Botella

**Estado Actual (Capacidad)**

```python
# Setup actual:
- 1 instancia de FastAPI
- OpenAI API (rate limit: 10k RPM)
- ChromaDB local

# Capacidad estimada:
- ~100 mensajes/minuto
- ~6,000 mensajes/hora
- ~144,000 mensajes/día
```

**Cuellos de Botella Identificados (10x = 60k msg/hora)**

```
#1: OpenAI API Rate Limits
Revisión:
- RateLimitError en logs
- Mensajes en cola creciendo
- Timeouts

Solución:
- Upgrade a tier superior en OpenAI
- Implementar cola de mensajes
```

```
#2: Single API Instance
- FastAPI se puede saturar con 10x requests
- CPU/Memory del container se satura

Revision:
- Latencia aumenta >2 segundos
- Event loop bloqueado

Solución:
- Horizontal scaling (3-5 instancias)
- Load balancer (nginx)
-Auto-scaling basado en métricas
```

```
#3: SQLite Store
- Límite**: ~1000 writes/seg
- Rompe en**: 500 mensajes concurrentes

Síntomas:
- Aumento exponencial de latencia
- Database bloqueada

Solución:
- Cambiar a PostgreSQL
- Multiples lecturas simultaneas
```

---

### 6. Si el cliente quiere agregar un tercer agente (Regalías/Pagos), ¿qué tendrías que modificar?

La arquitectura con LangGraph está diseñada para ser **plug-and-play** con nuevos agentes.


**Paso 1: Definir el Agente**
**Paso 2: Crear Herramientas del Agente**
Ej:
- Balance de regalías
- Ganancia por stream
- Retirar fondos

**Paso 3: Actualizar Router**
Enrutar al agente apropiado en base a keywords

**Paso 4: Agregar Nodo al Grafo LangGraph**
Incorporar nodo de agente al grafo

#### Diagrama: Antes vs Después

```
ANTES (2 agentes):
                Router
                  │
         ┌────────┼────────┐
         │                 │
      Sales            Support
         
DESPUÉS (3 agentes):
                Router
                  │
         ┌────────┼────────┬─────────┐
         │        │        │         │
      Sales   Support  Royalties  Human
         │        │        │         │
         └────────┴────────┴─────────┘
              (Handoffs fluidos)
```

#### Lo que no cambia:

```
- Infraestructura (Docker, Redis)
- API endpoints
- Validacion de seguridad
- Análisis de sentimiento
-  Sistema RAG (solo agregar más docs)
- Webhooks de canales
-  Agentes existentes (Sales, Support)
```

---

## Sobre Robustez

### 7. ¿Qué pasa si el LLM falla en medio de una conversación?

#### Estrategia de manejo de fallos

**Nivel 1: Retry con Backoff Exponencial**
Llama al LLM con retry automático.
    Retry strategy:
        - Intento 1: Inmediato
        - Intento 2: Después de 2 segundos
        - Intento 3: Después de 4 segundos
        - Si falla: surge excepción
        
**Nivel 2: Respuestas Pre-definidas (Fallback)**

```python
FALLBACK_RESPONSES = {
    "sales": {
        "greeting": "Hola, soy tu asistente de ventas. ¿En qué puedo ayudarte hoy?",
        "technical_issue": "Disculpa, estoy teniendo dificultades técnicas. "
                          "¿Podrías intentar en unos momentos o prefieres hablar con un humano?",
        "pricing": "Tenemos tres planes: Básico ($19.99), Pro ($49.99) y Label ($99.99). "
                  "¿Sobre cuál te gustaría saber más?",
    },
    "support": {
        "greeting": "Hola, soy tu asistente de soporte. ¿Qué problema necesitas resolver?",
        "technical_issue": "Disculpa las molestias técnicas. "
                          "Voy a conectarte con un agente humano que te ayudará.",
        "status_check": "Para consultar el estado de tu lanzamiento necesito el título. "
                       "¿Puedes compartirlo?",
    }
}
```

**Nivel 3: Escalamiento a humano**

Fallbacks Específicos por Tipo de Error

    # Rate Limit
    openai.RateLimitError: {
        "message": "Estamos experimentando alto volumen. Espera 30 segundos.",
        "action": "retry_delayed",
        "delay": 30
    },
    
    # Timeout
    openai.Timeout: {
        "message": "La solicitud está tomando más tiempo del esperado. "
                  "¿Quieres esperar o hablamos en un momento?",
        "action": "retry_once",
        "escalate_after": 1
    },
    
    # API Error
    openai.APIError: {
        "message": "Estoy teniendo un problema técnico. "
                  "Déjame conectarte con un humano.",
        "action": "escalate_immediate",
        "escalate_after": 0
    }


---

### 8. ¿Cómo sabrías si el agente está funcionando bien?


**1. Métricas de Sistema (Logs estructurados)**

- Latencia promedio: <2 seg (target)
- Error rate: <1% (alert si >5%)
- Throughput: mensajes/seg

**2. Métricas de Calidad del Agente**

QUALITY_TARGETS = {
    "resolution_rate": 0.70,               # 70% resuelto sin humano
    "first_contact_resolution": 0.40,      # 40% en primer contacto
    "avg_messages_to_resolve": 3.0,        # Promedio 3 mensajes
    "escalation_rate": 0.10,               # <10% escalado
    "avg_handoffs_per_conversation": 0.5   # <0.5 handoffs promedio
}


**3. Métricas de Negocio**

BUSINESS_TARGETS = {
    "cost_per_conversation": 0.10,         # <$0.10 por conversación
    "human_hours_saved_per_week": 100,     # >100 horas/semana
    "tickets_automated_percentage": 0.70,  # >70% tickets
    "lead_to_signup_rate": 0.15,           # >15% conversión
    "issue_resolution_time_hours": 2.0     # <2 horas promedio
}
Sistema de Alertas Automáticas basado en metricas


#### Detección Proactiva de Problemas

**1. Health Checks**
**2. Monitoreo sintetico**
test_conversations = [
    "¿Cuánto cuesta?",
    "Tengo un problema"
]
**2. Detección de anomalías**
Traffic < Baseline
Error rate > Baseline

---

### 9. Roadmap Realista de Implementación

#### Fase 1: MVP (2 meses)

**Semanas 1-2: Inicializar**
- Setup infraestructura (FastAPI + Docker)
- Integración WhatsApp (Twilio)
- Base de datos (SQLite)
- Logging estructurado

**Semanas 3-4: Agentes Core**
- Sales Agent (3 tools)
- Support Agent (4 tools)
- Clasificación GPT

**Semanas 5-6: Orquestación**
- LangGraph workflow
- State management
- Handoff entre agentes

**Semanas 7-8: Inteligencia y testing**
- RAG con Pinecone
- Sentiment analysis
- Priority scoring
- Seguridad (validación)

**Entregable**: Sistema funcional, 2 agentes, WhatsApp, 100 conversaciones prueba.

ENTREGABLE MES 1:
Sistema funcional con Router + Sales Agent
WhatsApp funcionando
Documentación básica
Tests unitarios



#### Fase 2: Producción (4 meses)

**Mes 3: Optmizacion Inicial**
- PostgreSQL migration
- Redis
- Automatic Monitoring
- CI/CD

**Mes 4: Features**
- 3er agente: Regalías
- Integración Asana (tickets auto)
- A/B testing de prompts
- Multi-idioma (ES + EN)

**Mes 5: Escala**
- Ejecución de computo distribuida 
- Auto-scaling
- Backup automático diario
- Disaster recovery plan

**Mes 6: Expansión**
- Instagram, telegramm
- Voice incorporation
- Fine-tuning modelo custom
- Analytics predictivo

ENTREGABLE MES 6:
Sistema optimizado con datos reales
Latencia <500ms promedio
Costo reducido 30%
Sistema en producción en la nube

