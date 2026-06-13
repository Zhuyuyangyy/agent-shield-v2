"""
Shared test fixtures for AgentShield V2 test suite.
"""

import sys
import os

# Ensure backend is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from app.tool_call import ToolCallRequest, ToolCallAuditEngine
from app.shadow.database.sql_analyzer import SQLAnalyzer
from app.shadow.database.database_shadow_simulator import DatabaseShadowSimulator
from app.shadow.database.database_shadow_risk_scorer import DatabaseShadowRiskScorer


@pytest.fixture
def engine():
    """Fresh ToolCallAuditEngine instance."""
    return ToolCallAuditEngine()


@pytest.fixture
def sql_analyzer():
    """Fresh SQLAnalyzer instance."""
    return SQLAnalyzer()


@pytest.fixture
def simulator():
    """Fresh DatabaseShadowSimulator instance."""
    return DatabaseShadowSimulator()


@pytest.fixture
def scorer():
    """Fresh DatabaseShadowRiskScorer instance."""
    return DatabaseShadowRiskScorer()


@pytest.fixture
def sample_sensitive_request():
    """Sample high-risk database tool call request."""
    return ToolCallRequest(
        tool_name="cursor.execute",
        params={"sql": "SELECT phone, id_card, address FROM customers WHERE status = 1"},
        agent_id="finance_agent",
        session_id="test_session_001",
        is_database_tool=True,
    )


@pytest.fixture
def sample_safe_request():
    """Sample low-risk database tool call request."""
    return ToolCallRequest(
        tool_name="cursor.execute",
        params={"sql": "SELECT name, price FROM products WHERE category = 'electronics'"},
        agent_id="product_agent",
        session_id="test_session_002",
        is_database_tool=True,
    )


@pytest.fixture
def sample_non_db_request():
    """Sample non-database tool call request."""
    return ToolCallRequest(
        tool_name="send_message",
        params={"message": "Hello team"},
        agent_id="messenger_agent",
        session_id="test_session_003",
        is_database_tool=False,
    )
