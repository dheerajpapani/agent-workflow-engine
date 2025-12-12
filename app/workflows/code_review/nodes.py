# app/workflows/code_review/nodes.py
import re
import ast
from typing import Any

def extract_functions(state: dict[str, Any]) -> dict[str, Any]:
    """
    Extract function definitions from code.
    Normalize escaped newlines if present (common when JSON is produced
    from PowerShell or some shell quoting).
    """
    code = state.get("code", "") or ""

    # If payload contains literal backslash sequences (e.g. "\\n") but no real newlines,
    # normalize them into real newline characters so ast.parse works correctly.
    if "\\n" in code and "\n" not in code:
        code = code.replace("\\r\\n", "\r\n").replace("\\n", "\n")

    functions = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "args": [arg.arg for arg in node.args.args],
                    "line_start": getattr(node, "lineno", None),
                    "line_end": getattr(node, "end_lineno", getattr(node, "lineno", None)),
                    "docstring": ast.get_docstring(node),
                    "decorators": [
                        ast.unparse(d) if hasattr(ast, "unparse") else str(d)
                        for d in node.decorator_list
                    ],
                })
    except SyntaxError as e:
        # Preserve parse error for debugging and bail out gracefully
        state["parse_error"] = str(e)
        state["functions"] = []
        state["function_count"] = 0
        return state

    state["functions"] = functions
    state["function_count"] = len(functions)
    return state


def check_complexity(state: dict[str, Any]) -> dict[str, Any]:
    code = state.get("code", "")
    functions = state.get("functions", [])

    complexity_keywords = [
        "if", "elif", "else", "for", "while",
        "try", "except", "with", "and", "or"
    ]

    total_complexity = 0
    function_complexity = {}

    for func in functions:
        func_name = func["name"]
        try:
            start = max(0, func.get("line_start", 1) - 1)
            end = func.get("line_end", start + 1)
            lines = code.split("\n")[start:end]
        except Exception:
            lines = []
        func_code = "\n".join(lines)
        complexity = 1
        for keyword in complexity_keywords:
            complexity += len(re.findall(rf'\b{keyword}\b', func_code))
        function_complexity[func_name] = complexity
        total_complexity += complexity

    avg_complexity = total_complexity / len(functions) if functions else 0
    state["complexity"] = {
        "total": total_complexity,
        "average": round(avg_complexity, 2),
        "by_function": function_complexity,
    }
    state["complexity_score"] = max(0, 10 - avg_complexity)
    return state


def detect_issues(state: dict[str, Any]) -> dict[str, Any]:
    code = state.get("code", "")
    functions = state.get("functions", [])
    issues = []

    patterns = [
        {"name": "bare_except", "pattern": r"except\s*:", "message": "Bare except clause - specify exception type", "severity": "warning"},
        {"name": "print_statement", "pattern": r"\bprint\s*\(", "message": "Print statement found - consider using logging", "severity": "info"},
        {"name": "hardcoded_password", "pattern": r"password\s*=\s*['\"]", "message": "Possible hardcoded password detected", "severity": "error"},
        {"name": "todo_comment", "pattern": r"#\s*(TODO|FIXME|HACK)", "message": "TODO/FIXME comment found", "severity": "info"},
        {"name": "long_line", "pattern": r".{120,}", "message": "Line exceeds 120 characters", "severity": "warning"},
        {"name": "mutable_default", "pattern": r"def\s+\w+\s*\([^)]*=\s*(\[\]|\{\})", "message": "Mutable default argument - use None instead", "severity": "error"},
    ]

    lines = code.split("\n")
    for i, line in enumerate(lines, 1):
        for pattern in patterns:
            if re.search(pattern["pattern"], line, re.IGNORECASE):
                issues.append({
                    "line": i,
                    "type": pattern["name"],
                    "message": pattern["message"],
                    "severity": pattern["severity"],
                    "code": line.strip()[:200],
                })

    for func in functions:
        if not func.get("docstring"):
            issues.append({
                "line": func.get("line_start"),
                "type": "missing_docstring",
                "message": f"Function '{func['name']}' missing docstring",
                "severity": "warning",
            })

    state["issues"] = issues
    state["issue_count"] = len(issues)

    error_count = sum(1 for i in issues if i["severity"] == "error")
    warning_count = sum(1 for i in issues if i["severity"] == "warning")
    issue_penalty = (error_count * 2) + (warning_count * 0.5)
    state["issue_score"] = max(0, 10 - issue_penalty)
    return state


def suggest_improvements(state: dict[str, Any]) -> dict[str, Any]:
    functions = state.get("functions", [])
    complexity = state.get("complexity", {})
    issues = state.get("issues", [])

    suggestions = []

    for func_name, func_complexity in complexity.get("by_function", {}).items():
        if func_complexity > 10:
            suggestions.append({"type": "refactor", "target": func_name, "message": f"Consider breaking down '{func_name}' - complexity is {func_complexity}", "priority": "high"})
        elif func_complexity > 5:
            suggestions.append({"type": "refactor", "target": func_name, "message": f"Function '{func_name}' could be simplified", "priority": "medium"})

    issue_types = {}
    for issue in issues:
        itype = issue["type"]
        issue_types[itype] = issue_types.get(itype, 0) + 1

    for issue_type, count in issue_types.items():
        if count > 2:
            suggestions.append({"type": "pattern", "target": issue_type, "message": f"Multiple '{issue_type}' issues found ({count}) - consider systematic fix", "priority": "medium"})

    if not functions:
        suggestions.append({"type": "structure", "target": "code", "message": "No functions found - consider organizing code into functions", "priority": "high"})

    if len(functions) > 10:
        suggestions.append({"type": "structure", "target": "module", "message": f"Module has {len(functions)} functions - consider splitting into modules", "priority": "medium"})

    state["suggestions"] = suggestions
    state["suggestion_count"] = len(suggestions)
    return state


def calculate_quality_score(state: dict[str, Any]) -> dict[str, Any]:
    complexity_score = state.get("complexity_score", 5)
    issue_score = state.get("issue_score", 5)
    quality_score = (complexity_score * 0.4) + (issue_score * 0.6)
    state["quality_score"] = round(quality_score, 2)
    threshold = state.get("quality_threshold", 7)
    state["quality_met"] = quality_score >= threshold
    return state


def register_code_review_tools(registry) -> None:
    registry.register_function(
        extract_functions,
        name="extract_functions",
        description="Extract function definitions from Python code"
    )
    registry.register_function(
        check_complexity,
        name="check_complexity",
        description="Analyze code complexity using heuristics"
    )
    registry.register_function(
        detect_issues,
        name="detect_issues",
        description="Detect common code issues"
    )
    registry.register_function(
        suggest_improvements,
        name="suggest_improvements",
        description="Generate suggestions"
    )
    registry.register_function(
        calculate_quality_score,
        name="calculate_quality_score",
        description="Calculate overall quality score"
    )
