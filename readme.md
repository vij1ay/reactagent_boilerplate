# MultiAgent Boilerplate - Orchestrate AI workflows with ReactAgent and modular tools for scalable automation.

## Summary

**MultiAgent Boilerplate is a production-ready framework** for building extensible, tool-driven AI agents. It provides a **ReactAgent Orchestrator** for managing conversational flows, tool interactions, and business logic, with **LangGraph powering the orchestration logic** as a core component. The system is built on **FastAPI for APIs and WebSocket communication, ChromaDB for semantic retrieval, and Redis for state management and checkpointing.**

With the **ReactAgent Orchestrator**, the flow is fully controlled by prompts - from tool calling and validation to enforcing consent and compliance. Adding a new tool or modifying workflows is as simple as updating prompts, making it easier than ever to extend and adapt the system to new requirements.

**The project** is structured so it can run standalone or be plugged into an existing **FastAPI application** with minimal changes, making it highly adaptable. With modular prompts, strict compliance flows, scalable architecture, and **production-grade guardrails**, it accelerates the development of reliable AI assistants for enterprise use cases.

This project demonstrates a **Customer Journey example**, and can be easily adapted to any organization. Simply update the prompts to reflect company offerings and values, enrich case studies and testimonials with your own data, and you’ll have a **live chatbot ready to interact with customers** and even book appointments by integrating scheduling tools with your calendar.

---

## Features

- **AI Agent Orchestration:** Modular agents automate onboarding, expert matching, appointment scheduling, and customer engagement.
- **Tool Integration:** Agents interact with tools for onboarding, specialist search, appointment booking, case studies, testimonials, and conversation summarization.
- **Extensible Prompts:** System prompts enforce business rules, consent protocols, and summarization logic.
- **Strict Protocol Enforcement:** Implements mandatory consent, ID management, and summarization protocols for compliance and reliability.
- **Semantic Search:** ChromaDB powers semantic retrieval of case studies and testimonials.
- **State Management:** Redis-backed state and checkpointing for robust session handling.
- **Persistent Checkpointing:** Conversation state survives restarts via SQLite (or RedisStack when available).
- **WebSocket Real-Time Communication:** FastAPI WebSocket endpoints for live chat and event streaming.
- **Production-Grade Logging:** Centralized, structured logging for traceability.
- **Multi-Provider LLM Support:** Azure OpenAI, OpenAI, Google Gemini, and Ollama — auto-selected from environment variables.
- **Production Guardrails:** Five-layer safety pipeline protecting every stage of the conversation.

---

## Architecture

```mermaid
flowchart TB
    U["👤 User"] -- Interacts with --> UI["Web Chat Interface\nassets/chat.html"]
    UI -- WebSocket / HTTP --> API["FastAPI + WebSocket Server\nfastapi_app.py · chat_handler.py"]

    %% Guardrail Pipeline
    API --> IG["🛡️ Input Guardrail\nguardrails/input_guardrail.py\nSAFE · UNSAFE · PROMPT_INJECTION"]
    IG -- SAFE only --> PG["🔒 Prompt Guardrail\nSafety Rules in System Prompt\nNo PII · No destructive ops · Fallback to I don’t know"]
    PG --> ORCH["🤖 ReactAgent Orchestrator\nagent_tools/planner.py"]

    %% Tool Guardrail wraps all tools
    ORCH -- Guarded tool calls --> TG["🛡️ Tool Guardrail\nguardrails/tool_guardrail.py\nWhitelist · Dangerous pattern blocking"]
    TG --> T1["Onboarding Tool"]
    TG --> T2["Specialist Finder Tool"]
    TG --> T3["Scheduler Tool"]
    TG --> T4["Retriever Tool\nChromaDB"]
    TG --> T5["Summarizer &\nCompliance Tool"]
    TG --> T6["State Tools\nstore · get · clear"]

    %% RAG Guardrail
    T4 --> RG["🛡️ RAG Guardrail\nguardrails/rag_guardrail.py\nGrounding check · I don’t know fallback"]
    RG -- Grounded results --> VS["Chroma Vector Store"]

    %% Document population
    DP["Document Processor\npopulate_casestudies.py\npopulate_testimonials.py"] -- Populates --> VS
    DOCS["Case Studies · Testimonials\n/casestudies · /testimonials"] -- Processed by --> DP

    %% LLM + Output Guardrail
    ORCH -- Generates response --> LLM["Language Model\nAzure OpenAI · OpenAI\nGemini · Ollama"]
    LLM --> OG["🛡️ Output Guardrail\nguardrails/output_guardrail.py\nPydantic schema · Second-pass safety check"]
    OG -- Safe response --> API
    API -- Streams to --> U

    %% Persistence
    API --> CP["Checkpointer\nSQLite (default) · RedisStack (optional)"]
    API --> RD["Redis\nConversation history · Leads"]

    %% Violation logging
    IG & TG & RG & OG --> GL["📋 Guardrail Logger\nguardrails/logger.py\nStructured WARNING logs"]

    %% Styling
    classDef user fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef ui fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef api fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef agent fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef guardrail fill:#fff8e1,stroke:#f57f17,stroke-width:2px,stroke-dasharray:4 2
    classDef tools fill:#ede7f6,stroke:#4527a0,stroke-width:2px
    classDef vector fill:#ffebee,stroke:#b71c1c,stroke-width:2px
    classDef docs fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    classDef llm fill:#e0f2f1,stroke:#00695c,stroke-width:2px
    classDef store fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    classDef log fill:#f9fbe7,stroke:#827717,stroke-width:2px

    U:::user
    UI:::ui
    API:::api
    ORCH:::agent
    IG:::guardrail
    PG:::guardrail
    TG:::guardrail
    RG:::guardrail
    OG:::guardrail
    GL:::log
    VS:::vector
    DP:::docs
    DOCS:::docs
    T1:::tools
    T2:::tools
    T3:::tools
    T4:::tools
    T5:::tools
    T6:::tools
    LLM:::llm
    CP:::store
    RD:::store
```

### Component Reference

| Component | File(s) | Role |
|---|---|---|
| FastAPI + WebSocket | `fastapi_app.py`, `chat_handler.py` | REST and WebSocket endpoints, request routing |
| ReactAgent Orchestrator | `agent_tools/planner.py` | LangGraph agent loop, tool dispatch |
| Input Guardrail | `guardrails/input_guardrail.py` | LLM-based classifier — blocks UNSAFE / PROMPT_INJECTION |
| Prompt Guardrail | `prompts/planner_prompts.py` | System prompt safety rules — no PII, no destructive ops |
| Tool Guardrail | `guardrails/tool_guardrail.py` | Tool whitelist + dangerous pattern detection |
| RAG Guardrail | `guardrails/rag_guardrail.py` | Grounding check — returns "I don’t know" if no relevant docs |
| Output Guardrail | `guardrails/output_guardrail.py` | Pydantic schema validation + second-pass LLM safety check |
| Guardrail Logger | `guardrails/logger.py` | Structured `GUARDRAIL_VIOLATION` warning logs |
| ChromaDB | `chromastore/` | Semantic vector search for case studies and testimonials |
| Checkpointer | `fastapi_app.py` | SQLite (default) or RedisStack — conversation state survives restarts |
| Redis | `utils.py`, `conversations/` | Conversation history and leads storage |
| LLM Utils | `llm_utils.py` | Cached LLM factory — Azure OpenAI → OpenAI → Gemini → Ollama |

---

## Guardrails

This project implements a **five-layer guardrail pipeline** that protects every stage of the agent conversation.

```
User Input
    │
    ▼
┌─────────────────────────────────────────────┐
│  1. INPUT GUARDRAIL                         │
│     Classifies input as SAFE / UNSAFE /     │
│     PROMPT_INJECTION using an LLM call.     │
│     Blocks and logs anything non-SAFE.      │
└────────────────────┬────────────────────────┘
                     │ SAFE only
                     ▼
┌─────────────────────────────────────────────┐
│  2. PROMPT GUARDRAIL                        │
│     Safety Rules enforced in the system     │
│     prompt: no PII exposure, no destructive │
│     ops, respond "I don’t know" if unsure.  │
└────────────────────┬────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  3. TOOL GUARDRAIL                          │
│     Every tool call validated against a     │
│     10-tool whitelist. Inputs scanned for   │
│     dangerous patterns (SQL drops, shell    │
│     commands, path traversal, injections).  │
└────────────────────┬────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  4. RAG GUARDRAIL                           │
│     Chroma retrieval results checked for    │
│     relevance (cosine distance threshold).  │
│     Returns "I don’t know" if no grounded   │
│     context is found — prevents hallucation.│
└────────────────────┬────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────┐
│  5. OUTPUT GUARDRAIL                        │
│     Pydantic schema validates response      │
│     structure and length. A second-pass LLM │
│     safety check scans for PII, credentials │
│     and harmful content. Unsafe responses   │
│     are replaced with a safe fallback.      │
└────────────────────┬────────────────────────┘
                     │
                     ▼
              Safe Response → User

All violations logged as:
GUARDRAIL_VIOLATION | layer=X | thread=Y | reason=Z
```

### Guardrail Files

```
guardrails/
├── __init__.py            # Package exports
├── input_guardrail.py     # Input classification (SAFE / UNSAFE / PROMPT_INJECTION)
├── output_guardrail.py    # Pydantic output schema + second-pass LLM safety check
├── tool_guardrail.py      # Tool whitelist + dangerous pattern blocking
├── rag_guardrail.py       # RAG grounding check (relevance threshold)
├── logger.py              # Structured GUARDRAIL_VIOLATION log helper
└── utils.py               # Shared JSON parsing utility
```

---

## Project Structure

```
.
├── agent_tools/            # AI agent tools (customers, specialists, appointments, etc.)
├── conversations/          # Conversation state and thread management
├── guardrails/             # Five-layer safety pipeline
│   ├── input_guardrail.py  # Input classification
│   ├── output_guardrail.py # Output validation
│   ├── tool_guardrail.py   # Tool whitelist + pattern blocking
│   ├── rag_guardrail.py    # RAG grounding check
│   ├── logger.py           # Violation logger
│   └── utils.py            # Shared JSON parsing
├── websocket/              # WebSocket manager and handlers
├── prompts/                # System and planner prompts
├── data/                   # CSVs and persistent data (appointments, specialists, etc.)
├── chromastore/            # ChromaDB vector stores for semantic search
├── assets/                 # Static files for chat UI
├── fastapi_app.py          # FastAPI application entrypoint
├── llm_utils.py            # LLM and embedding utilities (cached, multi-provider)
├── utils.py                # Utility functions and environment management
├── config.py               # Company and chatbot configuration
├── populate_casestudies.py # Script to populate ChromaDB with case studies
├── populate_testimonials.py # Script to populate ChromaDB with testimonials
└── README.md               # Project documentation
```

---

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   Copy `.env.sample` to `.env` and fill in your credentials:

   ```env
   # LLM Provider — first match wins (Azure → OpenAI → Google → Ollama)
   AZURE_OPENAI_API_KEY=
   AZURE_OPENAI_ENDPOINT=
   AZURE_OPENAI_DEPLOYMENT_NAME=
   AZURE_OPENAI_API_VERSION=2024-02-01

   OPENAI_API_KEY=
   GOOGLE_API_KEY=

   # Redis (optional — for conversation history and leads)
   REDIS_HOST=localhost
   REDIS_PORT=6379

   # Persistent checkpointing (SQLite by default)
   CHECKPOINT_DB_PATH=checkpoints.db
   ```

   Modify `config.py` for company-specific settings (`COMPANY_NAME`, `CHATBOT_NAME`, etc.).

3. **Populate vector databases:**
   Place JSON/txt files in `casestudies/` and `testimonials/`, then run:
   ```bash
   python populate_casestudies.py
   python populate_testimonials.py
   ```

---

## Running the Application

1. **Start the FastAPI server:**
   ```bash
   python fastapi_app.py
   ```

2. **Access the chat interface:**
   - Open your browser to `http://localhost:8000`
   - A new thread is created automatically: `http://localhost:8000/?chat_threadid=<uuid>`
   - This thread ID manages conversation state — conversations **resume after restart** via the SQLite checkpointer.
   - Full message history is stored in Redis: hash `conversation:user`, key = `threadID`.
   - Open multiple tabs to simulate different users or sessions.
   - After appointment booking, a conversation summary is stored in Redis under `leads_generated` (view at `http://localhost:8000/leads_generated`).

---

## Checkpointing & Conversation Persistence

Conversation state is persisted using a three-tier checkpointer strategy:

| Priority | Checkpointer | When used |
|---|---|---|
| 1 | **AsyncRedisSaver** | `REDIS_HOST` set and RedisStack module available |
| 2 | **AsyncSqliteSaver** | Default fallback — persists to `checkpoints.db` |
| 3 | **MemorySaver** | Never used (removed as fallback) |

The SQLite checkpointer ensures conversations survive application restarts without requiring any additional infrastructure.

---

## Screenshots

> Chat Interface<BR>
<img src="assets/screenshots/chat.png" alt="Chat Interface" width="450"/>    <img src="assets/screenshots/chat1.png" alt="Chat Interface 1" width="450"/>

> Sample Flow Onboarding & Appointment Booking<BR>
<img src="assets/screenshots/onboarding.png" alt="Onboarding" width="300"/>  <img src="assets/screenshots/appointment.png" alt="Appointment" width="300"/>  <img src="assets/screenshots/appointment_confirmation.png" alt="Appointment Confirmation" width="300"/>

> Leads Dashboard
<img src="assets/screenshots/leads_generated.png" alt="Leads Generated" width="900"/>

---

## Future Customization

- **Add new tools:** Implement in `agent_tools/` and register with the planner in `agent_tools/planner.py`. Add the tool name to `ALLOWED_TOOLS` in `guardrails/tool_guardrail.py`.
- **Update prompts and business logic:** Edit `prompts/planner_prompts.py`.
- **Tune guardrail thresholds:** Adjust `_RELEVANCE_THRESHOLD` in `guardrails/rag_guardrail.py` or extend `_DANGEROUS_PATTERNS` in `guardrails/tool_guardrail.py`.
- **Integrate new data sources:** Update population scripts and vector database logic.
- **Extend agent capabilities:** Add new flows, protocols, or integrations as needed.

---

## Contributing

Contributions are welcome! Please open issues or submit pull requests for bug fixes, enhancements, or new features. For major changes, discuss proposals in advance.

---

## License

This project is intended for educational and production use and can be adapted for commercial deployments. Please review and comply with all third-party licenses.

