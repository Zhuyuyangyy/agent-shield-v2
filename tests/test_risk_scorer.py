"""
test_risk_scorer.py
===================
Comprehensive unit tests for DatabaseShadowRiskScorer.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import pytest
from app.shadow.database.database_shadow_risk_scorer import (
    DatabaseShadowRiskScorer, RiskFactorBreakdown, _WEIGHTS
)
from app.shadow.database.database_shadow_simulator import DatabaseShadowSimulator, ShadowEffect
from app.shadow.database.sql_analyzer import SQLAnalyzer


@pytest.fixture
def scorer():
    return DatabaseShadowRiskScorer()


@pytest.fixture
def simulator():
    return DatabaseShadowSimulator()


@pytest.fixture
def analyzer():
    return SQLAnalyzer()


class TestRiskScorerWeights:
    """Test risk factor weight configuration."""

    def test_weights_sum_to_one(self):
        total = sum(_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_sensitive_data_weight_is_dominant(self):
        assert _WEIGHTS["sensitive_data"] == 0.85

    def test_all_weights_positive(self):
        for weight in _WEIGHTS.values():
            assert weight > 0

    def test_weight_keys(self):
        expected_keys = {"sensitive_data", "data_volume", "bulk_operation", "external_transfer", "operation_type"}
        assert set(_WEIGHTS.keys()) == expected_keys


class TestRiskScorerSensitiveData:
    """Test sensitive data scoring."""

    def test_high_sensitive_score_for_customers(self, scorer):
        score = scorer._score_sensitive_data(["customers.phone", "customers.id_card"], ["customers"])
        assert score >= 0.95

    def test_no_sensitive_fields_table_default(self, scorer):
        score = scorer._score_sensitive_data([], ["customers"])
        assert score == 0.90  # TABLE_DEFAULT_SCORES for customers

    def test_no_sensitive_no_table(self, scorer):
        score = scorer._score_sensitive_data([], ["unknown_table"])
        assert score == 0.0

    def test_sensitive_with_dotted_format(self, scorer):
        score = scorer._score_sensitive_data(["customers.bank_account"], ["customers"])
        assert score == 1.0

    def test_sensitive_with_category_format(self, scorer):
        score = scorer._score_sensitive_data(["category:phone"], ["customers"])
        assert score >= 0.90


class TestRiskScorerDataVolume:
    """Test data volume scoring."""

    def test_high_volume(self, scorer):
        score = scorer._score_data_volume(15_000, 60.0)
        assert score == 0.95

    def test_medium_volume(self, scorer):
        score = scorer._score_data_volume(2_000, 10.0)
        assert score == 0.70

    def test_low_volume(self, scorer):
        score = scorer._score_data_volume(50, 0.1)
        assert score == 0.15

    def test_zero_volume(self, scorer):
        score = scorer._score_data_volume(0, 0.0)
        assert score == 0.0

    def test_moderate_volume(self, scorer):
        score = scorer._score_data_volume(150, 1.0)
        assert score == 0.40


class TestRiskScorerBulkOperation:
    """Test bulk operation scoring."""

    def test_bulk_high_rows(self, scorer):
        score = scorer._score_bulk_operation(True, 15_000)
        assert score == 0.95

    def test_bulk_medium_rows(self, scorer):
        score = scorer._score_bulk_operation(True, 2_000)
        assert score == 0.70

    def test_bulk_low_rows(self, scorer):
        score = scorer._score_bulk_operation(True, 500)
        assert score == 0.50

    def test_not_bulk(self, scorer):
        score = scorer._score_bulk_operation(False, 100)
        assert score == 0.0


class TestRiskScorerExternalTransfer:
    """Test external transfer scoring."""

    def test_email_external(self, scorer):
        score = scorer._score_external_transfer(True, "send_email", {})
        assert score == 1.0

    def test_webhook_external(self, scorer):
        score = scorer._score_external_transfer(True, "http_post_webhook", {})
        assert score == 0.90

    def test_other_external(self, scorer):
        # ftp_upload contains "upload" -> matches webhook/upload/post pattern -> 0.90
        score = scorer._score_external_transfer(True, "ftp_upload", {})
        assert score == 0.90

    def test_not_external(self, scorer):
        score = scorer._score_external_transfer(False, "cursor.execute", {})
        assert score == 0.0


class TestRiskScorerOperationType:
    """Test operation type scoring."""

    def test_select_score(self, scorer):
        score = scorer._score_operation_type("SELECT")
        assert score == 0.30

    def test_insert_score(self, scorer):
        score = scorer._score_operation_type("INSERT")
        assert score == 0.50

    def test_update_score(self, scorer):
        score = scorer._score_operation_type("UPDATE")
        assert score == 0.60

    def test_delete_score(self, scorer):
        score = scorer._score_operation_type("DELETE")
        assert score == 0.70

    def test_unknown_score(self, scorer):
        score = scorer._score_operation_type("UNKNOWN")
        assert score == 0.20


class TestRiskScorerIntegration:
    """Test full scoring pipeline."""

    def test_demo_scenario_high_score(self, scorer, analyzer, simulator):
        sql = "SELECT phone, id_card, address FROM customers WHERE status = 1"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        score = scorer.score("cursor.execute", {"sql": sql}, sql_info, effect)
        assert score >= 0.90

    def test_safe_query_low_score(self, scorer, analyzer, simulator):
        sql = "SELECT name, price FROM products WHERE category = 'electronics'"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("cursor.execute", {"sql": sql}, sql_info)
        score = scorer.score("cursor.execute", {"sql": sql}, sql_info, effect)
        assert score < 0.50

    def test_external_transfer_high_score(self, scorer, analyzer, simulator):
        sql = "SELECT phone FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("send_email", {"sql": sql, "to": "evil@test.com"}, sql_info)
        score = scorer.score("send_email", {"sql": sql, "to": "evil@test.com"}, sql_info, effect)
        assert score >= 0.90

    def test_score_capped_at_one(self, scorer, analyzer, simulator):
        sql = "SELECT phone, id_card, bank_account, address, email FROM customers"
        sql_info = analyzer.analyze(sql)
        effect = simulator.simulate("send_email", {"sql": sql, "to": "evil@test.com"}, sql_info)
        score = scorer.score("send_email", {"sql": sql}, sql_info, effect)
        assert score <= 1.0

    def test_none_effect_returns_zero(self, scorer, analyzer):
        sql_info = analyzer.analyze("SELECT 1")
        score = scorer.score("cursor.execute", {}, sql_info, None)
        assert score == 0.0


class TestRiskFactorBreakdown:
    """Test RiskFactorBreakdown dataclass."""

    def test_breakdown_fields(self):
        breakdown = RiskFactorBreakdown(
            sensitive_score=0.95,
            volume_score=0.50,
            bulk_score=0.30,
            external_score=0.0,
            operation_score=0.30,
            total_score=0.85,
            dominant_factor="sensitive_data"
        )
        assert breakdown.sensitive_score == 0.95
        assert breakdown.total_score == 0.85
        assert breakdown.dominant_factor == "sensitive_data"
