"""アプリケーションUIの最小スモークテスト。"""

from pathlib import Path

from knowledge_tree.ui.main_window import MainWindow
from PyQt6.QtCore import QPointF
from knowledge_tree.project_session import ProjectSession
from knowledge_tree.project_storage import ProjectStorage
from knowledge_tree.reference_catalog import Book, ReferenceKind, ReferenceLink
from knowledge_tree import application as application_module


def test_main_window_displays_the_canvas(qtbot: object) -> None:
    """MainWindowが生成され、Canvasへサンプルが投入される。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle().startswith("KnowledgeTree")
    assert window.canvas.selected_node_ids() == []


def test_application_run_initializes_the_main_startup_path(monkeypatch: object, tmp_path: Path) -> None:
    """main.pyから呼ばれるrunは、アプリとNavigatorを初期化してイベントループへ進む。"""
    class FakeApplication:
        """イベントループを開始せず、runの初期化だけ検証する代替アプリ。"""

        def __init__(self) -> None:
            self.application_name = ""

        def setApplicationName(self, application_name: str) -> None:
            """設定されたアプリケーション名を記録する。"""
            self.application_name = application_name

        def exec(self) -> int:
            """テスト用の終了コードを返す。"""
            return 23

    class FakeNavigator:
        """実ウィンドウを開かず、起動要求を検証する代替Navigator。"""

        def __init__(self, application: FakeApplication, project_storage: object, global_settings_store: object, session_state_store: object) -> None:
            """runから渡される起動依存を記録する。"""
            assert application.application_name == "KnowledgeTree"
            assert project_storage is not None
            assert global_settings_store is not None
            assert session_state_store is not None

        def start(self) -> bool:
            """起動成功を返し、イベントループ開始を要求する。"""
            return True

    fake_application = FakeApplication()
    monkeypatch.setattr(application_module, "QApplication", lambda arguments: fake_application)
    monkeypatch.setattr(application_module, "ApplicationNavigator", FakeNavigator)
    monkeypatch.chdir(tmp_path)

    assert application_module.run() == 23


def test_adding_an_edge_keeps_an_externally_updated_node_position(qtbot: object) -> None:
    """接続追加でViewModelを再投入しても、手動位置を初期値へ戻さない。"""
    window = MainWindow()
    qtbot.addWidget(window)

    window._show_node_move("isolated", QPointF(80.0, 500.0), QPointF(620.0, 430.0))
    window._create_demo_edge("question", "isolated")

    assert window.canvas._nodes["isolated"].pos() == QPointF(620.0, 430.0)


def test_inspector_edits_a_selected_question_and_edge(qtbot: object) -> None:
    """右側インスペクタの編集は、外部状態とCanvasへ即時反映される。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.canvas.select_node("goal")
    qtbot.waitUntil(lambda: window.inspector.title_edit.text() == "社会的・工学的な大きな目標")
    window.inspector.title_edit.setText("更新した質問")
    window.inspector.title_edit.editingFinished.emit()
    window.inspector.combination_combo.setCurrentIndex(2)

    node = window._demo_graph_editor.node_view_model("goal")
    assert (node.text, node.badge_text) == ("更新した質問", "OR")
    assert window.canvas._nodes["goal"]._view_model.badge_text == "OR"

    window.canvas.select_edge("edge-goal")
    qtbot.waitUntil(lambda: window.inspector.edge_type_combo.currentText() == "refines")
    assert window.inspector.edge_type_combo.itemIcon(0).isNull() is False


def test_node_kinds_select_the_default_relation_for_new_edges(qtbot: object) -> None:
    """新規エッジには始点・終点のノード種類に対応する関係を自動適用する。"""
    window = MainWindow()
    qtbot.addWidget(window)

    window._create_demo_edge("evidence", "question")

    edge = next(edge for edge in window._demo_graph_editor.graph().edges if edge.source_node_id == "evidence" and edge.target_node_id == "question")
    assert (edge.label, edge.style_key) == ("contributesTo", "global-edge-type:contributes-to")


def test_toolbar_does_not_show_a_default_relation_combo(qtbot: object) -> None:
    """関係は接続するノード種類から決まるため、既定ラベルコンボを表示しない。"""
    window = MainWindow()
    qtbot.addWidget(window)

    assert hasattr(window, "default_edge_label_combo") is False


def test_inspector_can_be_reopened_from_the_view_menu_and_double_click_handlers(qtbot: object) -> None:
    """閉じたインスペクタは表示メニューとダブルクリック操作で再表示できる。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    window.inspector_dock.hide()
    window.inspector_visibility_action.trigger()
    assert window.inspector_dock.isVisible() is True

    window.inspector_dock.hide()
    window._show_node_inspector("goal")
    assert window.inspector_dock.isVisible() is True
    assert window.canvas.selected_node_ids() == ["goal"]

    window.inspector_dock.hide()
    window._show_edge_inspector("edge-goal")
    assert window.inspector_dock.isVisible() is True
    assert window.canvas.selected_edge_ids() == ["edge-goal"]


def test_opening_inspector_preserves_the_canvas_top_left_scene_position(qtbot: object) -> None:
    """右側ドックを表示しても、Canvas左上のscene座標は見かけ上移動しない。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.inspector_dock.hide()
    qtbot.wait(10)
    top_left_before = window.canvas.mapToScene(window.canvas.viewport().rect().topLeft())

    window._show_node_inspector("goal")
    qtbot.wait(20)
    top_left_after = window.canvas.mapToScene(window.canvas.viewport().rect().topLeft())

    assert abs(top_left_after.x() - top_left_before.x()) < 2.0
    assert abs(top_left_after.y() - top_left_before.y()) < 2.0


def test_disallowed_node_kind_combination_does_not_create_an_edge(qtbot: object) -> None:
    """関係定義にないノード種類の組合せでは、新規エッジを作成しない。"""
    window = MainWindow()
    qtbot.addWidget(window)

    edge_count_before = len(window._demo_graph_editor.graph().edges)
    window._create_demo_edge("question", "isolated")

    assert len(window._demo_graph_editor.graph().edges) == edge_count_before


def test_main_window_autosaves_changes_when_opened_from_a_project(qtbot: object, tmp_path: Path) -> None:
    """プロジェクトとして開いたWindowの編集は、明示保存なしで次回読込へ反映される。"""
    storage = ProjectStorage(tmp_path / "userdata")
    storage.create_project("自動保存")
    window = MainWindow(ProjectSession.open(storage, "自動保存"))
    qtbot.addWidget(window)

    window._show_node_move("isolated", QPointF(80.0, 500.0), QPointF(620.0, 430.0))

    loaded = storage.load_project("自動保存")
    isolated_node = next(node for node in loaded.graph.nodes if node.id == "isolated")
    assert (isolated_node.position_x, isolated_node.position_y) == (620.0, 430.0)


def test_reference_node_is_created_unselected_and_can_select_a_catalog_record(qtbot: object, tmp_path: Path) -> None:
    """文献ノードは追加時にマスタを作らず、インスペクタで既存文献を関連付けられる。"""
    storage = ProjectStorage(tmp_path / "userdata")
    storage.create_project("文献選択")
    session = ProjectSession.open(storage, "文献選択")
    record = Book("book-001", "選択する書籍")
    session.reference_catalog.replace_books((record,))
    window = MainWindow(session)
    qtbot.addWidget(window)

    window._create_reference_node(QPointF(600.0, 400.0))
    node_id = window.canvas.selected_node_ids()[0]
    created = window._demo_graph_editor.node_view_model(node_id)
    assert created.reference_link is None

    window.canvas.select_node(node_id)
    index = next(
        item_index
        for item_index in range(window.inspector.reference_combo.count())
        if window.inspector.reference_combo.itemData(item_index) == ReferenceLink(ReferenceKind.BOOK, record.id)
    )
    window.inspector.reference_combo.setCurrentIndex(index)

    updated = window._demo_graph_editor.node_view_model(node_id)
    assert (updated.reference_link, updated.text, updated.badge_text) == (ReferenceLink(ReferenceKind.BOOK, record.id), "選択する書籍", "Book")
    window.canvas.clear_selection()
    window.canvas.select_node(node_id)

    assert window.inspector.reference_combo.currentData() == ReferenceLink(ReferenceKind.BOOK, record.id)
