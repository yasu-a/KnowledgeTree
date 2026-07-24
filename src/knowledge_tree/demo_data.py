"""新規プロジェクトへ投入する、意味論的なデモデータ。"""

from knowledge_tree.domain_graph import ChildCombination, KnowledgeGraph
from knowledge_tree.graph_factory import GraphFactory
from knowledge_tree.graph_layout import EdgeLayout, GraphLayout, NodeLayout
from knowledge_tree.project_content import ProjectContent
from knowledge_tree.project_settings import ProjectSettings
from knowledge_tree.reference_catalog import ReferenceKind, ReferenceLink


def build_demo_project(graph_factory: GraphFactory | None = None) -> ProjectContent:
    """GraphFactoryで生成した意味論・レイアウト・設定の初期プロジェクトを返す。"""
    factory = graph_factory or GraphFactory()
    # 生成済みノードのIDだけをエッジとレイアウトに渡し、手書きIDを持ち込まない。
    goal = factory.create_question("社会的・工学的な大きな目標", "量子計算機を有用な技術にする")
    operation = factory.create_question("量子プロセッサを\n安定して運用するには？", "システム上の課題")
    diagnosis = factory.create_question("診断・較正の時間と\n実験資源を削減できるか？", "現在のボトルネック")
    question = factory.create_question("処置に必要な情報だけを\n抽出できるか？", "現在検討中の問い", ChildCombination.ALL)
    evidence = factory.create_reference(ReferenceLink(ReferenceKind.PAPER, "paper-001"))
    note = factory.create_memo("比較指標", "shots / 設定数 / QPU占有時間 / 学習時間")
    warning = factory.create_memo("検証上の注意", "量子を使うこと自体を目的にしない")
    isolated = factory.create_memo("未整理のメモ", "孤立ノードの表示例")
    nodes = (goal, operation, diagnosis, question, evidence, note, warning, isolated)
    edges = (
        factory.create_edge(goal.id, operation.id, "refines"),
        factory.create_edge(operation.id, diagnosis.id, "refines"),
        factory.create_edge(diagnosis.id, question.id, "refines"),
        factory.create_edge(evidence.id, question.id, "contributesTo"),
        factory.create_edge(note.id, question.id, "contributesTo"),
    )
    layout = GraphLayout(
        (
            NodeLayout(goal.id, 80.0, 80.0, 240.0, 105.0),
            NodeLayout(operation.id, 410.0, 75.0, 235.0, 110.0),
            NodeLayout(diagnosis.id, 750.0, 75.0, 255.0, 110.0),
            NodeLayout(question.id, 750.0, 300.0, 255.0, 110.0),
            NodeLayout(evidence.id, 410.0, 310.0, 235.0, 105.0),
            NodeLayout(note.id, 1070.0, 300.0, 285.0, 105.0),
            NodeLayout(warning.id, 1070.0, 500.0, 285.0, 100.0),
            NodeLayout(isolated.id, 80.0, 500.0, 220.0, 95.0),
        ),
        tuple(EdgeLayout(edge.id) for edge in edges),
    )
    return ProjectContent(KnowledgeGraph(nodes, edges), layout, ProjectSettings())
