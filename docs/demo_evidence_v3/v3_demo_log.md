# AgentShield V3 Demo Log

**Date:** 2026-05-07
**Session:** sess_financial_001
**Tag:** agentshield-v3-behavior-chain-baseline
**Status:** PASS

---

## Test Scenario

Financial multi-agent system with 5 agents and 4 behavior edges.

```
FinancialAgent (root)
  ├── CustomerDataAgent (calls)
  │     └── EmailAgent (data_flow)
  └── DataExportAgent (calls)
        └── LoggerAgent (calls)
```

---

## Layer 1: Agent Behavior Graph

| Agent | Status | Shadow Score | Inherited Risk | Fuse Action |
|---|---|---|---|---|
| FinancialAgent | SAFE | 0.05 | 0.0 | allow |
| CustomerDataAgent | HIGH | 0.75 | 0.025 | allow |
| EmailAgent | CRITICAL | 0.98 | 0.55 | block |
| DataExportAgent | HIGH | 0.82 | 0.05 | allow |
| LoggerAgent | SAFE | 0.01 | 0.08 | allow |

Edges:
- FinancialAgent --[calls]--> CustomerDataAgent (risk_flow=0.75)
- CustomerDataAgent --[data_flow]--> EmailAgent (risk_flow=0.98)
- FinancialAgent --[calls]--> DataExportAgent (risk_flow=0.82)
- DataExportAgent --[calls]--> LoggerAgent (risk_flow=0.01)

---

## Layer 2: Causality Engine

**Causal chains found:** 1

Chain: EmailAgent (terminal_risk=0.98, amplification=1.0)

**Root Cause Attribution:**

| Agent | Responsibility | Direct Risk | Inherited Risk | Chain Length |
|---|---|---|---|---|
| FinancialAgent | 1.000 | 0.75 | 0.025 | 2 |
| FinancialAgent | 0.980 | 0.82 | 0.05 | 2 |
| CustomerDataAgent | 0.045 | 0.98 | 0.55 | 3 |

Root cause identified as **FinancialAgent** (highest responsibility score = 1.000).

---

## Layer 3: Governance Engine

### Decisions (3)

| Agent | Action | Confidence | Rationale |
|---|---|---|---|
| CustomerDataAgent | allow | 0.00 | Node risk acceptable (direct=0.75, inherited=0.03). Proceed with audit log. |
| DataExportAgent | allow | 0.00 | Node risk acceptable (direct=0.82, inherited=0.05). Proceed with audit log. |
| EmailAgent | block | 0.00 | Risk score 0.98 >= 0.9 threshold. Direct block. |

### What-if Scenarios (2)

**Scenario 1: whatif_block_early**
- Type: block_at_root
- Target: FinancialAgent
- Mechanism: Block at root to prevent risk propagation to downstream agents
- Risk reduction: 97.5% (0.975)
- New terminal score: 0.025
- **Recommended: YES**
- Recommendation: "Early blocking shows significant effect (97.5% risk reduction), minimal impact on normal business."

**Scenario 2: whatif_threshold_raise**
- Type: raise_threshold (0.9 -> 0.95)
- Target: threshold
- Risk reduction: 3.1% (0.031)
- **Recommended: NO**
- Recommendation: "Raising threshold increases missed detection risk. Current threshold sensitivity is appropriate."

---

## Overall Result

| Field | Value |
|---|---|
| Overall Risk Level | **high** |
| Overall Action | "阻断 1 个高风险节点。生成 2 个反事实场景，其中 1 个建议采纳。" |
| Decisions | 3 (1 block, 2 allow) |
| What-if scenarios | 2 (1 recommended) |
| Root cause | FinancialAgent |

---

## V2+V3 Unified Report Summary

- V2 modules: ToolCallAuditEngine, ShadowDatabaseSimulator, RiskScoreFuseController, HardGateOverride
- V3 layers: Behavior Graph (5 nodes/4 edges) + Causality Engine + Governance Engine
- End-to-end: V2 audits each agent's tool call -> V3 Layer 1 builds behavior graph -> Layer 2 identifies causal chains -> Layer 3 generates governance decisions + what-if counterfactuals

---

## Bug Fixes Applied (Pre-Demo)

1. **causality_engine.py:106** - `has_child` field error (to_node_id -> from_node_id)
2. **governance_engine.py:74-75** - dataclass field order error (confidence before recommendation)
3. **test_v3_demo.py** - Updated API calls to match actual facade method signatures
4. **test_v3_demo.py** - Updated key names: `status`->`risk_status`, `shadow_risk_score`->`risk_score`, removed `scenario_type` (field is `description`)

---

## Evidence Files

- `behavior_graph_result.json` - Full Layer 1 output
- `causality_result.json` - Full Layer 2 output
- `governance_decision_result.json` - Full Layer 3 governance decisions
- `what_if_result.json` - What-if scenario details
- `unified_v2_v3_report.json` - Combined V2+V3 summary report
- `bugfix_record.md` - Development bug fix log
- `v3_demo_log.md` - This file

---

## Commit & Tag

```bash
git commit -m "feat: complete AgentShield V3 behavior-chain governance baseline"
git tag agentshield-v3-behavior-chain-baseline
```

Commit hash: `b530030`
