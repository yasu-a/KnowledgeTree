"""グラフ変更のドメイン規則を検証する。"""

from knowledge_tree.graph_mutation_service import Graph, GraphEdge, GraphMutationService, GraphNode
from knowledge_tree.node_kind import NodeKind
from knowledge_tree.project_settings import ProjectSettings


def test_deleting_a_question_keeps_only_same_type_question_connections() -> None:
    """問い削除では、同じ関係種類の問い間接続だけを維持する。"""
    graph = Graph(
        (
            GraphNode("a", NodeKind.QUESTION),
            GraphNode("b", NodeKind.QUESTION),
            GraphNode("c", NodeKind.QUESTION),
            GraphNode("reference", NodeKind.REFERENCE),
        ),
        (
            GraphEdge("a-b", "a", "b", "refines", True),
            GraphEdge("b-c", "b", "c", "refines", True),
            GraphEdge("reference-b", "reference", "b", "contributesTo", True),
        ),
    )

    plan = GraphMutationService(graph, ProjectSettings().edge_types()).plan_node_deletion("b")

    assert [(item.source_node_id, item.target_node_id, item.label) for item in plan.reconnections] == [
        ("a", "c", "refines"),
    ]


def test_deleting_a_question_does_not_create_many_to_many_reconnections() -> None:
    """同一関係でも多対多の問い接続は、削除時に自動再接続しない。"""
    graph = Graph(
        tuple(GraphNode(node_id, NodeKind.QUESTION) for node_id in ("a", "b", "center", "d", "e")),
        (
            GraphEdge("a-center", "a", "center", "refines", True),
            GraphEdge("b-center", "b", "center", "refines", True),
            GraphEdge("center-d", "center", "d", "refines", True),
            GraphEdge("center-e", "center", "e", "refines", True),
        ),
    )

    plan = GraphMutationService(graph, ProjectSettings().edge_types()).plan_node_deletion("center")

    assert plan.reconnections == ()


def test_reconnection_rejects_an_endpoint_not_allowed_by_the_relation_label() -> None:
    """関係ラベルの許可範囲外へエッジを付け替える操作を拒否する。"""
    graph = Graph(
        (
            GraphNode("question-a", NodeKind.QUESTION),
            GraphNode("question-b", NodeKind.QUESTION),
            GraphNode("reference", NodeKind.REFERENCE),
        ),
        (GraphEdge("refines", "question-a", "question-b", "refines", True),),
    )
    service = GraphMutationService(graph, ProjectSettings().edge_types())

    result = service.validate_reconnect_edge("refines", "reference", "question-b")

    assert result.allowed is False


def test_only_a_relation_that_accepts_two_question_nodes_can_be_split_with_a_question() -> None:
    """問いを挿入する分割は、分割後の二本とも許可される関係だけに限定する。"""
    graph = Graph(
        (
            GraphNode("question-a", NodeKind.QUESTION),
            GraphNode("question-b", NodeKind.QUESTION),
            GraphNode("reference", NodeKind.REFERENCE),
        ),
        (
            GraphEdge("refines", "question-a", "question-b", "refines", True),
            GraphEdge("contributes", "reference", "question-b", "contributesTo", True),
        ),
    )
    service = GraphMutationService(graph, ProjectSettings().edge_types())

    assert service.validate_split_edge("refines", NodeKind.QUESTION).allowed is True
    assert service.validate_split_edge("contributes", NodeKind.QUESTION).allowed is False
