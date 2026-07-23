"""一つのプロジェクトセッションを編集するMainWindow。"""

from PyQt6.QtCore import QEvent, QPoint, QPointF, QSignalBlocker, QTimer, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QCloseEvent, QColor, QIcon, QKeySequence, QPixmap
from PyQt6.QtWidgets import QDialogButtonBox, QDockWidget, QMainWindow, QMenu, QStatusBar, QToolBar, QVBoxLayout

from knowledge_tree.color_palette import ColorPalette
from knowledge_tree.demo_graph_editor import ChildCombination, DemoGraphEditor
from knowledge_tree.graph.graph_canvas_widget import GraphCanvasWidget
from knowledge_tree.graph.styles import StyleRegistry
from knowledge_tree.project_session import ProjectSession
from knowledge_tree.project_settings import EdgeType
from knowledge_tree.node_kind import NodeKind
from knowledge_tree.reference_catalog import Book, Paper, ReferenceKind, ReferenceLink, Website
from knowledge_tree.ui.edge_type_editor_widget import EdgeTypeEditorWidget
from knowledge_tree.ui.property_inspector import PropertyInspector
from knowledge_tree.ui.reference_catalog_dialog import ReferenceCatalogDialog
from knowledge_tree.ui.save_cancel_dialog import SaveCancelDialog


class MainWindow(QMainWindow):
    """一つのプロジェクトセッションのCanvas編集と入力処理を担当する。"""

    project_list_requested = pyqtSignal()
    global_settings_requested = pyqtSignal()
    project_activated = pyqtSignal(str)
    project_closed = pyqtSignal(str)

    def __init__(self, project_session: ProjectSession | None = None) -> None:
        """指定プロジェクトのCanvas、メニュー、編集状態を初期化する。"""
        super().__init__()
        self._project_session = project_session or ProjectSession.demo()
        self.setWindowTitle(f"KnowledgeTree - {self._project_session.project_name}")
        self.resize(1200, 760)
        self.canvas = GraphCanvasWidget(self)
        self.setCentralWidget(self.canvas)
        self.project_settings = self._project_session.project_settings
        self._register_edge_type_styles()
        self._create_property_inspector()
        self._create_actions()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_status_bar()
        self._connect_canvas_events()
        self._demo_graph_editor = self._project_session.graph_editor
        self.canvas.set_graph(self._demo_graph_editor.graph())
        QTimer.singleShot(0, self.canvas.fit_all)
        self.statusBar().showMessage("背景をドラッグして移動できます。ノード辺で新規接続、エッジ端で付け替え・削除できます。")

    def _create_actions(self) -> None:
        """メニューとツールバーで共用するアクションを作成する。"""
        self.fit_all_action = QAction("全体を表示", self)
        self.fit_all_action.setShortcut("F")
        self.fit_all_action.triggered.connect(self.canvas.fit_all)

        self.close_project_action = QAction("プロジェクトを閉じる", self)
        self.close_project_action.setShortcut(QKeySequence.StandardKey.Close)
        self.close_project_action.triggered.connect(self.close)

        self.open_project_action = QAction("プロジェクトを開く…", self)
        self.open_project_action.triggered.connect(self.project_list_requested.emit)

        self.global_settings_action = QAction("全体設定…", self)
        self.global_settings_action.triggered.connect(self.global_settings_requested.emit)

        self.project_settings_action = QAction("⚙", self)
        self.project_settings_action.setToolTip("プロジェクト設定")
        self.project_settings_action.triggered.connect(self._show_project_settings)

        self.reference_catalog_action = QAction("文献を管理…", self)
        self.reference_catalog_action.setToolTip("文献を管理")
        self.reference_catalog_action.triggered.connect(lambda: self._show_reference_catalog())

    def _create_menu_bar(self) -> None:
        """ファイル・表示メニューを構築する。"""
        file_menu = self.menuBar().addMenu("ファイル")
        file_menu.addAction(self.open_project_action)
        file_menu.addAction(self.global_settings_action)
        file_menu.addAction(self.reference_catalog_action)
        file_menu.addSeparator()
        file_menu.addAction(self.close_project_action)
        view_menu = self.menuBar().addMenu("表示")
        view_menu.addAction(self.fit_all_action)
        view_menu.addAction(self.inspector_visibility_action)

    def _create_toolbar(self) -> None:
        """表示操作用のツールバーを構築する。"""
        toolbar = QToolBar("表示", self)
        toolbar.setMovable(False)
        toolbar.addAction(self.project_settings_action)
        toolbar.addAction(self.reference_catalog_action)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _create_property_inspector(self) -> None:
        """Canvasの選択対象を編集する右側ドックを作成する。"""
        self.inspector = PropertyInspector(self.project_settings, self)
        self.inspector_dock = QDockWidget("インスペクタ", self)
        self.inspector_dock.setObjectName("property-inspector-dock")
        self.inspector_dock.setWidget(self.inspector)
        self.inspector_dock.setMinimumWidth(260)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
        self.inspector_visibility_action = QAction("インスペクタ", self)
        self.inspector_visibility_action.setCheckable(True)
        self.inspector_visibility_action.setChecked(True)
        self.inspector_visibility_action.triggered.connect(self._toggle_inspector_visibility)
        self.inspector_dock.visibilityChanged.connect(self.inspector_visibility_action.setChecked)

    def _create_status_bar(self) -> None:
        """操作結果を表示するステータスバーを設定する。"""
        self.setStatusBar(QStatusBar(self))

    def _show_project_settings(self) -> None:
        """エッジ種類コレクションを編集するプロジェクト設定ダイアログを表示する。"""
        changes_pending = [False]
        edited_settings = self.project_settings.copy()
        dialog = SaveCancelDialog(lambda: changes_pending[0], self)
        dialog.setWindowTitle("プロジェクト設定")
        dialog.resize(600, 500)
        editor = EdgeTypeEditorWidget(edited_settings, dialog)
        editor.edge_types_changed.connect(lambda: changes_pending.__setitem__(0, True))
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            parent=dialog,
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.discard)
        layout = QVBoxLayout(dialog)
        layout.addWidget(editor)
        layout.addWidget(buttons)
        if dialog.exec() == SaveCancelDialog.DialogCode.Accepted:
            self.project_settings.replace_with(edited_settings)
            self._apply_project_settings_changes()

    def _show_reference_catalog(self, active_reference_link: ReferenceLink | None = None) -> None:
        """文献マスタの管理ダイアログを開き、参照元ノードがあれば該当文献を選択する。"""
        catalog = self._project_session.reference_catalog
        if catalog is None:
            self.statusBar().showMessage("保存先のないデモでは文献マスタを編集できません。")
            return
        dialog = ReferenceCatalogDialog(catalog, active_reference_link, self)
        dialog.catalog_changed.connect(self._sync_reference_nodes_from_catalog)
        dialog.exec()
        self._show_selection(self.canvas.selected_node_ids(), self.canvas.selected_edge_ids())

    def _toggle_inspector_visibility(self, visible: bool) -> None:
        """表示メニューからインスペクタを切り替え、Canvas左上のscene位置を維持する。"""
        top_left_position = self._canvas_scene_top_left()
        self.inspector_dock.setVisible(visible)
        self._restore_canvas_top_left_after_layout(top_left_position)

    def _show_inspector_without_moving_canvas(self) -> None:
        """インスペクタを表示し、ドック幅の変化によるCanvasの見かけの移動を防ぐ。"""
        if self.inspector_dock.isVisible():
            return
        top_left_position = self._canvas_scene_top_left()
        self.inspector_dock.show()
        self._restore_canvas_top_left_after_layout(top_left_position)

    def _canvas_scene_top_left(self) -> QPointF:
        """現在のCanvas表示領域の左上に対応するscene座標を返す。"""
        return self.canvas.mapToScene(self.canvas.viewport().rect().topLeft())

    def _restore_canvas_top_left_after_layout(self, top_left_position: QPointF) -> None:
        """ドック表示でレイアウトが確定した後、Canvas左上を元のscene位置へ戻す。"""
        QTimer.singleShot(0, lambda: self._align_canvas_top_left(top_left_position))

    def _align_canvas_top_left(self, top_left_position: QPointF) -> None:
        """現在の左上との差分だけCanvasを移動し、画面上のノード位置を維持する。"""
        current_top_left = self._canvas_scene_top_left()
        current_center = self.canvas.mapToScene(self.canvas.viewport().rect().center())
        self.canvas.centerOn(current_center + top_left_position - current_top_left)

    def _apply_project_settings_changes(self) -> None:
        """変更されたエッジ種類を、ツールバーと現在のCanvas表示へ反映する。"""
        self._register_edge_type_styles()
        self.inspector.reload_edge_types()
        self._refresh_demo_graph()
        self._persist_project()

    def _register_edge_type_styles(self) -> None:
        """プロジェクト設定のエッジ種類を、Canvasの汎用スタイルキーとして登録する。"""
        for edge_type in self.project_settings.edge_types():
            StyleRegistry.set_edge_type_color(
                self._edge_type_style_key(edge_type),
                ColorPalette.color_hex(edge_type.color_token),
            )
        for node_kind in NodeKind:
            StyleRegistry.set_node_type_color(
                f"project-node:{node_kind.value}",
                ColorPalette.color_hex(self.project_settings.node_color(node_kind)),
            )

    def _connect_canvas_events(self) -> None:
        """Canvasの汎用イベントを、このデモ用の操作処理へ接続する。"""
        self.canvas.selection_changed.connect(self._show_selection)
        self.canvas.zoom_changed.connect(self._show_zoom)
        self.canvas.canvas_context_requested.connect(self._show_canvas_context_menu)
        self.canvas.node_context_requested.connect(self._show_node_context_menu)
        self.canvas.edge_context_requested.connect(self._show_edge_context_menu)
        self.canvas.node_move_committed.connect(self._show_node_move)
        self.canvas.edge_label_move_committed.connect(self._show_label_move)
        self.canvas.delete_requested.connect(self._show_delete_request)
        self.canvas.connection_requested.connect(self._create_demo_edge)
        self.canvas.node_creation_requested.connect(self._create_demo_node_from_connection)
        self.canvas.edge_reconnection_requested.connect(self._reconnect_demo_edge)
        self.canvas.edge_disconnect_requested.connect(self._disconnect_demo_edge)
        self.inspector.question_changed.connect(self._update_question_from_inspector)
        self.inspector.memo_changed.connect(self._update_memo_from_inspector)
        self.inspector.edge_type_changed.connect(self._update_edge_type_from_inspector)
        self.inspector.reference_changed.connect(self._update_reference_from_inspector)
        self.inspector.reference_catalog_requested.connect(self._show_reference_catalog_for_node)
        self.canvas.node_double_clicked.connect(self._show_node_inspector)
        self.canvas.edge_double_clicked.connect(self._show_edge_inspector)

    def _show_selection(self, node_ids: list[str], edge_ids: list[str]) -> None:
        """現在のノード・エッジ選択数をステータスバーへ表示する。"""
        # 単一選択だけをインスペクタへ渡し、複数選択は編集対象を持たない。
        if len(node_ids) == 1 and not edge_ids:
            node_id = node_ids[0]
            node = self._demo_graph_editor.node_view_model(node_id)
            if node.node_kind == NodeKind.QUESTION:
                self.inspector.show_question(node, self._demo_graph_editor.child_combination(node_id))
            elif node.node_kind == NodeKind.MEMO:
                self.inspector.show_memo(node)
            else:
                self.inspector.show_reference(node, self._reference_choices())
        elif len(edge_ids) == 1 and not node_ids:
            edge = self._demo_graph_editor.edge_view_model(edge_ids[0])
            source_kind = self._demo_graph_editor.node_view_model(edge.source_node_id).node_kind
            target_kind = self._demo_graph_editor.node_view_model(edge.target_node_id).node_kind
            allowed_edge_type_ids = tuple(
                edge_type.id
                for edge_type in self.project_settings.edge_types()
                if (source_kind, target_kind) in edge_type.allowed_endpoints
            )
            self.inspector.show_edge(edge, allowed_edge_type_ids)
        else:
            self.inspector.clear()
        if not node_ids and not edge_ids:
            self.statusBar().showMessage("選択なし")
            return
        self.statusBar().showMessage(f"選択中: ノード {len(node_ids)} 件、エッジ {len(edge_ids)} 件")

    def _show_zoom(self, zoom: float) -> None:
        """現在のCanvas倍率をステータスバーへ表示する。"""
        self.statusBar().showMessage(f"ズーム率: {zoom * 100:.0f}%")

    def _show_node_inspector(self, node_id: str) -> None:
        """指定ノードを選択し、閉じていればインスペクタを再表示する。"""
        self._show_inspector_without_moving_canvas()
        self.inspector_dock.raise_()
        self.canvas.select_node(node_id)
        self.statusBar().showMessage("ノードをインスペクタで表示しています。")

    def _show_edge_inspector(self, edge_id: str) -> None:
        """指定エッジを選択し、閉じていればインスペクタを再表示する。"""
        self._show_inspector_without_moving_canvas()
        self.inspector_dock.raise_()
        self.canvas.select_edge(edge_id)
        self.statusBar().showMessage("エッジをインスペクタで表示しています。")

    def _show_canvas_context_menu(self, scene_position: QPointF, global_position: QPoint) -> None:
        """背景のコンテキストメニューを表示する。"""
        menu = QMenu(self)
        add_node_action = menu.addAction("質問ノードを追加")
        add_node_action.triggered.connect(lambda: self._create_question_node(scene_position))
        add_memo_action = menu.addAction("メモノードを追加")
        add_memo_action.triggered.connect(lambda: self._create_memo_node(scene_position))
        add_reference_action = menu.addAction("文献ノードを追加")
        add_reference_action.triggered.connect(lambda: self._create_reference_node(scene_position))
        menu.addSeparator()
        menu.addAction(self.fit_all_action)
        menu.exec(global_position)
        self.statusBar().showMessage(f"空白キャンバスを右クリック: ({scene_position.x():.0f}, {scene_position.y():.0f})")

    def _show_node_context_menu(self, node_id: str, scene_position: QPointF, global_position: QPoint) -> None:
        """指定ノードの操作メニューを表示する。"""
        del scene_position
        menu = QMenu(self)
        delete_action = menu.addAction("ノードを削除")
        delete_action.triggered.connect(lambda: self._request_node_deletion(node_id))
        edit_action = menu.addAction("ノードを編集（次フェーズ）")
        edit_action.setEnabled(False)
        center_action = menu.addAction("ノードを中央に表示")
        center_action.triggered.connect(lambda: self.canvas.center_on_node(node_id))
        menu.exec(global_position)

    def _show_edge_context_menu(self, edge_id: str, scene_position: QPointF, global_position: QPoint) -> None:
        """指定エッジの操作メニューを表示する。"""
        del scene_position
        menu = QMenu(self)
        insert_action = menu.addAction("このエッジにノードを追加")
        insert_action.triggered.connect(lambda: self._insert_node_on_edge(edge_id))
        edit_action = menu.addAction("エッジを編集（次フェーズ）")
        edit_action.setEnabled(False)
        menu.exec(global_position)
        self.statusBar().showMessage("エッジのコンテキストメニューを表示しています。")

    def _show_node_move(self, node_id: str, old_position: QPointF, new_position: QPointF) -> None:
        """確定したノード位置を外部デモ状態へ反映し、結果を表示する。"""
        self._demo_graph_editor.update_node_position(node_id, new_position.x(), new_position.y())
        self.canvas.update_node(self._demo_graph_editor.node_view_model(node_id))
        self._persist_project()
        self.statusBar().showMessage(
            f"ノードを移動: ({old_position.x():.0f}, {old_position.y():.0f}) → ({new_position.x():.0f}, {new_position.y():.0f})"
        )

    def _show_label_move(self, edge_id: str, old_offset: QPointF, new_offset: QPointF) -> None:
        """確定したラベル位置を外部デモ状態へ反映し、結果を表示する。"""
        self._demo_graph_editor.update_edge_label_offset(edge_id, new_offset.x(), new_offset.y())
        self._persist_project()
        self.statusBar().showMessage(
            f"エッジラベルを移動: ({old_offset.x():.0f}, {old_offset.y():.0f}) → ({new_offset.x():.0f}, {new_offset.y():.0f})"
        )

    def _show_delete_request(self, node_ids: list[str], edge_ids: list[str]) -> None:
        """選択対象を確認なしで外部デモ状態から削除する。"""
        if len(node_ids) == 1 and not edge_ids:
            self._request_node_deletion(node_ids[0])
            return
        # 複数選択は意図しない再接続を避け、接続を再構成せず削除する。
        removed_edge_count = self._demo_graph_editor.remove_edges(edge_ids)
        for node_id in node_ids:
            result = self._demo_graph_editor.remove_node(node_id, reconnect=False)
            removed_edge_count += result.removed_edge_count
        self._refresh_demo_graph()
        self.statusBar().showMessage(f"ノード {len(node_ids)} 件、エッジ {removed_edge_count} 件を削除しました。")

    def _request_node_deletion(self, node_id: str) -> None:
        """安全に自動再接続できる場合だけ接続を維持し、確認なしで単一ノードを削除する。"""
        plan = self._demo_graph_editor.deletion_plan(node_id)
        result = self._demo_graph_editor.remove_node(node_id, reconnect=plan.can_reconnect_automatically)
        self._refresh_demo_graph()
        self.statusBar().showMessage(
            f"ノードを削除しました。削除エッジ: {result.removed_edge_count} 件、再接続: {result.created_edge_count} 件"
        )

    def _insert_node_on_edge(self, edge_id: str) -> None:
        """指定エッジを分割してデモノードを追加し、その位置へ表示を寄せる。"""
        node_id = self._demo_graph_editor.insert_node_on_edge(edge_id)
        self._refresh_demo_graph()
        self.canvas.center_on_node(node_id)
        self.statusBar().showMessage("エッジを分割し、ノードを追加しました。")

    def _create_demo_edge(self, source_node_id: str, target_node_id: str) -> None:
        """Canvasの接続要求を受け、デモ用の既定エッジを外部状態へ追加する。"""
        if self._demo_graph_editor.would_create_directed_cycle(source_node_id, target_node_id):
            self.statusBar().showMessage("主構造の親子関係に閉路ができるため、この接続は追加できません。")
            return
        edge_type = self._selected_edge_type(source_node_id, target_node_id)
        if edge_type is None:
            self.statusBar().showMessage("このノード種類の組合せに許可された関係はありません。")
            return
        edge_id = self._demo_graph_editor.add_edge(
            source_node_id,
            target_node_id,
            edge_type.label,
            self._edge_type_style_key(edge_type),
        )
        if edge_id is None:
            self.statusBar().showMessage("同一方向の接続がすでにあるため、追加しませんでした。")
            return
        self.canvas.update_edge(self._demo_graph_editor.edge_view_model(edge_id))
        self.canvas.select_edge(edge_id)
        self._persist_project()
        self.statusBar().showMessage("新しいエッジを追加しました。")

    def _create_demo_node_from_connection(self, source_node_id: str, scene_position: QPointF) -> None:
        """新規接続を背景で離した場合に、外部デモ状態へノードとエッジを追加する。"""
        edge_type = self._selected_edge_type(source_node_id, NodeKind.QUESTION)
        if edge_type is None:
            self.statusBar().showMessage("このノード種類から新しい問いへ作れる関係はありません。")
            return
        node_id = self._demo_graph_editor.create_node_connected_from(
            source_node_id,
            scene_position.x(),
            scene_position.y(),
            edge_type.label,
            self._edge_type_style_key(edge_type),
        )
        if node_id is None:
            self.statusBar().showMessage("新しいノードを追加できませんでした。")
            return
        self._refresh_demo_graph()
        self.canvas.select_node(node_id)
        self.statusBar().showMessage("ノードと新しい接続を追加しました。")

    def _create_question_node(self, scene_position: QPointF) -> None:
        """背景メニューの指定位置へ、接続を持たない質問ノードを追加する。"""
        node_id = self._demo_graph_editor.create_question_node_at(scene_position.x(), scene_position.y())
        self.canvas.update_node(self._demo_graph_editor.node_view_model(node_id))
        self.canvas.select_node(node_id)
        self._persist_project()
        self.statusBar().showMessage("質問ノードを追加しました。")

    def _create_memo_node(self, scene_position: QPointF) -> None:
        """背景メニューの指定位置へ、接続を持たないメモノードを追加する。"""
        node_id = self._demo_graph_editor.create_memo_node_at(scene_position.x(), scene_position.y())
        self.canvas.update_node(self._demo_graph_editor.node_view_model(node_id))
        self.canvas.select_node(node_id)
        self._persist_project()
        self.statusBar().showMessage("メモノードを追加しました。")

    def _create_reference_node(self, scene_position: QPointF) -> None:
        """背景メニューの指定位置へ、参照先が未選択の文献ノードを追加する。"""
        node_id = self._demo_graph_editor.create_reference_node_at(scene_position.x(), scene_position.y())
        self.canvas.update_node(self._demo_graph_editor.node_view_model(node_id))
        self.canvas.select_node(node_id)
        self._persist_project()
        self.statusBar().showMessage("文献ノードを追加しました。")

    def _disconnect_demo_edge(self, edge_id: str) -> None:
        """Canvasからの切断要求を受け、外部デモ状態のエッジを削除する。"""
        if self._demo_graph_editor.remove_edges([edge_id]) == 0:
            return
        self.canvas.remove_edge(edge_id)
        self._persist_project()
        self.statusBar().showMessage("エッジを切断しました。")

    def _reconnect_demo_edge(self, edge_id: str, source_node_id: str, target_node_id: str) -> None:
        """既存エッジの端を別ノードへドロップした結果を、外部デモ状態へ反映する。"""
        if not self._demo_graph_editor.reconnect_edge(edge_id, source_node_id, target_node_id):
            self.statusBar().showMessage("重複または閉路になるため、エッジの付け替えを取り消しました。")
            return
        self.canvas.update_edge(self._demo_graph_editor.edge_view_model(edge_id))
        self.canvas.select_edge(edge_id)
        self._persist_project()
        self.statusBar().showMessage("エッジを付け替えました。")

    def _refresh_demo_graph(self) -> None:
        """外部デモ状態から再構築したViewModelをCanvasへ反映する。"""
        self.canvas.set_graph(self._demo_graph_editor.graph())
        self._persist_project()

    def _update_question_from_inspector(
        self,
        node_id: str,
        title: str,
        body: str,
        combination: ChildCombination,
    ) -> None:
        """インスペクタの質問編集を外部状態とCanvasへ即時反映する。"""
        if not title.strip():
            self.statusBar().showMessage("質問のタイトルは空欄にできません。")
            return
        self._demo_graph_editor.update_question_node(node_id, title, body, combination)
        self.canvas.update_node(self._demo_graph_editor.node_view_model(node_id))
        self._persist_project()

    def _update_edge_type_from_inspector(self, edge_id: str, edge_type_id: str | None) -> None:
        """インスペクタの種類選択を、エッジのラベルと色へ即時反映する。"""
        edge = self._demo_graph_editor.edge_view_model(edge_id)
        edge_type = self._selected_edge_type(edge.source_node_id, edge.target_node_id)
        if edge_type is None or edge_type.id != edge_type_id:
            self.statusBar().showMessage("このノード種類の組合せには、その関係を設定できません。")
            return
        self._demo_graph_editor.update_edge_type(edge_id, edge_type.label, self._edge_type_style_key(edge_type))
        self.canvas.update_edge(self._demo_graph_editor.edge_view_model(edge_id))
        self._persist_project()

    def _update_memo_from_inspector(self, node_id: str, title: str, body: str) -> None:
        """インスペクタのメモ編集を外部状態とCanvasへ即時反映する。"""
        if not title.strip():
            self.statusBar().showMessage("メモのタイトルは空欄にできません。")
            return
        self._demo_graph_editor.update_memo_node(node_id, title, body)
        self.canvas.update_node(self._demo_graph_editor.node_view_model(node_id))
        self._persist_project()

    def _update_reference_from_inspector(self, node_id: str, reference_link: ReferenceLink | None) -> None:
        """インスペクタで選んだ文献をノードへ関連付け、表示内容をカタログから同期する。"""
        record = self._reference_for_link(reference_link)
        if record is None:
            self._demo_graph_editor.update_reference_node(node_id, None, "文献を選択してください", None)
        else:
            self._demo_graph_editor.update_reference_node(node_id, reference_link, record.title, self._reference_secondary_text(record))
        self.canvas.update_node(self._demo_graph_editor.node_view_model(node_id))
        self._persist_project()

    def _show_reference_catalog_for_node(self, node_id: str) -> None:
        """文献ノードが現在参照する文献を選択した状態で管理ダイアログを開く。"""
        self._show_reference_catalog(self._demo_graph_editor.node_view_model(node_id).reference_link)

    def _sync_reference_nodes_from_catalog(self) -> None:
        """文献マスタの変更を、関連付け済み文献ノードの表示へ反映する。"""
        for node in self._demo_graph_editor.graph().nodes:
            if node.node_kind != NodeKind.REFERENCE or node.reference_link is None:
                continue
            record = self._reference_for_link(node.reference_link)
            if record is None:
                self._demo_graph_editor.update_reference_node(node.id, None, "文献を選択してください", None)
            else:
                self._demo_graph_editor.update_reference_node(node.id, node.reference_link, record.title, self._reference_secondary_text(record))
            self.canvas.update_node(self._demo_graph_editor.node_view_model(node.id))
        self._persist_project()

    def _reference_choices(self) -> tuple[tuple[ReferenceLink, str], ...]:
        """種類別文献ドメインから、インスペクタ選択用の文献リンク一覧を作る。"""
        catalog = self._project_session.reference_catalog
        if catalog is None:
            return ()
        return (
            *((ReferenceLink(record_kind, record.id), record.title) for record_kind, records in ((ReferenceKind.PAPER, catalog.papers()), (ReferenceKind.BOOK, catalog.books()), (ReferenceKind.WEBSITE, catalog.websites())) for record in records),
        )

    def _reference_for_link(self, link: ReferenceLink | None) -> Paper | Book | Website | None:
        """文献リンクから、該当する種類別文献ドメインを取得する。"""
        catalog = self._project_session.reference_catalog
        return None if catalog is None or link is None else catalog.find(link)

    def _reference_secondary_text(self, record: Paper | Book | Website) -> str | None:
        """種類別文献のタイトル以外の情報を、ノードの補足テキストへ整形する。"""
        if isinstance(record, Paper):
            parts = ["Paper", record.authors, record.year, record.doi, record.url, record.notes]
        elif isinstance(record, Book):
            parts = ["Book", record.authors, record.year, record.isbn, record.publisher, record.notes]
        else:
            parts = ["Website", record.site_name, record.published_at, record.accessed_at, record.url, record.notes]
        return " / ".join(part for part in parts if part) or None

    def _persist_project(self) -> None:
        """現在のプロジェクトセッションへ、編集内容の保存を依頼する。"""
        self._project_session.save()

    def _selected_edge_type(self, source_node_id: str, target_node_id: str | NodeKind) -> EdgeType | None:
        """始点・終点のノード種別に許可された先頭の関係種類を返す。"""
        source_kind = self._demo_graph_editor.node_view_model(source_node_id).node_kind
        target_kind = target_node_id if isinstance(target_node_id, NodeKind) else self._demo_graph_editor.node_view_model(target_node_id).node_kind
        return self.project_settings.default_edge_type(source_kind, target_kind)

    def _edge_type_style_key(self, edge_type: EdgeType) -> str:
        """プロジェクト設定のエッジ種類IDを、Canvas用の汎用スタイルキーへ変換する。"""
        return f"global-edge-type:{edge_type.id}"

    def _edge_type_icon(self, edge_type: EdgeType) -> QIcon:
        """エッジ種類の色トークンを示す小さな四角形アイコンを作成する。"""
        pixmap = QPixmap(14, 14)
        pixmap.fill(QColor(ColorPalette.color_hex(edge_type.color_token)))
        return QIcon(pixmap)

    def changeEvent(self, event: QEvent) -> None:
        """ウィンドウがアクティブになった時、Navigatorへプロジェクトを通知する。"""
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            self.project_activated.emit(self._project_session.project_name)

    def closeEvent(self, event: QCloseEvent) -> None:
        """閉じる直前に保存し、Navigatorへセッション終了を通知する。"""
        self._project_session.save()
        event.accept()
        self.project_closed.emit(self._project_session.project_name)
