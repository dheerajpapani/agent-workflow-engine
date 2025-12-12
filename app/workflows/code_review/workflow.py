# app/workflows/code_review/workflow.py
from app.schemas.graph import NodeDefinition, EdgeDefinition, NodeType, GraphCreateRequest

def create_code_review_workflow() -> GraphCreateRequest:
    nodes = [
        NodeDefinition(id="extract", type=NodeType.FUNCTION, tool="extract_functions", config={"description": "Parse and extract function definitions"}),
        NodeDefinition(id="complexity", type=NodeType.FUNCTION, tool="check_complexity", config={"description": "Analyze code complexity"}),
        NodeDefinition(id="issues", type=NodeType.FUNCTION, tool="detect_issues", config={"description": "Detect code issues"}),
        NodeDefinition(id="suggestions", type=NodeType.FUNCTION, tool="suggest_improvements", config={"description": "Generate improvement suggestions"}),
        NodeDefinition(id="quality", type=NodeType.FUNCTION, tool="calculate_quality_score", config={"description": "Calculate final quality score"}),
    ]

    edges = [
        EdgeDefinition(source="extract", target="complexity"),
        EdgeDefinition(source="complexity", target="issues"),
        EdgeDefinition(source="issues", target="suggestions"),
        EdgeDefinition(source="suggestions", target="quality"),
        # Optional loop: go back from quality to complexity if quality not met
        EdgeDefinition(source="quality", target="complexity", condition="not state.get('quality_met', False)"),
    ]

    return GraphCreateRequest(
        name="Code Review Agent",
        description="Automated code review workflow with quality scoring",
        nodes=nodes,
        edges=edges,
        entry_node="extract",
    )

CODE_REVIEW_WORKFLOW = create_code_review_workflow()
