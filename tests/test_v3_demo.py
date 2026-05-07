"""V3 Demo"""
import sys
sys.path.insert(0, 'backend')
from app.shadow.v3_facade import AgentShieldV3

def demo():
    print("="*60)
    print("AgentShield V3 Demo")
    print("="*60)

    v3 = AgentShieldV3(session_id="sess_financial_001")

    v3.add_tool_call(agent_id="FinancialAgent", tool_name="cursor.execute",
        params_summary="SELECT name, price FROM products WHERE category=?",
        fuse_action="allow", shadow_risk_score=0.05, inherited_risk=0.0, labels=["low_risk"])
    print("FinancialAgent: SAFE")

    v3.add_tool_call(agent_id="CustomerDataAgent", tool_name="cursor.execute",
        params_summary="SELECT phone, address FROM customers WHERE status=1",
        fuse_action="allow", shadow_risk_score=0.75, parent_agent_id="FinancialAgent",
        edge_type="calls", inherited_risk=0.025, labels=["medium_risk", "sensitive_data"])
    print("CustomerDataAgent: MEDIUM (score=0.75, inherited=0.025)")

    v3.add_tool_call(agent_id="EmailAgent", tool_name="send_email",
        params_summary="send_email(to=external_partner.com, data=customer_data)",
        fuse_action="block", shadow_risk_score=0.98, parent_agent_id="CustomerDataAgent",
        edge_type="data_flow", inherited_risk=0.55, labels=["critical", "external_transfer"])
    print("EmailAgent: CRITICAL (score=0.98, inherited=0.55)")

    v3.add_tool_call(agent_id="DataExportAgent", tool_name="export_csv",
        params_summary="SELECT * FROM customers (no WHERE)",
        fuse_action="human_review", shadow_risk_score=0.82, parent_agent_id="CustomerDataAgent",
        edge_type="calls", inherited_risk=0.35, labels=["high_risk", "bulk_export"])
    print("DataExportAgent: HIGH (score=0.82, inherited=0.35)")

    v3.add_tool_call(agent_id="ComplianceAgent", tool_name="audit_log",
        params_summary="log_event(type=data_access)",
        fuse_action="allow", shadow_risk_score=0.12, parent_agent_id="EmailAgent",
        edge_type="returns", inherited_risk=0.0, labels=["audit"])
    print("ComplianceAgent: audit log (score=0.12)")

    gs = v3.graph.summary()
    print("Graph: nodes=%d, edges=%d" % (gs["total_nodes"], gs["total_edges"]))

    print("---Layer2---")
    v3.run_governance()
    fr = v3.get_result()
    cr = fr.causality_report

    for chain in cr.get("critical_chains", [])[:3]:
        print("Chain: root=%s, terminal_risk=%.2f, amplification=%.2fx" % (
            chain["root_agent"], chain["terminal_risk"], chain["amplification"]))
        print("  trajectory: %s" % chain["trajectory"])
        print("  weak_links: %s" % str(chain["weak_links"]))

    for attr in cr.get("root_cause_attributions", [])[:3]:
        print("Attr: node=%s (%s), responsibility=%.3f" % (
            attr["node_id"], attr["agent_id"], attr["responsibility"]))
        print("  direct=%.3f, inherited=%.3f" % (attr["direct"], attr["inherited"]))
        print("  explanation: %s" % attr["explanation"][:80])

    print("---Layer3---")
    gr = fr.governance_report
    print("Overall risk level: %s" % fr.overall_risk_level.upper())
    print("Governance summary: %s" % fr.governance_summary)
    print("Decisions: %d" % len(gr["decisions"]))
    for d in gr['decisions']:
        print("  [%s] %s @ %s" % (d["action"].upper(), d["target_agent"], d["target_node"]))
        print("  rationale: %s" % d["rationale"][:60])
        print("  predicted_effect=%.2f" % d["predicted_effect"])
    print("WhatIf scenarios: %d" % len(gr["whatif_scenarios"]))
    for w in gr['whatif_scenarios']:
        print("  %s" % w["scenario_id"])
        print("  %s" % w["description"][:70])
        print("  risk_reduction=%.2f%%, confidence=%.0f%%" % (
            w["predicted_risk_reduction"]*100, w["confidence"]*100))
        print("  %s" % w["recommendation"][:60])
    print("="*60)
    print("V3 Demo PASSED")
    print("="*60)
    return v3

if __name__ == '__main__':
    demo()