# tests/test_nodes.py
import pytest
from app.workflows.code_review import nodes as cr_nodes

SAMPLE_CODE = """
def add(a, b):
    \"\"\"Add two numbers\"\"\"
    result = a + b
    if result > 10:
        print("big")
    return result
"""

def test_extract_functions():
    state = {"code": SAMPLE_CODE}
    out = cr_nodes.extract_functions(state.copy())
    assert isinstance(out, dict)
    assert out.get("function_count", 0) == 1
    funcs = out.get("functions", [])
    assert funcs and funcs[0]["name"] == "add"

def test_check_complexity_and_scores():
    state = {"code": SAMPLE_CODE}
    state = cr_nodes.extract_functions(state)
    state = cr_nodes.check_complexity(state)
    assert "complexity" in state
    assert "by_function" in state["complexity"]
    assert state["complexity_score"] >= 0 and state["complexity_score"] <= 10

def test_detect_issues_and_issue_score():
    state = {"code": SAMPLE_CODE}
    state = cr_nodes.extract_functions(state)
    state = cr_nodes.detect_issues(state)
    assert "issues" in state
    assert isinstance(state["issues"], list)
    assert "issue_score" in state
    assert 0 <= state["issue_score"] <= 10

def test_calculate_quality_score():
    state = {"code": SAMPLE_CODE}
    state = cr_nodes.extract_functions(state)
    state = cr_nodes.check_complexity(state)
    state = cr_nodes.detect_issues(state)
    state = cr_nodes.calculate_quality_score(state)
    assert "quality_score" in state
    assert "quality_met" in state
    # quality_score should be numeric and quality_met boolean
    assert isinstance(state["quality_score"], (int, float))
    assert isinstance(state["quality_met"], bool)
