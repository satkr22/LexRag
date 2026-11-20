# LexRAG architecture

This document describes the runtime system, persistence layer, corpus-ingestion path, and retrieval-only evaluation path. It separates the RAG subsystem from the agentic layer so that benchmark results are not interpreted as end-to-end agent results.

## System context

~~~mermaid
flowchart TB
    USER[User] --> WEB[React + Vite web app]
    WEB -->|Supabase auth| AUTH[Supabase authentication]
    WEB -->|Bearer token + query| API[FastAPI backend]

    API --> AGENT[LangGraph legal agent]
    API --> USERDB[(PostgreSQL users, sessions and messages)]
    AGENT --> LLM[Configured chat LLM]
    AGENT --> TOOLS[Legal retrieval tools]
    TOOLS --> RAG[RAG retrieval subsystem]
    RAG --> CORPUS[(Qdrant legal_docs collection)]
    RAG --> ACTS[(Qdrant legal_acts collection)]

    AGENT -->|SSE message, status and metadata events| API
    API --> WEB
~~~

## Runtime request flow

The normal request path starts at POST /agent/chat. Authentication and message persistence are handled by the API layer; the agent owns routing, retrieval decisions, tool use, and response generation.

~~~mermaid
sequenceDiagram
    autonumber
    participant User
    participant Web as React frontend
    participant API as FastAPI /agent/chat
    participant Auth as Supabase JWT
    participant DB as PostgreSQL
    participant Agent as LangGraph agent
    participant Router as Query router
    participant RAG as Hybrid retriever
    participant Qdrant as Qdrant
    participant LLM as Chat LLM

    User->>Web: Submit legal question
    Web->>Auth: Read authenticated session
    Auth-->>Web: Access token
    Web->>API: query + thread_id + bearer token
    API->>Auth: Verify JWT
    Auth-->>API: user identity
    API->>DB: Persist user message
    API->>Agent: Start run(query, thread_id)
    Agent->>Router: Classify and enrich query

    alt Retrieval required
        Router->>RAG: dense query + BM25 terms + category filters
        RAG->>Qdrant: Dense prefetch
        RAG->>Qdrant: Sparse BM25 prefetch
        Qdrant-->>RAG: Candidate sections
        RAG-->>Agent: RRF-ranked statutory context
        opt More context is needed
            Agent->>RAG: Call search_sections tool
            RAG->>Qdrant: Filtered hybrid search
            Qdrant-->>RAG: Additional sections
            RAG-->>Agent: Tool result
        end
    end

    Agent->>LLM: Generate grounded answer
    LLM-->>Agent: Answer and reasoning state
    Agent-->>API: Stream events
    API-->>Web: Server-sent events
    API->>DB: Persist final agent message
~~~

## Agent and RAG boundaries

The agentic system and the RAG system are related but not identical:

~~~mermaid
flowchart LR
    subgraph AG[Agentic system]
        ROUTE[Legal query routing]
        GRAPH[LangGraph state and control flow]
        SELECT[Tool selection]
        ANSWER[Answer generation]
        STREAM[Streaming and conversation state]
        ROUTE --> GRAPH --> SELECT --> ANSWER --> STREAM
    end

    subgraph R[Retrieval-only RAG system]
        ENRICH[Dense query and BM25 keyword enrichment]
        DENSE[Dense vector search]
        SPARSE[Sparse BM25 search]
        FUSE[RRF fusion]
        CONTEXT[Ranked statutory sections]
        ENRICH --> DENSE --> FUSE
        ENRICH --> SPARSE --> FUSE
        FUSE --> CONTEXT
    end

    SELECT --> ENRICH
    CONTEXT --> ANSWER
~~~

The current benchmark exercises the retrieval-only RAG system. It does not exercise the complete path through tool selection, answer generation, streaming, or conversation persistence.

## Query routing and hybrid retrieval

The router produces:

- requires_retrieval: whether the request is a legal information request.
- category_ids: optional legal-domain filters.
- dense_query: a semantically expanded search query.
- bm25_keywords: compact legal terms for lexical search.

The retriever uses both query forms and fuses their candidates:

~~~mermaid
flowchart TB
    Q[User query] --> ROUTER[Query router]
    ROUTER --> DENSEQ[Semantic query]
    ROUTER --> SPARSEQ[BM25 keywords]
    ROUTER --> FILTER[Optional category filter]

    DENSEQ --> DENSEMODEL[BAAI/bge-large-en-v1.5]
    DENSEMODEL --> DV[Dense candidates]
    SPARSEQ --> SPARSEMODEL[Qdrant/bm25]
    SPARSEMODEL --> SV[Sparse candidates]
    FILTER --> DV
    FILTER --> SV

    DV --> RRF[Reciprocal Rank Fusion]
    SV --> RRF
    RRF --> DEDUP[Section-level deduplication]
    DEDUP --> RESULT[Up to five ranked sections]
~~~

The corpus collection stores section payloads such as Act code, section ID, section number, title, text, category, and completeness metadata. The runtime response formats these payloads into section-level results for the agent.

## Corpus ingestion and indexing

Corpus preparation is a batch path separate from online question answering:

~~~mermaid
flowchart LR
    HTML[Statutory HTML pages] --> SCRAPE[Scrape]
    SCRAPE --> PARSE[Parse and normalize]
    PARSE --> MERGE[Merge section fragments]
    MERGE --> PG[(PostgreSQL corpus metadata)]
    MERGE --> CHUNK[Chunk sections]
    CHUNK --> DENSE[Dense embeddings]
    CHUNK --> SPARSE[Sparse BM25 embeddings]
    DENSE --> QD[(Qdrant legal_docs)]
    SPARSE --> QD
    MERGE --> ACT[Act metadata]
    ACT --> QA[(Qdrant legal_acts)]
~~~

The orchestration entry point is backend/app/rag/data_ingestion_pipeline.py. The individual stages live under backend/app/rag/data_ingestion/ and backend/app/rag/vector_embeddings/.

## Retrieval evaluation path

The committed benchmark bypasses the agent and evaluates direct hybrid retrieval:

~~~mermaid
flowchart LR
    QUESTIONS[Reference questions] --> DATASET[Evaluation dataset]
    DATASET --> RETRIEVE[Direct hybrid retriever]
    RETRIEVE --> TOPK[Top five section IDs and contexts]
    TOPK --> COMPARE[Compare with referenced section IDs]
    TOPK --> JUDGE[LLM context-recall judge]
    COMPARE --> METRICS[Recall, precision, Hit@5 and MRR]
    JUDGE --> LLMRECALL[LLM context recall]
    METRICS --> RESULTS[Evaluation JSON, CSV and JSONL]
    LLMRECALL --> RESULTS
~~~

The evaluation dataset contains 163 questions:

- 113 single-reference questions.
- 50 multi-reference questions.
- Questions over BNS 2023, BNSS 2023, and BSA 2023.
- Reference section IDs and reference answer context.
- Retrieved section IDs and retrieved text context.

The current committed results are:

| Metric | Score |
|---|---:|
| ID-based context recall | 89.88% |
| ID-based context precision | 82.45% |
| Hit@5 | 96.32% |
| MRR | 90.85% |
| LLM context recall | 82.54% |

These metrics answer: “Did direct retrieval return the reference legal context?” They do not answer:

- Did the agent decide correctly whether retrieval was needed?
- Did the agent choose the right tool?
- Did the generated answer faithfully use the retrieved sections?
- Were citations complete and legally correct?
- Was the response fast or cost-efficient?

## Main implementation map

| Area | Main files |
|---|---|
| FastAPI application | backend/app/main.py |
| Agent runtime and graph | backend/app/agent/ |
| API routes and streaming | backend/app/api/routes/agent_router.py |
| Query routing and production retrieval | backend/app/rag/retrieval/retriever_main.py |
| Retrieval tools | backend/app/agent/tools/legal_tools.py |
| Corpus ingestion | backend/app/rag/data_ingestion_pipeline.py |
| Embedding and indexing | backend/app/rag/vector_embeddings/ |
| Evaluation orchestration | backend/app/rag/evaluation_pipeline.py |
| Evaluation retriever | backend/app/rag/evaluation/retrrieve/hybrid_retriever.py |
| Evaluation metrics | backend/app/rag/evaluation/ragas/evaluate_comprehensive.py |

## Data stores

| Store | Responsibility |
|---|---|
| PostgreSQL users database | Users, sessions and chat messages |
| PostgreSQL corpus database | Corpus metadata and persisted legal sections |
| Qdrant legal_docs | Section-level dense and sparse retrieval |
| Qdrant legal_acts | Act-level lookup and routing support |
| Local data/ volumes | Development persistence for PostgreSQL and Qdrant |

## Deployment topology

~~~mermaid
flowchart TB
    subgraph COMPOSE[Docker Compose]
        FRONT[frontend container<br/>Vite dev server :5173]
        BACK[backend container<br/>FastAPI :9000]
        POSTGRES[postgres:17]
        QDRANT[qdrant]
    end

    BROWSER[Browser] --> FRONT
    FRONT --> BACK
    BACK --> POSTGRES
    BACK --> QDRANT
    BACK --> LLMAPI[External LLM APIs]
    BACK --> SUPABASE[Supabase auth]
~~~

The backend mounts the application source during development. PostgreSQL and Qdrant use local data volumes defined in docker-compose.yaml.

