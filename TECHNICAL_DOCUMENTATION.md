# Mosam CEDEAO Technical Documentation

## 1. Overview

Mosam is a full-stack tariff classification assistant for CEDEAO/TEC/SH workflows.
It combines:

- a FastAPI backend for classification, history, users, audit, and admin actions
- a Next.js frontend for the end-user classifier, history views, and administration
- Supabase for authentication and PostgreSQL storage
- Redis-compatible caching for classification results
- a RAG pipeline backed by FAISS and tariff reference data

The production direction in this repository is backend API + frontend web app.
The older Streamlit-era flow is no longer the primary interface.

## 2. Repository Layout

### Backend

- `sam/api.py`: FastAPI app, request models, endpoints, auth helpers, admin logic
- `sam/rag.py`: main retrieval and generation pipeline
- `sam/product_identification.py`: optional pre-classification product enrichment
- `sam/decision_engine.py`: decision synthesis from final classification state
- `sam/cache.py`: classification cache helpers
- `sam/db.py`: SQLAlchemy engine and DB session management
- `sam/config/settings.py`: environment loading and runtime settings
- `sam/tariff_*.py`: tariff labels, notes, rates, metadata, and rules
- `sam/classification_*.py`: completeness, coherence, progress, source, and risk helpers
- `sam/openai_web_search.py`: optional web-search-assisted product identification
- `sam/rgi/`: RGI pipeline helpers and types
- `sam/tests/`: backend test suites and campaign scripts

### Frontend

- `frontend/src/app/page.tsx`: main classification UI
- `frontend/src/app/historique/page.tsx`: personal history page
- `frontend/src/app/admin/page.tsx`: admin dashboard
- `frontend/src/app/admin/historique/page.tsx`: global history view
- `frontend/src/app/admin/logs/page.tsx`: audit log view
- `frontend/src/app/admin/parametres/page.tsx`: settings page
- `frontend/src/app/api/mosam/[[...path]]/route.ts`: reverse proxy to the backend
- `frontend/src/app/api/auth/session/route.ts`: stores and clears Supabase access-token cookies
- `frontend/src/app/api/cron/supabase-keepalive/route.ts`: Vercel cron keepalive for Supabase auth
- `frontend/src/lib/`: client helpers for API calls, Supabase, logging, and streaming
- `frontend/src/components/`: reusable UI panels and dialogs

### Deployment

- `Dockerfile`: backend container image
- `deploy/oci-backend.sh`: Oracle Cloud VM deployment helper
- `deploy/mosam-api.env.example`: environment template for backend deployment
- `frontend/vercel.json`: Vercel cron configuration

## 3. Runtime Architecture

### Request Flow

1. The user opens the Next.js app.
2. Middleware protects the main routes and checks the Supabase access token.
3. The frontend sends classification or admin requests to the backend API.
4. The backend validates the request, enriches the input, runs retrieval and RGI logic, and calls OpenAI when needed.
5. Results are normalized, cached when appropriate, and stored in Supabase/Postgres.
6. The frontend renders structured results, history, validation actions, and admin controls.

### Key Design Choice

The backend does not just return raw LLM output. It applies:

- tariff metadata lookup
- candidate position filtering
- subposition resolution
- completeness and risk enrichment
- RGI tracing and decision synthesis

This means the final response is shaped by the domain pipeline, not only by model text generation.

## 4. Backend Architecture

### `sam/api.py`

This is the main entry point of the backend. It creates the FastAPI app, configures CORS, defines request/response models, and exposes the API surface.

The file also contains:

- alias normalization cache and normalization alias table bootstrap
- chapter-to-section normalization from HS code
- validation and bulk validation payloads
- history exports
- user CRUD
- audit log endpoints
- admin cache controls

### `sam/config/settings.py`

This module loads `.env` from the repo root and optionally `.env.local` from the frontend when a JWT secret is missing.

Important settings include:

- OpenAI models
- Supabase DB connection string
- Supabase Auth credentials
- Redis credentials
- product identification toggle
- web search toggle and timeouts
- retrieval sizes for FAISS and candidate positions

### `sam/db.py`

This module builds the SQLAlchemy engine and session factory.

Operational notes:

- it forces `sslmode=require`
- it prefers `SUPABASE_DB_POOLER_URL` over `SUPABASE_DB_URL`
- it warns about Supabase direct-host and IPv6-only connectivity issues
- it disables query caching when using the transaction pooler

### `sam/rag.py`

This is the core classification engine.

It is responsible for:

- loading tariff sources and PDF content
- chunking and retrieval using FAISS
- calling OpenAI
- shaping classification narratives and structured output
- handling assistant/meta questions separately from product classification
- candidate attachment and reranking

### `sam/product_identification.py`

This optional pre-processing agent enriches short or ambiguous product descriptions before classification.

It can:

- detect whether a query needs enrichment
- infer the input type
- generate a richer product description
- optionally use OpenAI web search for extra context

### `sam/decision_engine.py`

This module transforms the final classification state into a structured decision object.

It is used to synthesize:

- product identity
- code selection
- chapter selection
- classification confidence
- criteria trace
- RGI trace

### Supporting backend modules

- `sam/candidate_set_enforcer.py`: limits and attaches allowed position candidates
- `sam/tariff_labels.py`: label lookups and HS/TEC resolution
- `sam/tariff_metadata.py`: section/chapter names
- `sam/tariff_rates.py`: duty and tax rate enrichment
- `sam/tariff_notes.py`: chapter notes and title indexes
- `sam/tariff_position_rules.py`: surface-sensitive and position rule helpers
- `sam/classification_*`: completeness, risk, source, coherence, and progress helpers
- `sam/cache.py`: result cache controls
- `sam/openai_web_search.py`: Responses API web search support

## 5. Backend API Surface

### Health and classification

- `GET /health`
- `POST /classify`
- `POST /classify/stream`
- `POST /classify/file`

### Admin cache and aliases

- `GET /admin/cache/classify/status`
- `PATCH /admin/cache/classify/status`
- `DELETE /admin/cache/classify`
- `GET /admin/normalization-aliases`
- `POST /admin/normalization-aliases`
- `PATCH /admin/normalization-aliases/{alias_id}`
- `DELETE /admin/normalization-aliases/{alias_id}`

### History

- `GET /dossiers`
- `GET /history`
- `GET /history.csv`
- `GET /admin/history.csv`

### Users

- `GET /users`
- `GET /users.csv`
- `POST /users`
- `PATCH /users/{user_id}`
- `DELETE /users/{user_id}`
- `POST /users/{user_id}/reset-password`

### Audit

- `GET /audit-logs`
- `GET /audit-logs.csv`

### Common patterns

- Admin routes depend on bearer-token validation.
- CSV endpoints mirror the JSON endpoints and are intended for exports.
- Classification validation writes additional metadata such as risk, justification, product identification, and dossier association.

## 6. Frontend Architecture

### Root layout

`frontend/src/app/layout.tsx` defines the shared metadata, viewport settings, and the global page shell.

### Middleware

`frontend/middleware.ts` protects:

- `/`
- `/historique`
- `/admin`

It checks for the `sb-access-token` cookie and validates the token against Supabase before allowing access.

### Main UI pages

- `/`: classification page with description input, table entry, file upload placeholder, progress panel, structured results, validation, and copy-to-clipboard output
- `/historique`: user-specific history with filters and CSV export
- `/admin`: user management and high-level stats
- `/admin/historique`: global history view for administrators
- `/admin/logs`: audit trail
- `/admin/parametres`: configuration page

### API client strategy

The frontend uses:

- `frontend/src/lib/apiBase.ts` to choose the backend base URL
- `frontend/src/app/api/mosam/[[...path]]/route.ts` as a proxy when the app is hosted on Vercel
- `frontend/src/lib/supabaseClient.ts` for auth/session state
- `frontend/src/app/api/auth/session/route.ts` to persist access tokens in an HTTP-only cookie

## 7. Data and Persistence

### Supabase / PostgreSQL

The app expects:

- a `public.users` table
- a `public.classifications` table
- a `public.audit_logs` table
- dossier/history relationships
- optional alias tables for normalization

The backend also creates or reads auxiliary data such as:

- normalization aliases
- classification cache keys
- audit log entries

### Local repository data

The repo contains local assets used by the backend and tests:

- `sam/indexFaiss/local_index.faiss`
- `sam/chunks.json`
- `sam/users.json`
- `sam/testprompt*.txt`
- `sam/test_multi_produits.txt`
- tariff PDFs under `sam/contrat/`

## 8. Environment Variables

### Backend

Minimum variables used by the backend:

- `OPENAI_API_KEY`
- `MOSAM_MODEL`
- `MOSAM_IDENTIFICATION_MODEL`
- `MOSAM_CLASSIFICATION_MODEL`
- `EMBEDDING_MODEL`
- `SUPABASE_DB_URL`
- `SUPABASE_DB_POOLER_URL`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `UPSTASH_REDIS_REST_URL`
- `UPSTASH_REDIS_REST_TOKEN`
- `MOSAM_PRODUCT_IDENTIFICATION_ENABLED`
- `MOSAM_WEB_SEARCH_ENABLED`
- `MOSAM_WEB_SEARCH_MODEL`
- `MOSAM_WEB_SEARCH_CONTEXT_SIZE`
- `MOSAM_WEB_SEARCH_TIMEOUT_SECONDS`
- `MOSAM_FAISS_TOP_K`
- `MOSAM_MAX_CANDIDATE_POSITIONS`

### Frontend

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `MOSAM_API_UPSTREAM` for the Vercel proxy
- `CRON_SECRET` for the keepalive route

### Notes

- `NEXT_PUBLIC_API_BASE_URL` defaults to `http://localhost:8000` in development.
- On Vercel, the frontend can proxy requests through `/api/mosam`.
- The backend prefers the Supabase session pooler connection string on IPv4-only environments.

## 9. Local Development

### Backend

Typical local startup:

```bash
python -m pip install -r sam/requirements.txt
python -m sam.api
```

The backend listens on `http://localhost:8000`.

### Frontend

Typical local startup:

```bash
cd frontend
npm install
npm run dev
```

The frontend listens on `http://localhost:3000`.

### Recommended developer order

1. Start the backend first.
2. Verify `/health`.
3. Start the frontend.
4. Sign in with Supabase.
5. Test classification and history flows before admin actions.

## 10. Deployment

### Backend container

`Dockerfile` builds a Python 3.13 slim image, installs backend dependencies, exposes port `8080`, and runs Uvicorn.

### Oracle Cloud VM helper

`deploy/oci-backend.sh` builds the Docker image and runs it with the supplied environment file.

### Vercel

`frontend/vercel.json` schedules the Supabase keepalive route daily.

When deployed on Vercel:

- frontend requests can be proxied through `/api/mosam`
- the proxy forwards to `MOSAM_API_UPSTREAM`
- the cron route keeps the Supabase auth service warm

## 11. Testing and Validation

### Backend tests

The backend has a wide test suite in `sam/tests/` covering:

- classification coherence
- analysis
- candidate set enforcement
- caching
- API helpers
- tariff labels, notes, rates, metadata, and rules
- product identification
- web search
- RGI pipeline
- section correction
- file extraction

### Frontend validation

The frontend currently relies on TypeScript, Next.js, and browser-side checks.
Useful validation points are:

- protected route redirect behavior
- session persistence
- API proxy behavior
- classification streaming and structured rendering
- history filtering and CSV export
- admin user mutation actions

## 12. Operational Notes

- The backend has explicit handling for Supabase connection errors, including pooler-related guidance.
- Admin endpoints are protected and the frontend avoids showing admin pages when the session is missing.
- Classification results can be validated and enriched with audit metadata.
- There is a cache-control surface for classification caching.
- The app supports both direct backend access and proxy-based access depending on deployment.

## 13. Client Issues and Root-Cause Analysis

This section captures two sources of product feedback:

- the detailed issue list shared during review
- the two main points raised verbally by the client in the meeting

### Meeting Takeaways

The client emphasized two top-level problems:

- API cost is too high. The client reported that even one product can cost more than USD 1, and multi-product inputs become very expensive.
- Results are not good enough. The client is not satisfied with the quality and reliability of the classifications.

These two concerns should be treated as the main business priorities. Most of the lower-level issues below are contributing causes of one or both.

### Detailed Issue List

1. High API cost
2. Slow response time
3. Optimization of the current pipeline
4. Manufacturer / part-number classification
5. Incomplete or incorrect classification, especially missing sub-levels
6. Batch / multi-product classification stability
7. Reliable file import for CSV, Excel, Word, and PDF invoices

### Issue-by-Issue Diagnosis

#### 1. High API cost

Importance: critical  
Complexity: medium

Why it matters:

- this was one of the two main complaints raised by the client
- if one product can exceed USD 1, scale usage becomes commercially difficult

Likely root cause in this repo:

- the same request can trigger multiple expensive stages
- web search may be enabled by default
- manufacturer-reference retries can add more model calls
- file classification may require many batch calls
- incomplete batch returns can trigger fallback per-item calls
- cache is present, but only helps when the normalized query repeats or when validations later populate stored responses

Code-level signals:

- `MOSAM_WEB_SEARCH_ENABLED` defaults to true
- identification and classification models can both default to the main model
- file processing explicitly performs batch fallback per item
- cache writes are limited and not all expensive intermediate steps are memoized

Main impact:

- high per-product cost
- cost explosion on multi-product uploads

#### 2. Slow response time

Importance: critical  
Complexity: medium

Why it matters:

- slow answers reduce trust and make the tool feel expensive even before invoices arrive
- long latency reinforces the client's perception that the API cost is too high

Likely root cause in this repo:

- multiple sequential stages: identification, retrieval, classification, normalization, enrichment
- optional web search adds latency
- file uploads can be split into multiple batches
- incomplete batch returns trigger per-item fallback processing

Code-level signals:

- classification streaming exists, but backend work still happens before final completion
- file classification loops through batches
- incomplete batches fall back to one-by-one calls

Main impact:

- long waits for single-product and multi-product flows
- poor user experience during large uploads

#### 3. Optimization of the current pipeline

Importance: high  
Complexity: medium

Why it matters:

- optimization is the fastest path to improving both business complaints without redesigning the whole product first
- better optimization can reduce cost, reduce time, and stabilize outputs

Likely optimization targets in this repo:

- route identification and classification to cheaper models where acceptable
- disable or narrow web search for cases that do not need it
- cache more intermediate results, not only final normalized responses
- avoid repeated fallback calls in batch mode
- reduce duplicate work between identification, retrieval, and final classification

Main impact:

- lower API cost
- faster turnaround time
- better operational scalability

#### 4. Manufacturer / part-number classification

Importance: critical  
Complexity: high

Why it matters:

- This is a common real-world customs workflow.
- If a user enters a manufacturer reference or part number and the system cannot reliably identify it, classification quality drops immediately.

What exists already:

- `sam/product_identification.py` already detects `MANUFACTURER_REF`
- it stores `manufacturer_part_number`
- it uses a dedicated prompt for manufacturer references
- it can optionally call OpenAI web search to enrich identification

What is still missing:

- a dedicated internal reference database or lookup service that maps part number to a canonical product profile
- a deterministic mapping layer from canonical product to likely tariff candidates

Likely root cause in this repo:

- the current path still relies heavily on LLM identification and optional web search instead of a stable reference dataset
- the system can enrich a part number, but it does not yet have a proper catalog-backed resolution layer

Main impact:

- poor quality on industrial references
- higher cost because web-assisted identification can trigger extra model usage

#### 5. Incomplete or incorrect classification, especially missing sub-levels

Importance: critical  
Complexity: high

Why it matters:

- This is the core product promise.
- If the result stops too early or returns the wrong subposition, users lose trust quickly.

What exists already:

- candidate position enforcement
- position validation
- RGI pipeline application
- subposition resolution from TEC
- criteria tracing and decision synthesis

What is still weak:

- difficult cases still depend on LLM interpretation plus retrieval quality
- hard-edge tariff distinctions can fail when product identification is vague or source extraction is noisy
- subposition completion is only as good as the evidence available to the decision engine

Likely root cause in this repo:

- inconsistent upstream product identification
- incomplete structured evidence for fine-grained tariff rules
- retrieval and candidate narrowing that may still leave ambiguity for the LLM layer

Main impact:

- low result quality
- client perception that the system is "not good"

#### 6. Batch / multi-product classification stability

Importance: medium-high  
Complexity: medium

Why it matters:

- once users upload files or classify lists, the product must stay consistent across many lines

What exists already:

- file batching
- deduplication and quantity aggregation
- per-item fallback when a batch is incomplete

What is still weak:

- batch behavior depends on how reliably the model returns one classification per input item
- fallback behavior improves completeness but increases cost and latency
- orchestration is present, but not yet optimized as a robust queue-based pipeline

Likely root cause in this repo:

- batch outputs are still model-shaped rather than fully deterministic
- the system compensates with fallback logic instead of preventing the failure earlier

Main impact:

- inconsistent multi-line results
- high cost and slower response on uploads

#### 7. Reliable file import for CSV, Excel, Word, and PDF invoices

Importance: high  
Complexity: high

Why it matters:

- many business users will work from invoices, packing lists, or spreadsheets rather than typing one item at a time

What exists already:

- `/classify/file`
- parsers for TXT, PDF, CSV, XLSX, XLS, and DOCX
- item aggregation and batching after extraction
- tests for file extraction helpers

What is still missing:

- OCR for scanned PDFs
- stronger table extraction for inconsistent invoice layouts
- asynchronous document processing pipeline for very large or messy files

Likely root cause in this repo:

- PDF handling is mostly text extraction based
- invoice understanding is not yet a full document-extraction subsystem
- complex documents can feed noisy item lists into the classifier, which hurts both quality and cost

Main impact:

- poor results from invoice imports
- extra retries and extra model calls when extracted items are messy

### Cross-Mapping to the Client's Two Main Complaints

#### Complaint A: "API cost is too high"

Most likely driven by:

- issue 1: direct expensive model usage and limited caching
- issue 2: slow multi-stage processing
- issue 3: optimization gaps in the current pipeline
- issue 4: manufacturer references needing enrichment and sometimes web-assisted retries
- issue 6: batch fallback to per-item processing
- issue 7: messy file extraction causing bad inputs downstream

#### Complaint B: "Results are not good"

Most likely driven by:

- issue 4: weak deterministic handling of part numbers
- issue 5: incomplete or incorrect subposition decisions
- issue 6: instability across batch outputs
- issue 7: poor upstream extraction from invoices and mixed-format documents

### Priority Recommendation

Recommended order of work:

1. Reduce API cost and response time first
2. Optimize the current pipeline before adding bigger new capabilities
3. Improve result quality for single-product classification
4. Improve deterministic handling of manufacturer references and part numbers
5. Harden multi-product orchestration
6. Strengthen invoice and document extraction

## 14. Suggested Next Improvements

- Add an endpoint matrix table with request/response schemas.
- Add an ER diagram for the Supabase tables.
- Add a deployment checklist for OCI and Vercel.
- Add a short runbook for common failures such as Supabase pooler timeouts or OpenAI auth errors.
