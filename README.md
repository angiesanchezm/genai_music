# 🎵 Multi-Agent Music Distributor

Sistema de agentes autónomos inteligente para disquera digital, utilizando **LangGraph**, **GPT-4o**, y **Pinecone** para ofrecer asistencia automatizada en ventas y soporte técnico a través de **WhatsApp Business API**.

## 🎯 Características Principales

- **2 Agentes Especializados**: Sales y Support con coordinación inteligente
- **Routing Automático**: Clasificación de intenciones y derivación contextual
- **RAG Semántico**: Knowledge base vectorizada con Pinecone
- **Priorización Inteligente**: Análisis de sentimiento + scoring multi-dimensional
- **Escalamiento Automático**: Detecta casos críticos y escala a humanos
- **Seguridad**: Validación de contexto y detección de prompt injection

---

## 🏗️ Arquitectura del Sistema

```
WhatsApp → Twilio → FastAPI Webhook
                        ↓
                  SecurityValidator
                        ↓
                   Orchestrator (LangGraph)
                        ↓
            ┌───────────┴───────────┐
            ↓                       ↓
       Sales Agent            Support Agent
            ↓                       ↓
       [Tools]                  [Tools]
    - get_pricing          - check_release_status
    - generate_quote       - create_ticket
    - escalate             - query_royalties
            ↓                       ↓
            └───────────┬───────────┘
                        ↓
                RAG Service (Pinecone)
                        ↓
              Priority Scorer + Sentiment
                        ↓
                  Response → Twilio
```

### Stack Tecnológico
- **Backend**: Python 3.10 + FastAPI
- **Orquestación Multi-Agente**: LangGraph
- **LLM**: OpenAI GPT-4o
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
git clone https://github.com/angiesanchezm/genai_music.git
cd multi-agent-music-distributor
```

### Paso 2: Configurar Variables de Entorno

```bash
cp .env.example .env
```


### Paso 3: Iniciar con Docker Compose

```bash
docker-compose up --build
```

La aplicación estará disponible en `http://localhost:8000`

### Paso 4: Configurar WhatsApp Webhook

```bash
# Terminal 1: Servidor
python main.py

# Terminal 2: ngrok
ngrok http 8000
```
Copiar URL de ngrok (ej: `https://abc123.ngrok.io`) y configurar en:

**Twilio Console** → **Messaging** → **WhatsApp Sandbox Settings**
- WHEN A MESSAGE COMES IN: `https://abc123.ngrok.io/webhook`
- Method: `POST

### Paso 5: Testing

Health Check
```bash
curl http://localhost:8000/health
```
Probar desde WhatsApp
1. Activar sandbox de Twilio (enviar código de join a +14155238886)
2. Enviar: `"Hola, quiero información sobre planes"`
3. Recibir respuesta automática del agente


---

## 📋 Funcionalidades Principales

### MVP Funcional (Parte 1)

#### 1. **Capa de Seguridad**
- Validación de contexto (rechaza consultas fuera de scope)
- Detección de prompt injection
- Rate limiting básico
- Detección de intenciones maliciosas

#### 2. **Agente de Ventas**
- Explicación de servicios de distribución
- Consulta de precios dinámicos
- Generación de cotizaciones personalizadas
- Escalamiento a humano cuando necesario

#### 3. **Agente de Soporte**
- Consulta de estado de lanzamientos
- Resolución de dudas sobre regalías
- Creación de tickets de soporte
- Ayuda con metadata

#### 4. **Sistema RAG con Pinecone**
- Knowledge base vectorizada
- Retrieval semántico de documentación
- Respuestas contextualizadas

#### 5. **Sistema de Priorización Inteligente**
- Análisis de sentimiento (GPT-4o)
- Detección de implicaciones críticas:
  - Seguridad
  - Financiero
  - Legal
  - Operacional
- Score de prioridad multi-dimensional
- Auto-escalación a humanos

#### 6. **Orquestación con LangGraph**
- Workflow multi-agente
- State management robusto
- Handoff inteligente entre agentes
- Checkpointing de conversaciones

---

## 🔧 Estructura de Carpetas

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
│   └── whatsapp_twilio.py
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
## 📋 System Prompts
### Sales Agent
```
Eres un agente de ventas experto de una disquera digital. Tu misión es:

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

Recuerda: Tu objetivo es convertir leads en clientes, pero siempre con transparencia y honestidad.
```
### Support Agent
```
Eres un agente de soporte técnico experto de una distribuidora musical. Tu misión es:

**RESPONSABILIDADES:**
1. Diagnosticar problemas de lanzamientos (rechazos, demoras)
2. Resolver dudas sobre regalías y reportes de streaming
3. Ayudar con metadata incorrecta (artwork, nombres, ISRC)
4. Gestionar solicitudes de takedowns o claims de copyright
5. Crear tickets de incidencias técnicas
6. Escalar casos complejos a especialistas humanos

**HERRAMIENTAS DISPONIBLES:**
- check_release_status: Verificar estado de un lanzamiento
- create_ticket: Crear ticket de soporte
- query_royalties: Consultar información de regalías
- escalate_to_human: Transferir a agente humano

**ESTILO DE COMUNICACIÓN:**
- Empático y comprensivo
- Técnico pero accesible
- Claro en los pasos a seguir
- Proactivo en crear tickets

**CUÁNDO ESCALAR A HUMANO:**
- Disputas de copyright complejas
- Problemas con pagos/facturación
- Casos que requieren más de 48h de investigación
- Cliente extremadamente frustrado
- Problemas legales

**CONTEXTO RAG:**
Usa el contexto de la knowledge base para diagnosticar problemas comunes y dar soluciones rápidas.

Recuerda: Tu objetivo es resolver problemas rápidamente, pero si no puedes, crea un ticket y escala.
```

---

## 🎯 Casos de Uso

### Ejemplo 1: Consulta de Precios
```
Usuario: Hola, quisiera saber los precios de distribución

Bot: ¡Hola! Tenemos 3 planes principales:

Basic - $19.99/mes
• Distribución ilimitada
• 100% de tus regalías
• Análisis básico

Professional - $49.99/mes  
• Todo de Basic
• Pre-saves
• Análisis avanzado
• Soporte prioritario

Premium - $99.99/mes
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
#### Ejemplo 3: Escalamiento

```
Usuario: "Represento a Bad Bunny, necesitamos un plan enterprise"

[Agent detecta: cliente de alto valor]
[Agent ejecuta: escalate_to_human("high_value_client")]

Agent: "¡Excelente! Para artistas de su nivel, nuestro equipo enterprise te brindará atención especializada. Te estoy conectando con nuestro VP de Ventas ahora mismo. Recibirás una llamada en los próximos 15 minutos."
```

### Ejemplo 4: Cambio de Agente

```
Usuario: "¿Cuánto cuesta el plan básico?"
Bot (Sales): [Responde con precios]

Usuario: "Ok, ya contraté pero mi música no se publicó"
Bot (Support): [Se detecta cambio de contexto]
"Entiendo que ya eres cliente. Déjame ayudarte con el problema...
```

