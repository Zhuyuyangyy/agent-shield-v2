"""V3 Demo - 完整端到端验证 + 证据输出"""
import sys, json
sys.path.insert(0, 'backend')
from app.shadow.v3_facade import AgentShieldV3

v3 = AgentShieldV3(session_id="sess_financial_001")

v3.add_tool_call("FinancialAgent","cursor.execute","SELECT name,price...","allow",0.05,inherited_risk=0.0,labels=["low_risk"])
v3.add_tool_call("CustomerDataAgent","cursor.execute","SELECT phone,address...","allow",0.75,parent_agent_id="FinancialAgent",edge_type="calls",inherited_risk=0.025,labels=["medium_risk","sensitive_data"])
v3.add_tool_call("EmailAgent","send_email","send_email(to=ext,data=cust)","block",0.98,parent_agent_id="CustomerDataAgent",edge_type="data_flow",inherited_risk=0.55,labels=["critical","external_transfer"])
v3.add_tool_call("DataExportAgent","export_csv","export_csv()","allow",0.82,parent_agent_id="FinancialAgent",edge_type="calls",inherited_risk=0.05,labels=["medium_risk","data_export"])
v3.add_tool_call("LoggerAgent","log_event","log_event(level=INFO)","allow",0.01,parent_agent_id="DataExportAgent",edge_type="calls",inherited_risk=0.08,labels=["low_risk"])

graph = v3.graph.to_graph_dict()
node_to_agent = {n['node_id']: n['agent_id'] for n in graph['nodes']}

gov_report = v3.run_governance()
result = v3.get_result()
cy = result.causality_report

# Print human-readable
print("=" * 60)
print("AgentShield V3 Demo Output")
print("=" * 60)
print()
print("Layer 1: Agent Behavior Graph")
print(f"  Nodes: {len(graph['nodes'])} agents")
for n in graph['nodes']:
    print(f"    {n['agent_id']}: {n['risk_status'].upper()} score={n['risk_score']} inherited={n['inherited_risk']}")
print(f"  Edges: {len(graph['edges'])}")
for e in graph['edges']:
    fa = node_to_agent.get(e['from'], e['from'])
    ta = node_to_agent.get(e['to'], e['to'])
    print(f"    {fa} --[{e['type']}]--> {ta} risk_flow={e['risk_flow']}")

print()
print("Layer 2: Causality Engine")
chains = cy.get('critical_chains', [])
print(f"  Causal chains: {len(chains)}")
for c in chains:
    print(f"    path={' -> '.join(c.get('chain', []))} terminal_risk={c['terminal_risk']}")
for r in cy.get('root_cause_attributions', []):
    print(f"  Root cause: Agent {r['agent_id']} responsibility={r['responsibility']:.3f}")

print()
print("Layer 3: Governance Engine")
decisions = gov_report.get('decisions', [])
print(f"  Decisions: {len(decisions)}")
for d in decisions:
    print(f"    {d.get('target_agent','?')}: {d['action']} | {d.get('rationale','')}")
whatifs = gov_report.get('whatif_scenarios', [])
print(f"  What-if scenarios: {len(whatifs)}")
for w in whatifs:
    print(f"    {w['scenario_id']}: {w.get('description','')[:60]}")
    print(f"      recommended={w.get('recommended',False)} reduction={w.get('predicted_risk_reduction','N/A')}")

print()
print(f"Overall: {result.overall_risk_level} | {result.governance_summary}")
print("=" * 60)

# Save evidence JSONs
import os
out_dir = "/mnt/d/ZYY Project/agent-shield-v2/docs/demo_evidence_v3"
os.makedirs(out_dir, exist_ok=True)

with open(f"{out_dir}/behavior_graph_result.json", "w", encoding="utf-8") as f:
    json.dump(graph, f, indent=2, ensure_ascii=False, default=str)

with open(f"{out_dir}/causality_result.json", "w", encoding="utf-8") as f:
    json.dump(cy, f, indent=2, ensure_ascii=False, default=str)

with open(f"{out_dir}/governance_decision_result.json", "w", encoding="utf-8") as f:
    json.dump(gov_report, f, indent=2, ensure_ascii=False, default=str)

print(f"\nEvidence files saved to {out_dir}/")
