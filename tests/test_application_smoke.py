"""アプリケーションUIの最小スモークテスト。"""

from knowledge_tree.ui.main_window import MainWindow
from PyQt6.QtCore import QPointF


def test_main_window_displays_the_canvas(qtbot: object) -> None:
    """MainWindowが生成され、Canvasへサンプルが投入される。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle().startswith("KnowledgeTree")
    assert window.canvas.selected_node_ids() == []


def test_adding_an_edge_keeps_an_externally_updated_node_position(qtbot: object) -> None:
    """接続追加でViewModelを再投入しても、手動位置を初期値へ戻さない。"""
    window = MainWindow()
    qtbot.addWidget(window)

    window._show_node_move("isolated", QPointF(80.0, 500.0), QPointF(620.0, 430.0))
    window._create_demo_edge("question", "isolated")

    assert window.canvas._nodes["isolated"].pos() == QPointF(620.0, 430.0)
