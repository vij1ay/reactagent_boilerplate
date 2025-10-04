# MultiAgent Boilerplate - Orchestrate AI workflows with ReactAgent and modular tools for scalable automation.

## Summary

**MultiAgent Boilerplate is a production-ready framework** for building extensible, tool-driven AI agents. It provides a **ReactAgent Orchestrator** for managing conversational flows, tool interactions, and business logic, with **LangGraph powering the orchestration logic** as a core component. The system is built on **FastAPI for APIs and WebSocket communication, ChromaDB for semantic retrieval, and Redis for state management and checkpointing.**

With the **ReactAgent Orchestrator**, the flow is fully controlled by prompts - from tool calling and validation to enforcing consent and compliance. Adding a new tool or modifying workflows is as simple as updating prompts, making it easier than ever to extend and adapt the system to new requirements.

**The project** is structured so it can run standalone or be plugged into an existing **FastAPI application** with minimal changes, making it highly adaptable. With modular prompts, strict compliance flows, and scalable architecture, it accelerates the development of reliable AI assistants for enterprise use cases.

This project demonstrates a **Customer Journey example**, and can be easily adapted to any organization. Simply update the prompts to reflect company offerings and values, enrich case studies and testimonials with your own data, and you’ll have a **live chatbot ready to interact with customers** and even book appointments by integrating scheduling tools with your calendar.

---

## Features

- **AI Agent Orchestration:** Modular agents automate onboarding, expert matching, appointment scheduling, and customer engagement.
- **Tool Integration:** Agents interact with tools for onboarding, specialist search, appointment booking, case studies, testimonials, and conversation summarization.
- **Extensible Prompts:** System prompts enforce business rules, consent protocols, and summarization logic.
- **Strict Protocol Enforcement:** Implements mandatory consent, ID management, and summarization protocols for compliance and reliability.
- **Semantic Search:** ChromaDB powers semantic retrieval of case studies and testimonials.
- **State Management:** Redis-backed state and checkpointing for robust session handling.
- **WebSocket Real-Time Communication:** FastAPI WebSocket endpoints for live chat and event streaming.
- **Production-Grade Logging:** Centralized, structured logging for traceability.

---

## Architecture

```mermaid
flowchart TB
    U["User"] -- Interacts with --> UI["Web Chat Interface<br>assets/chat.html"]
    UI -- HTTP Requests/WebSocket --> API["FastAPI Server<br>fastapi_app.py,chat_handler.py"]
    API -- Orchestration --> ORCH["ReactAgent Orchestrator<br>planner.py"]

    %% Vector Store + Docs
    T4 -- Semantic Search --> VS["Chroma Vector Store"]
    DP["Document Processor<br>populate_casestudies.py / testimonials.py"] -- Populates --> VS
    DOCS["Case Studies, Testimonials"] -- Processed by --> DP

    %% Agent Tools
    ORCH -- Uses --> T1["Onboarding Tool"]
    ORCH -- Uses --> T2["Specialist Finder Tool"]
    ORCH -- Uses --> T3["Scheduler Tool"]
    ORCH -- Uses --> T4["Retriever Tool<br>(ChromaDB)"]
    ORCH -- Uses --> T5["Summarizer & Compliance Tool"]

    %% Final LLM Output
    ORCH -- Generates Responses with --> LLM["Language Model"]
    LLM -- Reply to User --> U

    %% Styling
    U:::user
    UI:::ui
    API:::api
    ORCH:::agent
    VS:::vector
    DP:::docs
    DOCS:::docs
    T1:::tools
    T2:::tools
    T3:::tools
    T4:::tools
    T5:::tools
    LLM:::llm

    %% Class Definitions
    classDef user fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef ui fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef api fill:#e8f5e8,stroke:#1b5e20,stroke-width:2px
    classDef agent fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef tools fill:#ede7f6,stroke:#4527a0,stroke-width:2px
    classDef vector fill:#ffebee,stroke:#b71c1c,stroke-width:2px
    classDef docs fill:#f1f8e9,stroke:#33691e,stroke-width:2px
    classDef llm fill:#e0f2f1,stroke:#00695c,stroke-width:2px
```

- **FastAPI**: Serves REST and WebSocket endpoints for chat and event streaming.
- **LangGraph ReactAgent**: Orchestrates agent logic, tool calls, and prompt management.
- **ChromaDB**: Provides semantic search for case studies and testimonials.
- **Redis**: Manages state, session history, and checkpointing.
- **WebSocketManager**: Handles real-time client connections and message broadcasting.
- **Planner Prompts**: Enforce business rules, consent, ID management, and summarization protocols.

---

## Project Structure

```
.
├── agent_tools/           # AI agent tools (customers, specialists, appointments, etc.)
├── conversations/         # Conversation state and thread management
├── websocket/             # WebSocket manager and handlers
├── prompts/               # System and planner prompts
├── data/                  # CSVs and persistent data (appointments, specialists, etc.)
├── chromastore/           # ChromaDB vector stores for semantic search
├── assets/                # Static files for chat UI
├── fastapi_app.py         # FastAPI application entrypoint
├── llm_utils.py           # LLM and embedding utilities
├── utils.py               # Utility functions and environment management
├── config.py              # Company and chatbot configuration
├── populate_casestudies.py # Script to populate ChromaDB with case studies
├── populate_testimonials.py # Script to populate ChromaDB with testimonials
└── README.md              # Project documentation
```

---

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   - Create a `.env` file with required keys (OpenAI, Google, Redis, etc.).
   - Modify config in `config.py` for company-specific settings (CompanyName, ChatbotName, etc.).

3. **Populate vector databases:**
    - Add Case Studies and Testimonials to ChromaDB by placing JSON/txt files in the `casestudies/` and `testimonials/` directories respectively and populate by running:
      
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
   - The browser will redirect with a new chat thread like. `http://localhost:8000/?chat_threadid=5d791107-957b-46f4-adfd-b25c1d60a612`
   - This thread ID is used to manage conversation state.
   - Can see the full message history in the redis hash - `conversation:user` and key is the `threadID`. (In this project UserID is always "default" for simplicity.)
   - You can open multiple browser tabs to simulate different users or sessions.
   - The conversation will be summarized post the appointment booking and the summary will be stored in the redis hash - `leads_generated`. (access http://localhost:8000/leads_generated)

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

- **Add new tools:** Implement in `agent_tools/` and register with the planner `agent_tools/planner.py`.
- **Update prompts and business logic:** Edit `prompts/planner_prompts.py`.
- **Integrate new data sources:** Update population scripts and vector database logic.
- **Extend agent capabilities:** Add new flows, protocols, or integrations as needed by adding new tools.

---

## Contributing

Contributions are welcome! Please open issues or submit pull requests for bug fixes, enhancements, or new features. For major changes, discuss proposals in advance.

---

## License



This project is intended for production use and can be adapted for commercial deployments. Please review and comply with all third-party licenses

