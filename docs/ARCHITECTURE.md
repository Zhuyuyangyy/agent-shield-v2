# AgentShield V2 Architecture

## System Overview

AgentShield V2 is a safety governance system for AI agent tool calls. It intercepts database operations before execution through shadow simulation and risk-based fuse control.

## Core Pipeline

```
ToolCallRequest
     |
     v
+--------------------+
| SQL Analyzer       |  Parse SELECT/INSERT/UPDATE/DELETE
| (sql_analyzer.py)  |  Extract tables, columns, WHERE clauses
+--------+-----------+
         |
         v
+--------------------+
| Shadow Simulator   |  Map data asset sensitivity
| (database_shadow_  |  Estimate affected rows
|  simulator.py)     |  Detect external transfer intent
+--------+-----------+
         |
         v
+--------------------+
| Risk Scorer        |  5-factor weighted scoring (0.0-1.0)
| (database_shadow_  |  Sensitive data: 85% weight
|  risk_scorer.py)   |  Volume/Bulk/External/Operation: 15%
+--------+-----------+
         |
         v
+--------------------+
| Fuse Controller    |  >= 0.90: BLOCK
| (RiskFuseController|  0.50-0.90: HUMAN_REVIEW
| )                  |  < 0.50: ALLOW
+--------+-----------+
         |
         v
+--------------------+
| Audit Logger       |  Structured risk profile
| (AuditLogEntry)    |  Factor breakdown + decision
+--------------------+
```

## Module Details

### 1. SQLAnalyzer (`backend/app/shadow/database/sql_analyzer.py`)

Parses SQL statements to extract:
- Table names (FROM, INSERT INTO, UPDATE, DELETE FROM)
- Column names (SELECT clause)
- WHERE conditions
- Operation type (SELECT/INSERT/UPDATE/DELETE)
- Aggregation functions (COUNT, SUM, AVG, etc.)
- JOIN operations
- Bulk query detection (no WHERE, large LIMIT)

### 2. DatabaseShadowSimulator (`backend/app/shadow/database/database_shadow_simulator.py`)

Predicts tool call impact without execution:
- Maps data asset sensitivity via `TABLE_SENSITIVITY`
- Estimates affected rows
- Detects sensitive field exposure
- Identifies external transfer intent
- Generates risk indicators

### 3. DatabaseShadowRiskScorer (`backend/app/shadow/database/database_shadow_risk_scorer.py`)

Computes 5-factor weighted risk score (0.0-1.0):
- **Sensitive data (85%)**: Table x field sensitivity matching
- **Data volume (5%)**: Affected row count and data size
- **Bulk operation (5%)**: No WHERE clause or LIMIT > 100
- **External transfer (3%)**: Email/webhook/FTP outbound intent
- **Operation type (2%)**: SELECT/INSERT/UPDATE/DELETE classification

### 4. ToolCallAuditEngine (`backend/app/tool_call.py`)

Orchestrates the full audit pipeline:
1. Check if tool is database-related
2. Run SQL analysis
3. Run shadow simulation
4. Compute risk score
5. Make fuse decision
6. Generate audit log entry

## V3 Extensions

### Layer 1: AgentBehaviorGraph

Multi-agent behavior chain tracking:
- Nodes represent tool calls with risk scores
- Edges represent agent-to-agent relationships
- Risk propagation computation
- Critical node identification

### Layer 2: CausalityEngine

Risk causal inference:
- Root cause attribution
- Causal chain identification
- Weak link detection
- Amplification factor computation

### Layer 3: GovernanceEngine

Governance decision and what-if simulation:
- Block/degrade/allow decisions
- Counterfactual scenario generation
- Rule evolution feedback
- Intervention effectiveness tracking

## Data Flow

```
Agent Tool Call
    |
    v
ToolCallRequest (standardized format)
    |
    v
ToolCallAuditEngine.audit()
    |
    +-- SQLAnalyzer.analyze()
    |       |
    |       v
    |   SQLInfo (tables, columns, operation, sensitive fields)
    |
    +-- DatabaseShadowSimulator.simulate()
    |       |
    |       v
    |   ShadowEffect (predicted impact, risk indicators)
    |
    +-- DatabaseShadowRiskScorer.score()
    |       |
    |       v
    |   Risk Score (0.0-1.0)
    |
    +-- Fuse Decision
    |       |
    |       v
    |   allow / human_review / block
    |
    +-- AuditLogEntry (structured log)
```

## Risk Scoring Model

### Weight Distribution

| Factor | Weight | Rationale |
|--------|--------|-----------|
| Sensitive data | 85% | Dominant factor; ensures sensitive queries trigger blocking |
| Data volume | 5% | Secondary; large exports increase risk |
| Bulk operation | 5% | Secondary; no WHERE clause = high risk |
| External transfer | 3% | Special path; dedicated blocking for data exfiltration |
| Operation type | 2% | Minimal; DELETE > UPDATE > INSERT > SELECT |

### Threshold Mapping

| Score Range | Risk Level | Fuse Action |
|-------------|------------|-------------|
| >= 0.90 | CRITICAL | BLOCK |
| 0.70 - 0.89 | HIGH | HUMAN_REVIEW |
| 0.50 - 0.69 | MEDIUM | HUMAN_REVIEW |
| 0.20 - 0.49 | LOW | ALLOW |
| < 0.20 | SAFE | ALLOW |

## Security Considerations

- **Fail-safe**: Unparseable operations default to HUMAN_REVIEW
- **Conservative**: Shadow simulation errors trigger BLOCK
- **Audit trail**: All decisions are logged with full context
- **No execution**: Shadow simulation never touches real data
