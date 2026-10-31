# FairShare

**FairShare: Intelligent Group Expense Sharing and Minimum Transaction Settlement System**

A group expense app: record who paid and who consumed, split by four methods,
compute balances, and settle with the fewest payments.

## Features
- Groups and members (deactivate instead of delete when history exists)
- Four split methods: equal, custom, percentage, item-based; multiple payers
- Money stored as integer paise (exact, no float errors)
- Net balances (paid - owed; always sum to zero)
- Minimum-transaction settlement: exact search for up to 12 people, greedy beyond
- Pending/Completed settlements with history
- Dashboard, Plotly analytics, PDF and CSV export
- SQLite persistence

## Architecture
Streamlit UI -> services -> logic -> data (repositories) -> SQLite

## Run locally (Windows)
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    streamlit run app.py

## Tests
    pytest -q

## Project layout
pages/ (UI), ui/ (shared UI), services/ (application layer), logic/ (pure business rules),
data/ (models, schema, SQL), reports/ (PDF, CSV), tests/

## Author
Gaddam Ganga RaagaSreshta , Jain deemed-to-be University
