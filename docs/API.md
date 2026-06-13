# AgentShield V2 API Reference

## Core Classes

### ToolCallRequest

Standardized tool call request format.

```python
from app.tool_call import ToolCallRequest

request = ToolCallRequest(
    tool_name="cursor.execute",          # Tool name
    params={"sql": "SELECT ..."},        # Tool parameters
    agent_id="finance_agent",            # Agent identifier
    session_id="session_001",            # Session identifier
    is_database_tool=True,               # Is database tool?
)
```

**Fields:**
- `tool_name` (str): Name of the tool being called
- `params` (dict): Tool call parameters
- `agent_id` (str): Identifier of the calling agent
- `session_id` (str): Session identifier
- `timestamp` (datetime): Call timestamp (auto-generated)
- `is_database_tool` (bool): Whether this is a database tool
- `is_network_tool` (bool): Whether this is a network tool
- `is_file_tool` (bool): Whether this is a file tool
- `shadow_risk_score` (Optional[float]): Computed risk score (0.0-1.0)
- `simulated_effect` (Optional[dict]): Shadow simulation result
- `risk_level` (RiskLevel): Computed risk level
- `fuse_action` (str): Fuse decision (allow/block/human_review)
- `fuse_reason` (str): Reason for fuse decision
- `audit_log_id` (Optional[str]): Audit log entry ID

### ToolCallAuditEngine

Main audit engine facade.

```python
from app.tool_call import ToolCallAuditEngine

engine = ToolCallAuditEngine()
result = engine.audit(request)
```

**Methods:**
- `audit(request: ToolCallRequest) -> ToolCallRequest`: Run full audit pipeline
- `get_audit_trail(session_id: str) -> list[AuditLogEntry]`: Get audit trail for session

### SQLAnalyzer

SQL statement parser.

```python
from app.shadow.database.sql_analyzer import SQLAnalyzer

analyzer = SQLAnalyzer()
sql_info = analyzer.analyze("SELECT phone FROM customers WHERE id = 1")
```

**Methods:**
- `analyze(sql: str) -> SQLInfo`: Parse SQL statement

**SQLInfo Fields:**
- `tables` (list[str]): Table names
- `operation` (str): Operation type (SELECT/INSERT/UPDATE/DELETE)
- `selected_columns` (list[str]): Selected column names
- `where_conditions` (list[str]): WHERE conditions
- `has_aggregation` (bool): Has aggregation functions
- `has_join` (bool): Has JOIN operations
- `is_bulk_query` (bool): Is bulk query
- `sensitive_fields_detected` (list[str]): Detected sensitive fields

### DatabaseShadowSimulator

Shadow simulation engine.

```python
from app.shadow.database.database_shadow_simulator import DatabaseShadowSimulator

simulator = DatabaseShadowSimulator()
effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
```

**Methods:**
- `simulate(tool_name, params, sql_info) -> ShadowEffect`: Run shadow simulation

**ShadowEffect Fields:**
- `predicted_tables` (list[str]): Predicted table access
- `predicted_columns` (list[str]): Predicted column access
- `affected_rows_estimate` (int): Estimated affected rows
- `sensitive_fields_detected` (list[str]): Detected sensitive fields
- `data_volume_mb` (float): Estimated data volume
- `is_external_transfer` (bool): Is external transfer
- `is_bulk_operation` (bool): Is bulk operation
- `risk_indicators` (list[str]): Risk indicators
- `summary` (str): Human-readable summary

### DatabaseShadowRiskScorer

5-factor risk scoring engine.

```python
from app.shadow.database.database_shadow_risk_scorer import DatabaseShadowRiskScorer

scorer = DatabaseShadowRiskScorer()
score = scorer.score(tool_name, params, sql_info, simulated_effect)
```

**Methods:**
- `score(tool_name, params, sql_info, simulated_effect) -> float`: Compute risk score (0.0-1.0)

## V3 API

### AgentShieldV3

Unified V3 audit facade.

```python
from app.shadow.v3_facade import AgentShieldV3, ChainAuditRequest

v3 = AgentShieldV3(session_id="session_001")

# Add tool calls
v3.add_tool_call(
    agent_id="agent_1",
    tool_name="cursor.execute",
    params_summary="SELECT * FROM customers",
    fuse_action="block",
    shadow_risk_score=0.95,
)

# Run governance
report = v3.run_governance()
result = v3.get_result()
```

**Methods:**
- `add_tool_call(...)`: Add a tool call to the behavior graph
- `audit_chain(request) -> ChainAuditResult`: Run full chain audit
- `run_governance() -> dict`: Run governance on existing graph
- `get_result() -> Optional[ChainAuditResult]`: Get latest governance result

### AgentBehaviorGraph

Multi-agent behavior graph.

```python
from app.shadow.behavior.agent_behavior_graph import AgentBehaviorGraph

graph = AgentBehaviorGraph(session_id="session_001")
graph.add_tool_call_as_node(...)
graph.compute_risk_propagation()
```

**Methods:**
- `add_node(node)`: Add a behavior node
- `add_edge(edge)`: Add a behavior edge
- `add_tool_call_as_node(...)`: Add tool call as node
- `get_node(node_id)`: Get node by ID
- `get_session_nodes()`: Get all session nodes
- `get_critical_nodes(threshold)`: Get critical risk nodes
- `get_risk_path(start, end)`: Get risk path between nodes
- `get_downstream_nodes(node_id)`: Get downstream nodes
- `compute_risk_propagation()`: Compute risk propagation
- `to_graph_dict()`: Export graph as dict
- `summary()`: Get graph summary

### CausalityEngine

Causal inference engine.

```python
from app.shadow.causality.causality_engine import CausalityEngine

engine = CausalityEngine(graph)
report = engine.analyze()
```

**Methods:**
- `analyze() -> dict`: Run full causal analysis
- `get_report() -> dict`: Get analysis report

### GovernanceEngine

Governance decision engine.

```python
from app.shadow.governance.governance_engine import GovernanceEngine

engine = GovernanceEngine(graph, causality_report)
decisions = engine.govern()
report = engine.get_governance_report()
```

**Methods:**
- `govern() -> list[InterventionDecision]`: Run governance decisions
- `get_governance_report() -> dict`: Get governance report
- `record_outcome(decision, actual_risk, original_risk)`: Record intervention outcome

## FastAPI Endpoints

### Health Check

```
GET /health
Response: {"status": "ok"}
```

## Error Handling

- SQL parse failure -> HUMAN_REVIEW
- Unknown tool type -> HUMAN_REVIEW
- Shadow simulation exception -> BLOCK
- Bulk query without WHERE -> HUMAN_REVIEW
