"""第1フェーズで Canvas へ注入する操作確認用データ。"""

from knowledge_tree.viewmodels.graph_viewmodels import (
    GraphEdgeViewModel,
    GraphNodeViewModel,
    GraphViewModel,
)


def build_demo_graph() -> GraphViewModel:
    """操作感を確認できる、研究構造を模した表示専用データを返す。"""
    nodes = (
        GraphNodeViewModel(
            id="goal",
            text="社会的・工学的な大きな目標",
            secondary_text="量子計算機を有用な技術にする",
            position_x=80.0,
            position_y=80.0,
            width=240.0,
            height=105.0,
            style_key="question",
        ),
        GraphNodeViewModel(
            id="operation",
            text="量子プロセッサを\n安定して運用するには？",
            secondary_text="システム上の課題",
            position_x=410.0,
            position_y=75.0,
            width=235.0,
            height=110.0,
            style_key="question",
        ),
        GraphNodeViewModel(
            id="diagnosis",
            text="診断・較正の時間と\n実験資源を削減できるか？",
            secondary_text="現在のボトルネック",
            position_x=750.0,
            position_y=75.0,
            width=255.0,
            height=110.0,
            style_key="question",
        ),
        GraphNodeViewModel(
            id="question",
            text="処置に必要な情報だけを\n抽出できるか？",
            secondary_text="現在検討中の問い",
            position_x=750.0,
            position_y=300.0,
            width=255.0,
            height=110.0,
            style_key="question",
        ),
        GraphNodeViewModel(
            id="evidence",
            text="既存の専用診断を比較する",
            secondary_text="Ramsey・echo・相関測定",
            position_x=410.0,
            position_y=310.0,
            width=235.0,
            height=105.0,
            style_key="default",
        ),
        GraphNodeViewModel(
            id="note",
            text="比較指標",
            secondary_text="shots / 設定数 / QPU占有時間 / 学習時間",
            position_x=1070.0,
            position_y=300.0,
            width=285.0,
            height=105.0,
            style_key="note",
        ),
        GraphNodeViewModel(
            id="warning",
            text="検証上の注意",
            secondary_text="量子を使うこと自体を目的にしない",
            position_x=1070.0,
            position_y=500.0,
            width=285.0,
            height=100.0,
            style_key="warning",
        ),
        GraphNodeViewModel(
            id="isolated",
            text="未整理のメモ",
            secondary_text="孤立ノードの表示例",
            position_x=80.0,
            position_y=500.0,
            width=220.0,
            height=95.0,
            style_key="default",
        ),
    )
    edges = (
        GraphEdgeViewModel("edge-goal", "goal", "operation", "具体化する", True, "default"),
        GraphEdgeViewModel("edge-operation", "operation", "diagnosis", "具体化する", True, "default"),
        GraphEdgeViewModel("edge-diagnosis", "diagnosis", "question", "検討する", True, "default"),
        GraphEdgeViewModel("edge-evidence", "evidence", "question", "比較する", True, "default"),
        GraphEdgeViewModel("edge-note", "question", "note", "評価する", False, "note"),
        GraphEdgeViewModel("edge-warning", "note", "warning", "注意する", True, "warning"),
    )
    return GraphViewModel(nodes=nodes, edges=edges)
