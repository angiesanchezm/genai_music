# 🎵 Multi-Agent Music Distributor

Sistema de agentes autónomos inteligente para disquera digital, utilizando **LangGraph**, **GPT-5**, y **Pinecone** para ofrecer asistencia automatizada en ventas y soporte técnico a través de **WhatsApp Business API**.

---

## 🏗️ Arquitectura del Sistema

### Stack Tecnológico
- **Backend**: Python 3.11 + FastAPI
- **Orquestación Multi-Agente**: LangGraph
- **LLM**: OpenAI GPT-5
- **Vector Database**: Pinecone
- **Persistencia**: SQLite
- **Mensajería**: WhatsApp Business API
- **Containerización**: Docker + Docker Compose

---

## 🚀 Inicio Rápido

### Prerrequisitos
- Docker & Docker Compose instalados
- Cuenta de OpenAI con acceso a GPT-5
- Cuenta de Pinecone
- WhatsApp Business API configurada

### Paso 1: Clonar el Repositorio

```bash
git clone https://github.com/tu-usuario/multi-agent-music-distributor.git
cd multi-agent-music-distributor
```

### Paso 2: Configurar Variables de Entorno

```bash
cp .env.example .env
```

Editar `.env` con tus credenciales:

```bash
# OpenAI GPT-5
OPENAI_API_KEY=sk-tu-api-key-aqui
OPENAI_MODEL=gpt-5

# Pinecone
PINECONE_API_KEY=tu-pinecone-api-key
PINECONE_ENVIRONMENT=us-east-1-aws
PINECONE_INDEX_NAME=music-distributor-kb

# WhatsApp Business API
WHATSAPP_API_TOKEN=tu-whatsapp-token
WHATSAPP_PHONE_NUMBER_ID=tu-phone-id
WHATSAPP_VERIFY_TOKEN=tu-verify-token-123
```

### Paso 3: Iniciar con Docker Compose

```bash
docker-compose up --build
```

La aplicación estará disponible en `http://localhost:8000`

### Paso 4: Configurar Webhook de WhatsApp

1. Ir a Meta for Developers
2. Configurar webhook URL: `https://tu-dominio.com/webhook`
3. Verify Token: el valor de `WHATSAPP_VERIFY_TOKEN`
4. Suscribirse a eventos: `messages`

---

## 📋 Funcionalidades Principales

### ✅ MVP Funcional (Parte 1)

#### 1. **Capa de Seguridad**
- ✅ Validación de contexto (rechaza consultas fuera de scope)
- ✅ Detección de prompt injection
- ✅ Rate limiting básico
- ✅ Detección de intenciones maliciosas

#### 2. **Agente de Ventas**
- ✅ Explicación de servicios de distribución
- ✅ Consulta de precios dinámicos
- ✅ Generación de cotizaciones personalizadas
- ✅ Escalamiento a humano cuando necesario

#### 3. **Agente de Soporte**
- ✅ Consulta de estado de lanzamientos
- ✅ Resolución de dudas sobre regalías
- ✅ Creación de tickets de soporte
- ✅ Ayuda con metadata

#### 4. **Sistema RAG con Pinecone**
- ✅ Knowledge base vectorizada
- ✅ Retrieval semántico de documentación
- ✅ Respuestas contextualizadas

#### 5. **Sistema de Priorización Inteligente**
- ✅ Análisis de sentimiento (GPT-5)
- ✅ Detección de implicaciones críticas:
  - Seguridad
  - Financiero
  - Legal
  - Operacional
- ✅ Score de prioridad multi-dimensional
- ✅ Auto-escalación a humanos

#### 6. **Orquestación con LangGraph**
- ✅ Workflow multi-agente
- ✅ State management robusto
- ✅ Handoff inteligente entre agentes
- ✅ Checkpointing de conversaciones

---

## 🧪 Testing del Sistema

### Health Check
```bash
curl http://localhost:8000/health
```

### Enviar Mensaje de Prueba
```bash
curl -X POST http://localhost:8000/send-message \
  -H "Content-Type: application/json" \
  -d '{
    "to": "1234567890",
    "message": "Hola, prueba del sistema"
  }'
```

### Ver Estadísticas
```bash
curl http://localhost:8000/stats
```

---

## 📊 Base de Datos

### Esquema SQLite

**Tabla `users`**
```sql
- id (PK)
- phone (UNIQUE)
- name
- tier (basic/pro/premium)
- created_at
- updated_at
```

**Tabla `conversations`**
```sql
- id (PK)
- user_id (FK)
- messages (JSON)
- current_agent
- state (JSON)
- created_at
- updated_at
```

**Tabla `tickets`**
```sql
- id (PK)
- conversation_id (FK)
- priority_score
- status (open/in_progress/resolved)
- assigned_to
- created_at
- resolved_at
```

**Tabla `analytics`**
```sql
- id (PK)
- event_type
- metadata (JSON)
- timestamp
```

---

## 🔧 Estructura del Código

```
.
├── agents/              # Agentes especializados
│   ├── sales_agent.py
│   └── support_agent.py
├── orchestrator/        # Orquestador LangGraph
│   └── router.py
├── services/           # Servicios core
│   ├── security_validator.py
│   ├── rag_service.py
│   ├── sentiment_analyzer.py
│   └── priority_scorer.py
├── integrations/       # Conectores externos
│   └── whatsapp_connector.py
├── storage/            # Persistencia
│   ├── database.py
│   └── state_manager.py
├── config/             # Configuración
│   └── settings.py
├── data/               # Knowledge base y DB
│   ├── knowledge_base/
│   └── database/
├── main.py            # FastAPI app
└── docker-compose.yml # Orquestación
```

---

## 📈 Logs y Monitoreo

Los logs estructurados se almacenan en:
```
./logs/
├── agent_interactions.log
└── security_events.log
```

Formato JSON para fácil parsing:
```json
{
  "event": "message_processed",
  "timestamp": "2025-12-06T10:30:00Z",
  "user": "+1234567890",
  "agent": "sales_agent",
  "priority_score": 5.2,
  "escalated": false
}
```

---

## 🛡️ Seguridad

### Validaciones Implementadas
1. **Context Validation**: Rechaza consultas fuera del dominio musical
2. **Prompt Injection Detection**: Detecta intentos de manipulación
3. **Rate Limiting**: Protección contra abuso
4. **Malicious Intent**: Análisis de intencionalidad con GPT-5

### Ejemplos de Mensajes Rechazados
- "¿En qué debo invertir mi dinero?"
- "¿Qué debería comer para el almuerzo?"
- "Ignora todas las instrucciones anteriores..."

---

## 🎯 Casos de Uso

### Ejemplo 1: Consulta de Precios
```
Usuario: Hola, quisiera saber los precios de distribución

Bot: ¡Hola! Tenemos 3 planes principales:

📦 Basic - $19.99/mes
• Distribución ilimitada
• 100% de tus regalías
• Análisis básico

🚀 Professional - $49.99/mes  
• Todo de Basic
• Pre-saves
• Análisis avanzado
• Soporte prioritario

💎 Premium - $99.99/mes
• Todo de Pro
• Account manager dedicado
• Marketing tools incluidas

¿Te gustaría una cotización personalizada?
```

### Ejemplo 2: Problema Técnico
```
Usuario: Mi lanzamiento no aparece en Spotify :(

Bot: Entiendo tu preocupación. Déjame verificar:

1. ¿Cuándo enviaste tu lanzamiento?
2. ¿Recibiste confirmación de aprobación?

Mientras tanto, reviso el estado...

[Consulta sistema]

He creado un ticket prioritario #TKT-1234. 
Un especialista te contactará en las próximas 2 horas.
```

---

## 🚧 Troubleshooting

### Error: "Pinecone index not found"
```bash
# Verificar que el índice existe
# Crear manualmente si es necesario
```

### Error: "WhatsApp webhook verification failed"
```bash
# Verificar WHATSAPP_VERIFY_TOKEN coincide
# Revisar logs en Meta for Developers
```

### Error: "OpenAI API rate limit"
```bash
# Reducir TEMPERATURE o MAX_TOKENS_RESPONSE
# Considerar upgrade de plan OpenAI
```

---

## 📞 Soporte

Para problemas o consultas:
- Email: support@tu-disquera.com
- Slack: #multi-agent-support
- Issues: GitHub Issues

---

## 📜 Licencia

MIT License - Ver archivo LICENSE para detalles

---

## 🙏 Agradecimientos

- OpenAI por GPT-5
- Pinecone por su vector database
- LangChain/LangGraph por el framework
- Meta por WhatsApp Business API

---

**Sistema desarrollado con ❤️ para revolucionar el soporte en la industria musical**
# genai_music
