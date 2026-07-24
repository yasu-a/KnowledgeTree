"""アプリケーションUIの最小スモークテスト。"""

from pathlib import Path

from knowledge_tree.ui.main_window import MainWindow
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QLabel
from knowledge_tree.project_session import ProjectSession
from knowledge_tree.project_storage import ProjectStorage
from knowledge_tree.reference_catalog import Book, ReferenceKind, ReferenceLink
from knowledge_tree import application as application_module
from knowledge_tree.application_version import APPLICATION_VERSION
from knowledge_tree.ui.about_dialog import AboutDialog
from knowledge_tree.domain_graph import ReferenceNode


def _node_id(window: MainWindow, title: str) -> str:
    """デモの表示タイトルから、テスト対象の生成済みノードIDを取得する。"""
    return next(node.id for node in window._demo_graph_editor.semantic_graph().nodes if getattr(node, "title", None) == title)


def _reference_node_id(window: MainWindow) -> str:
    """デモの文献ノードIDを取得する。"""
    return next(node.id for node in window._demo_graph_editor.semantic_graph().nodes if isinstance(node, ReferenceNode))


def _edge_id(window: MainWindow, source_node_id: str, target_node_id: str) -> str:
    """両端ノードから、テスト対象の生成済みエッジIDを取得する。"""
    return next(edge.id for edge in window._demo_graph_editor.semantic_graph().edges if (edge.source_node_id, edge.target_node_id) == (source_node_id, target_node_id))


def test_main_window_displays_the_canvas(qtbot: object) -> None:
    """MainWindowが生成され、Canvasへサンプルが投入される。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.windowTitle().startswith("KnowledgeTree")
    assert window.canvas.selected_node_ids() == []


def test_about_dialog_displays_the_unified_knowledge_tree_version(qtbot: object) -> None:
    """Aboutダイアログはアプリと保存形式に共通のバージョンを表示する。"""
    dialog = AboutDialog(APPLICATION_VERSION)
    qtbot.addWidget(dialog)

    labels = [label.text() for label in dialog.findChildren(QLabel)]

    assert any("1.0" in text and "バージョン" in text for text in labels)
    assert any("https://github.com/yasu-a/KnowledgeTree" in text for text in labels)


def test_application_run_initializes_the_main_startup_path(monkeypatch: object, tmp_path: Path) -> None:
    """main.pyから呼ばれるrunは、アプリとNavigatorを初期化してイベントループへ進む。"""
    class FakeApplication:
        """イベントループを開始せず、runの初期化だけ検証する代替アプリ。"""

        def __init__(self) -> None:
            self.application_name = ""

        def setApplicationName(self, application_name: str) -> None:
            """設定されたアプリケーション名を記録する。"""
            self.application_name = application_name

        def setApplicationVersion(self, application_version: str) -> None:
            """設定されたアプリケーション版を記録する。"""
            assert application_version == "1.0"

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

    isolated_id = _node_id(window, "未整理のメモ")
    question_id = _node_id(window, "処置に必要な情報だけを\n抽出できるか？")
    window._show_node_move(isolated_id, QPointF(80.0, 500.0), QPointF(620.0, 430.0))
    window._create_demo_edge(question_id, isolated_id)

    assert window.canvas._nodes[isolated_id].pos() == QPointF(620.0, 430.0)


def test_inspector_edits_a_selected_question_and_edge(qtbot: object) -> None:
    """右側インスペクタの編集は、外部状態とCanvasへ即時反映される。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    goal_id = _node_id(window, "社会的・工学的な大きな目標")
    operation_id = _node_id(window, "量子プロセッサを\n安定して運用するには？")
    window.canvas.select_node(goal_id)
    qtbot.waitUntil(lambda: window.inspector.title_edit.text() == "社会的・工学的な大きな目標")
    window.inspector.title_edit.setText("更新した質問")
    window.inspector.title_edit.editingFinished.emit()
    window.inspector.combination_combo.setCurrentIndex(2)

    node = window._demo_graph_editor.node_view_model(goal_id)
    assert (node.text, node.badge_text) == ("更新した質問", "OR")
    assert window.canvas._nodes[goal_id]._view_model.badge_text == "OR"

    window.canvas.select_edge(_edge_id(window, goal_id, operation_id))
    qtbot.waitUntil(lambda: window.inspector.edge_type_combo.currentText() == "refines")
    assert window.inspector.edge_type_combo.itemIcon(0).isNull() is False


def test_node_kinds_select_the_default_relation_for_new_edges(qtbot: object) -> None:
    """新規エッジには始点・終点のノード種類に対応する関係を自動適用する。"""
    window = MainWindow()
    qtbot.addWidget(window)

    evidence_id = _reference_node_id(window)
    question_id = _node_id(window, "処置に必要な情報だけを\n抽出できるか？")
    window._create_demo_edge(evidence_id, question_id)

    edge = next(edge for edge in window._demo_graph_editor.graph().edges if edge.source_node_id == evidence_id and edge.target_node_id == question_id)
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
    goal_id = _node_id(window, "社会的・工学的な大きな目標")
    operation_id = _node_id(window, "量子プロセッサを\n安定して運用するには？")
    window._show_node_inspector(goal_id)
    assert window.inspector_dock.isVisible() is True
    assert window.canvas.selected_node_ids() == [goal_id]

    window.inspector_dock.hide()
    edge_id = _edge_id(window, goal_id, operation_id)
    window._show_edge_inspector(edge_id)
    assert window.inspector_dock.isVisible() is True
    assert window.canvas.selected_edge_ids() == [edge_id]


def test_opening_inspector_preserves_the_canvas_top_left_scene_position(qtbot: object) -> None:
    """右側ドックを表示しても、Canvas左上のscene座標は見かけ上移動しない。"""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.inspector_dock.hide()
    qtbot.wait(10)
    top_left_before = window.canvas.mapToScene(window.canvas.viewport().rect().topLeft())

    window._show_node_inspector(_node_id(window, "社会的・工学的な大きな目標"))
    qtbot.wait(20)
    top_left_after = window.canvas.mapToScene(window.canvas.viewport().rect().topLeft())

    assert abs(top_left_after.x() - top_left_before.x()) < 2.0
    assert abs(top_left_after.y() - top_left_before.y()) < 2.0


def test_disallowed_node_kind_combination_does_not_create_an_edge(qtbot: object) -> None:
    """関係定義にないノード種類の組合せでは、新規エッジを作成しない。"""
    window = MainWindow()
    qtbot.addWidget(window)

    edge_count_before = len(window._demo_graph_editor.graph().edges)
    window._create_demo_edge(_node_id(window, "処置に必要な情報だけを\n抽出できるか？"), _node_id(window, "未整理のメモ"))

    assert len(window._demo_graph_editor.graph().edges) == edge_count_before


def test_question_deletion_keeps_only_same_type_question_connections(qtbot: object) -> None:
    """問い削除ではrefinesだけをつなぎ直し、文献由来の関係は切断する。"""
    window = MainWindow()
    qtbot.addWidget(window)
    evidence_id = _reference_node_id(window)
    operation_id = _node_id(window, "量子プロセッサを\n安定して運用するには？")
    goal_id = _node_id(window, "社会的・工学的な大きな目標")
    diagnosis_id = _node_id(window, "診断・較正の時間と\n実験資源を削減できるか？")
    window._create_demo_edge(evidence_id, operation_id)

    window._request_node_deletion(operation_id)

    edges = window._demo_graph_editor.graph().edges
    assert all(operation_id not in (edge.source_node_id, edge.target_node_id) for edge in edges)
    assert any((edge.source_node_id, edge.target_node_id, edge.label) == (goal_id, diagnosis_id, "refines") for edge in edges)
    assert not any((edge.source_node_id, edge.target_node_id) == (evidence_id, diagnosis_id) for edge in edges)


def test_contribution_edge_cannot_be_split_by_inserting_a_question(qtbot: object) -> None:
    """contributesToを問いで分割する操作は、関係規則により反映しない。"""
    window = MainWindow()
    qtbot.addWidget(window)
    graph_before = window._demo_graph_editor.graph()

    window._insert_node_on_edge(_edge_id(window, _reference_node_id(window), _node_id(window, "処置に必要な情報だけを\n抽出できるか？")))

    graph_after = window._demo_graph_editor.graph()
    assert len(graph_after.nodes) == len(graph_before.nodes)
    assert len(graph_after.edges) == len(graph_before.edges)


def test_main_window_autosaves_changes_when_opened_from_a_project(qtbot: object, tmp_path: Path) -> None:
    """プロジェクトとして開いたWindowの編集は、明示保存なしで次回読込へ反映される。"""
    storage = ProjectStorage(tmp_path / "userdata")
    storage.create_project("自動保存")
    window = MainWindow(ProjectSession.open(storage, "自動保存"))
    qtbot.addWidget(window)

    isolated_id = _node_id(window, "未整理のメモ")
    window._show_node_move(isolated_id, QPointF(80.0, 500.0), QPointF(620.0, 430.0))

    loaded = storage.load_project("自動保存")
    isolated_layout = loaded.layout.node_layout(isolated_id)
    assert (isolated_layout.position_x, isolated_layout.position_y) == (620.0, 430.0)


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
    assert window._demo_graph_editor.reference_link(node_id) is None

    window.canvas.select_node(node_id)
    index = next(
        item_index
        for item_index in range(window.inspector.reference_combo.count())
        if window.inspector.reference_combo.itemData(item_index) == ReferenceLink(ReferenceKind.BOOK, record.id)
    )
    window.inspector.reference_combo.setCurrentIndex(index)

    updated = window._demo_graph_editor.node_view_model(node_id)
    assert (window._demo_graph_editor.reference_link(node_id), updated.text, updated.badge_text) == (ReferenceLink(ReferenceKind.BOOK, record.id), "選択する書籍", "Book")
    window.canvas.clear_selection()
    window.canvas.select_node(node_id)

    assert window.inspector.reference_combo.currentData() == ReferenceLink(ReferenceKind.BOOK, record.id)


def test_reference_node_keeps_a_link_when_its_catalog_record_is_deleted(qtbot: object, tmp_path: Path) -> None:
    """文献マスタから消えた参照先も、ノードはリンクを失わず欠損状態として表示する。"""
    storage = ProjectStorage(tmp_path / "userdata")
    storage.create_project("欠損文献")
    session = ProjectSession.open(storage, "欠損文献")
    link = ReferenceLink(ReferenceKind.BOOK, "book-001")
    session.reference_catalog.replace_books((Book(link.id, "削除される書籍"),))
    window = MainWindow(session)
    qtbot.addWidget(window)

    window._create_reference_node(QPointF(600.0, 400.0))
    node_id = window.canvas.selected_node_ids()[0]
    window._update_reference_from_inspector(node_id, link)
    session.reference_catalog.replace_books(())
    window._sync_reference_nodes_from_catalog()
    updated = window._demo_graph_editor.node_view_model(node_id)
    window.canvas.clear_selection()
    window.canvas.select_node(node_id)

    assert window._demo_graph_editor.reference_link(node_id) == link
    assert updated.text == "削除された文献"
    assert updated.badge_text == "Book"
    assert window.inspector.reference_combo.currentData() == link
    assert "削除された文献" in window.inspector.reference_combo.currentText()
