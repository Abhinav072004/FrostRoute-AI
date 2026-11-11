# FrostRoute AI

An AI copilot for cold-chain logistics: a Python / Streamlit AI FDE project combining historical fleet telemetry, operating procedures, and optional current weather. The default demo runs without cloud credentials. Conversational mode uses a bounded LangGraph tool-calling loop with OpenAI, Ollama, or DeepSeek.

[View the handwritten project notes](docs/NOTES.md) · [Download the original PDF](notes.pdf?raw=true)

## Run in VS Code

Install Python 3.12. Open this project folder in VS Code and use its integrated terminal.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock.txt
Copy-Item .env.example .env
streamlit run src/ui.py
```

On macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock.txt
cp .env.example .env
streamlit run src/ui.py
```

If PowerShell blocks activation, run `.venv\Scripts\python.exe -m pip install -r requirements.lock.txt` and `.venv\Scripts\python.exe -m streamlit run src/ui.py` directly. The lock file records the Python 3.12 environment tested on Linux; platform-specific ODBC installation may still be needed. `requirements.txt` provides compatible ranges for other environments.

Use **Evidence explorer** to load the historical fleet sample, search the SOP with local BM25, and check an explicitly confirmed fresh-perishable temperature. No Pinecone, embeddings, database server, or LLM is needed for these workflows. The checker provides recommendations; it does not perform dispatch actions.

## Enable conversational AI

Edit `.env` and restart Streamlit:

- OpenAI: `AGENT_LLM=OPENAI`, `OPENAI_API_KEY=...`; optionally set `LLM_MODEL` (default `gpt-4o-mini`).
- Ollama: run a local Ollama server with a model supporting tools, set `AGENT_LLM=OLLAMA`; default model is `qwen2.5:7b`. Download the model separately with `ollama pull qwen2.5:7b`.
- DeepSeek: `AGENT_LLM=DEEPSEEK`, `DEEPSEEK_API_KEY=...`; optionally set `LLM_MODEL` (default `deepseek-chat`). Verify model availability with your provider.

Hosted providers receive the conversation and retrieved evidence. Keep credentials in `.env`, which is excluded from Git. The system prompt is injected on every reasoning call. Up to 12 graph steps are allowed per request. A failed or interrupted request may leave partial conversation state; use **New conversation** before retrying.

## Retrieval and guardrails

`RAG_BACKEND=local` uses deterministic BM25 ranking over heading-aware chunks in `data/policy/`. Supported formats are Markdown, text, and text-based PDF; scanned PDFs need OCR outside this app. Results contain filenames, section labels and excerpts. Irrelevant zero-overlap questions return no evidence. Lexical overlap alone does not prove relevance: the assistant must abstain when passages do not support an answer. Restart after editing documents to refresh cached chunks.

SQL is parsed as an AST and restricted to one simple SELECT from the approved view, approved columns, no joins, functions, nested queries or writes, and ten returned rows. SQL Server also requires its restricted login, connection timeout and query timeout. This intentionally excludes aggregate analytics. Expand the SQL grammar only alongside tests and least-privilege database grants.

`assess_fresh_perishable` applies explicit thresholds with exact boundary tests. It requires confirmed cargo category and refuses to run after the bundled SOP content changes until the rule pack is reviewed and its hash updated. Unknown ETA remains unknown. Tool outputs and documents are evidence, not instructions. Prompt guidance helps reduce injection and unsupported claims, but is not a complete prompt-injection defense or a guarantee of grounded model output. Tool permissions and SQL validation enforce the executable boundaries.

## Optional SQL Server

1. Install SQL Server and Microsoft ODBC Driver 18 using the vendor instructions for your OS.
2. Configure a database and separate ingestion / administrator credentials as `SQL_ADMIN_USER` and `SQL_ADMIN_PASSWORD`. Set the host, port and `SQL_DATABASE` in `.env`.
3. Run `python scripts/ingest_legacy_data.py`. It refuses to overwrite an existing table; `--replace` explicitly replaces the sample table.
4. Provision a unique restricted SQL login named `USR_FDE_RO` using your database administration tool. Run `scripts/setup_security_and_view.sql` with the VS Code MSSQL extension as an administrator in the target database.
5. Set `DATA_BACKEND=mssql` and `SQL_AGENT_PASSWORD`. Keep ingestion credentials out of the deployed app environment. Use encrypted transport and a valid server certificate. For a local self-signed development server only, explicitly configure `SQL_TRUST_CERTIFICATE=yes`.
6. Verify the restricted login can SELECT the view and cannot read or modify the raw table. Restart the app.

## Optional Pinecone

Local vectorless retrieval is the default. To compare hosted vector retrieval:

```bash
python -m pip install -r requirements-vector.txt
python scripts/ingest_sop_pinecone.py
```

Set `PINECONE_API_KEY` and either OpenAI credentials with `Embeddings_model=OPENAI` or `Embeddings_model=LOCAL` plus `Local_Embedding_Model`. Local embeddings download model weights and consume additional RAM. Then set `RAG_BACKEND=pinecone` and restart. Ingestion derives the embedding dimension, refuses mismatched indexes, and upserts into a content-specific policy namespace. It never deletes existing indexes. Wait for service consistency before testing; old namespaces require manual retention cleanup. Do not switch a local embedding model to another model with the same dimension in an existing index without a separate migration: equal dimensions do not imply compatible embeddings.

## Audit and deployment

Application events are stored in `.runtime/audit.sqlite3`, excluded from Git. Set a long random `AUDIT_VIEW_PASSWORD` to enable the viewer. Events can contain user text and evidence; configure filesystem access and retention before deployment. Local SQLite is durable but not immutable, centrally managed, encrypted, or suitable for multi-replica auditing. A logging failure stops the request rather than silently losing its trail.

Conversation history stays in process memory. Restart loses it; expired-session cleanup and persistent multi-replica state are future deployment work. Public hosting needs identity-aware access, HTTPS, rate limits and a central protected audit sink. The included GitHub workflow is an optional manual EC2 template, not a configured deployment. Its environment and secrets must be supplied in your own repository. Reference PDFs describe the original design intent; this README and `docs/REVIEW.md` describe the implemented behavior.

## Test

From the project root with the virtual environment active:

```bash
python -m unittest discover -s tests -v
python -m pip check
```

Tests cover retrieval relevance and abstention, SQL bypass attempts, weather failures, compliance boundaries, policy changes, mocked agent execution / system prompt / session isolation, and Streamlit interactions. See `docs/REVIEW.md` for actual validation and external-service limits.

## Download or clone this repository

On GitHub, select **Code → Download ZIP**, extract the archive, and open its `FrostRoute-AI-main` folder in VS Code. Or clone it:

```bash
git clone https://github.com/Abhinav072004/FrostRoute-AI.git
cd FrostRoute-AI
```

## Push your own copy to GitHub

Create an empty GitHub repository, then run from this folder:

```bash
git init
git add .
git commit -m "Build cold-chain evidence assistant"
git branch -M main
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPOSITORY.git
git push -u origin main
```

Review the staged files before committing. Do not commit `.env`, `.runtime`, `.venv`, credentials, or local logs. The dataset source link is retained in `data/source/data.txt`.
