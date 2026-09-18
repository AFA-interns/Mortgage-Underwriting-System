# Property Valuation Agent — India

This repository contains an **Agentic AI Mortgage Underwriting System** specifically designed for Residential Property Valuation in India. It is a decision-support component built with **FastAPI** and **LangGraph**, relying on a hybrid valuation approach (Comparable Sales + Market APIs) rather than an LLM alone.

## Architecture Highlights

```mermaid
flowchart TD
    Client([Client / Underwriting System])
    
    subgraph FastAPI [FastAPI Backend]
        EvaluateAPI["POST /api/v1/valuation/evaluate"]
        ResumeAPI["POST /api/v1/valuation/{thread_id}/resume"]
    end
    
    subgraph LangGraph [LangGraph Agent Workflow]
        Intake["1. Intake Node<br/>(Normalize Input)"]
        Location["2. Location Node<br/>(Geocode via Nominatim)"]
        Comps["3. Comps Node<br/>(Query Comparable DB)"]
        MockAPI["4. External API Node<br/>(Fetch Market Benchmark)"]
        Reconcile["5. Reconcile Node<br/>(Compare Data & Score Risk)"]
        Decision{"Confidence Low?<br/>or High Risk?"}
        Explanation["6. Explanation Node<br/>(Gemini 3.1 Flash Lite)"]
        EndNode(((End)))
    end
    
    Client -->|Submits Property Details| EvaluateAPI
    EvaluateAPI --> Intake
    Intake --> Location
    Location --> Comps
    Comps --> MockAPI
    MockAPI --> Reconcile
    Reconcile --> Decision
    
    Decision -->|"Yes (Review Required)"| Pause(("Interrupt<br/>(MemorySaver)"))
    Pause -.->|Returns Status: PENDING| Client
    
    Client -->|Underwriter Approves| ResumeAPI
    ResumeAPI --> Explanation
    
    Decision -->|"No (High Confidence)"| Explanation
    Explanation --> EndNode
    EndNode -->|Returns Final JSON Package| Client
```

- **LangGraph Orchestration**: Stateful workflow that handles Intake -> Geocoding -> Comps Retrieval -> Market API -> Reconciliation -> Explanation.
- **Dual-Engine Valuation**: Reconciles an internal comparable sales database against an external market valuation benchmark.
- **Human-in-the-Loop (HITL)**: Asynchronous REST endpoints allow the workflow to pause execution when confidence is low, requiring an underwriter to review and approve the valuation before generating the final report.
- **Auditable Explanations**: Uses Google's Gemini LLM (`gemini-3.1-flash-lite`) to generate natural language justifications for the mathematical outputs.

## Setup & Installation

### 1. Requirements
Ensure you have Python 3.10+ installed.

### 2. Environment Setup
```bash
# Clone the repository and cd into the directory
cd property-valuation-agent

# Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Environment Variables
To enable the LLM explanation generator, create a `.env` file in the root directory:
```text
GEMINI_API_KEY="your_google_api_key_here"
```
*(If no API key is provided, the system will safely fallback to a mock explanation string).*

## Running the API

Start the FastAPI server using Uvicorn:
```bash
uvicorn app.main:app --reload
```

Once running, navigate to the interactive API documentation:
**[http://localhost:8000/docs](http://localhost:8000/docs)**

## Testing the Flow (Mock Data)

The repository comes pre-loaded with a `dummy_properties.csv` database containing mock properties in Bangalore and Mumbai, as well as a simulated external valuation API. 

**It is 100% ready to test out of the box.**

You can run the automated integration test to see the LangGraph pause and resume mechanism in action:
```bash
python test_api.py
```

### API Endpoints
- `POST /api/v1/valuation/evaluate`: Triggers the valuation agent. Returns either a finished valuation or a `PENDING_HUMAN_REVIEW` status.
- `POST /api/v1/valuation/{thread_id}/resume`: Allows an underwriter to approve or reject a paused valuation.

## Future Enhancements
- Swap the mock `dummy_properties.csv` with a Vector Database (e.g., ChromaDB/FAISS).
- Swap the mock external API (`app/tools/external_api.py`) with a live integration (e.g., Zapkey, Propstack) or a live web scraper.
