# AgentShield V2

> Database tool-call shadow simulation and fuse-intercept for AI agent safety.

![Python](https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Baseline%20Committed-brightgreen)
![Tests](https://img.shields.io/badge/Tests-Passing-brightgreen)
![Coverage](https://img.shields.io/badge/Coverage-80%25+-yellow)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker&logoColor=white)

## Overview

AgentShield V2 is a safety governance system that intercepts database tool calls **before execution** through shadow simulation and risk-based fuse control. While V1 focused on auditing what AI models *say* (output compliance, hallucination detection, RAG traceability), V2 governs what agents *do* -- specifically, their database operations.

The core innovation is the **shadow simulation engine**: when an AI agent attempts a database operation (SQL query, data export, email send), V2 parses the SQL structure, maps data asset sensitivity, simulates the predicted impact, computes a 5-factor weighted risk score, and triggers a three-level fuse (allow / human_review / block) -- all without executing the actual query. This enables proactive prevention of data exfiltration, bulk data exposure, and unauthorized external transfers.

AgentShield V2 represents the transition from "model output audit" to "agent behavior governance" in the AgentShield version lineage: V1 governs model outputs, V2 governs agent tool calls, and V3 governs multi-agent behavior chains.

## Key Features

1. **Tool Call Standardization** -- Abstracts AI agent database operations into a unified `ToolCallRequest` format, providing a single entry point for all tool-call governance.

2. **Database Shadow Simulation** -- Predicts the impact of SQL operations through structural analysis without executing the query. Identifies affected tables, columns, row counts, and sensitive field exposure.

3. **Data Asset Sensitivity Mapping** -- Dual-layer sensitivity model with `TABLE_SENSITIVITY` (table-level weights) and `_BASE_SENSITIVITY` (field-level scores) covering customer data, patient records, financial transactions, and more.

4. **5-Factor Weighted Risk Scoring** -- Computes risk scores (0.0--1.0) from five factors: sensitive data (85%), data volume (5%), bulk operations (5%), external transfer (3%), and operation type (2%). The 85% weight on sensitive data ensures queries touching sensitive fields reliably trigger high risk scores.

5. **Three-Level Fuse Control** -- Threshold-based governance: score >= 0.90 triggers BLOCK, 0.50--0.90 triggers HUMAN_REVIEW, below 0.50 allows execution. Conservative default: unparseable operations default to human_review.

6. **External Side-Effect Detection** -- Identifies intent to transfer data externally through email, webhook, FTP, or file export channels.

7. **Audit Trail** -- Generates structured `AuditLogEntry` records with full risk factor breakdown for compliance and debugging.

8. **V3 Behavior Chain Analysis** -- Multi-agent call chain tracking with risk propagation visualization, causal inference, and counterfactual what-if simulation.

## Architecture

```
+------------------------------------------------------------------+
|                    AgentShield V2 Pipeline                        |
+------------------------------------------------------------------+
|                                                                  |
|  ToolCallRequest                                                 |
|       |                                                          |
|       v                                                          |
|  +--------------------+                                          |
|  | SQL Analyzer       |  Parse SELECT/INSERT/UPDATE/DELETE       |
|  | (sql_analyzer.py)  |  Extract tables, columns, WHERE clauses |
|  +--------+-----------+                                          |
|           |                                                      |
|           v                                                      |
|  +--------------------+                                          |
|  | Shadow Simulator   |  Map data asset sensitivity              |
|  | (database_shadow_  |  Estimate affected rows                  |
|  |  simulator.py)     |  Detect external transfer intent         |
|  +--------+-----------+                                          |
|           |                                                      |
|           v                                                      |
|  +--------------------+                                          |
|  | Risk Scorer        |  5-factor weighted scoring (0.0-1.0)     |
|  | (database_shadow_  |  Sensitive data: 85% weight              |
|  |  risk_scorer.py)   |  Volume/Bulk/External/Operation: 15%    |
|  +--------+-----------+                                          |
|           |                                                      |
|           v                                                      |
|  +--------------------+                                          |
|  | Fuse Controller    |  >= 0.90: BLOCK                          |
|  | (RiskFuseController|  0.50-0.90: HUMAN_REVIEW                |
|  | )                  |  < 0.50: ALLOW                           |
|  +--------+-----------+                                          |
|           |                                                      |
|           v                                                      |
|  +--------------------+                                          |
|  | Audit Logger       |  Structured risk profile                 |
|  | (AuditLogEntry)    |  Factor breakdown + decision             |
|  +--------------------+                                          |
+------------------------------------------------------------------+
```

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Backend Framework | FastAPI | REST API server |
| SQL Parsing | Python regex | SQL structure analysis |
| Risk Scoring | Custom 5-factor model | Weighted risk computation |
| Testing | pytest | Unit and integration tests |
| Data Validation | Pydantic | Request/response schemas |
| Containerization | Docker | Deployment packaging |
| CI/CD | GitHub Actions | Automated lint, test, build |

## Quick Start

### Prerequisites

- Python 3.9 or higher
- pip package manager
- Docker (optional)

### Installation

```bash
git clone <repository-url>
cd agent-shield-v2

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ -v --cov=backend --cov-report=term-missing

# Run specific test suite
python -m pytest tests/test_database_shadow.py -v
```

### Running the Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Docker Deployment

```bash
# Build and run with Docker
docker build -t agent-shield-v2 .
docker run -p 8000:8000 agent-shield-v2

# Or use docker-compose
docker-compose up -d
```

### Demo Scenario

```
Financial Agent attempts:
  cursor.execute("SELECT phone, id_card, address FROM customers")
  send_email(to="external@company.com", attachment=data)

Expected result:
  shadow_risk_score >= 0.90 -> fuse_action = "block"
```

## Project Structure

```
agent-shield-v2/
+-- backend/
|   +-- app/
|   |   +-- __init__.py                           # Package init + version
|   |   +-- tool_call.py                          # Standardized request + audit facade
|   |   +-- shadow/
|   |       +-- __init__.py                       # Shadow module exports
|   |       +-- v3_facade.py                      # V3 unified audit facade
|   |       +-- behavior/
|   |       |   +-- agent_behavior_graph.py       # Multi-agent behavior graph
|   |       +-- causality/
|   |       |   +-- causality_engine.py           # Risk causal inference
|   |       +-- governance/
|   |       |   +-- governance_engine.py          # Governance + what-if simulation
|   |       +-- database/
|   |           +-- sql_analyzer.py               # SQL parsing (tables/columns/WHERE/sensitive fields)
|   |           +-- database_shadow_simulator.py  # Shadow simulation engine + TABLE_SENSITIVITY
|   |           +-- database_shadow_risk_scorer.py # 5-factor risk scoring (0.0-1.0)
+-- tests/
|   +-- __init__.py
|   +-- test_database_shadow.py                   # V2 core test suite
|   +-- test_sql_analyzer.py                      # SQL analyzer unit tests
|   +-- test_shadow_simulator.py                  # Shadow simulator unit tests
|   +-- test_risk_scorer.py                       # Risk scorer unit tests
|   +-- test_tool_call_audit.py                   # Audit engine integration tests
|   +-- test_behavior_graph.py                    # V3 behavior graph tests
|   +-- test_causality_engine.py                  # V3 causality engine tests
|   +-- test_governance_engine.py                 # V3 governance engine tests
|   +-- test_v3_facade.py                         # V3 facade integration tests
|   +-- test_smoke.py                             # Smoke tests
|   +-- conftest.py                               # Shared fixtures
+-- docs/
|   +-- ARCHITECTURE.md                           # Architecture documentation
|   +-- API.md                                    # API reference
|   +-- DEPLOYMENT.md                             # Deployment guide
|   +-- SECURITY.md                               # Security considerations
|   +-- demo_evidence_v2/                         # V2 demo evidence package
|   +-- demo_evidence_v3/                         # V3 demo evidence package
|   +-- patent/                                   # Patent documentation
+-- .github/
|   +-- workflows/
|       +-- ci.yml                                # CI/CD pipeline
+-- Dockerfile                                    # Container configuration
+-- docker-compose.yml                            # Multi-service orchestration
+-- requirements.txt                              # Python dependencies
+-- pyproject.toml                                # Project configuration
+-- .gitignore
+-- README.md
+-- TODO.md                                       # Innovation suggestions
+-- INNOVATION_ROADMAP.md                         # Patent roadmap
+-- OPTIMIZATION_REPORT.md                        # Optimization report
```

## Benchmarks & Results

### V2 Demo Verification (All Cases Passed)

| Case | Tool | SQL / Input | Score | Action | Expected |
|------|------|-------------|------:|--------|----------|
| Sensitive customer query | `cursor.execute` | `SELECT phone, id_card, address FROM customers WHERE status = 1` | **0.901** | block | block |
| Safe product query | `cursor.execute` | `SELECT name, price FROM products WHERE category = electronics` | **0.051** | allow | allow |
| External email + customer data | `send_email` | `SELECT phone, bank_account FROM customers` + `to=external@evil.com` | **0.981** | block | block |
| `SELECT *` bulk query | `cursor.execute` | `SELECT * FROM customers` (no WHERE) | **0.866** | human_review | human_review |

### Risk Scoring Factor Weights

| Factor | Weight | Description |
|--------|-------:|-------------|
| Sensitive data | 85% | Matched sensitive fields x table combinations (dominant factor) |
| Data volume | 5% | Affected row count and data size |
| Bulk operation | 5% | No WHERE clause or LIMIT > 100 |
| External transfer | 3% | Email/webhook/FTP outbound intent |
| Operation type | 2% | SELECT/INSERT/UPDATE/DELETE classification |

**Design principle**: Sensitive data weight (85%) dominates to ensure queries touching sensitive fields reliably reach the 0.90+ threshold for blocking.

## Boundary Handling

> **Unexplainable tool calls are not automatically executed.**

- SQL parse failure -> human_review
- Unknown tool type -> human_review
- Shadow simulation exception -> block (conservative strategy)
- Bulk query without WHERE -> human_review (preserves human judgment)

## Research Context

AgentShield V2 is part of a three-version safety governance lineage:

| Version | Scope | Focus |
|---------|-------|-------|
| **V1** | Model output | What did the AI say? (Hallucination, RAG, risk entropy) |
| **V2** | Agent tool calls | What did the agent do? (Shadow simulation, fuse control) |
| **V3** | Multi-agent chains | Why does this behavior chain become risky? (Graph, propagation) |

## Roadmap

| Phase | Status | Description |
|-------|--------|-------------|
| V1 Output Audit | Frozen | Hallucination detection, RAG traceability, risk entropy |
| V2 Shadow Simulation | Baseline committed | Tool-call standardization, shadow engine, 5-factor scoring |
| V3 Behavior Chain | Planned | Cross-agent call chain tracking, risk propagation visualization |

## Contributing

Contributions are welcome. Please ensure all tests pass before submitting changes.

```bash
# Run linting
pip install ruff
ruff check .

# Run tests with coverage
python -m pytest tests/ -v --cov=backend --cov-report=term-missing
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For questions, collaboration, or research inquiries, please open an issue on the repository.
