"""第1フェーズの MainWindow。メニューはCanvasの外で構築する。"""

from PyQt6.QtCore import QPoint, QPointF, QTimer, Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import QMainWindow, QMenu, QMessageBox, QStatusBar, QToolBar

from knowledge_tree.demo_data import build_demo_graph
from knowledge_tree.demo_graph_editor import DemoGraphEditor
from knowledge_tree.graph.graph_canvas_widget import GraphCanvasWidget


class MainWindow(QMainWindow):
    """サンプルデータの投入と、Canvasイベントの受け口を担当する。"""

    def __init__(self) -> None:
        """デモ用のCanvas、メニュー、外部編集状態を初期化する。"""
        super().__init__()
        self.setWindowTitle("KnowledgeTree - グラフ操作確認")
        self.resize(1200, 760)
        self.canvas = GraphCanvasWidget(self)
        self.setCentralWidget(self.canvas)
        self._create_actions()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_status_bar()
        self._connect_canvas_events()
        self._demo_graph_editor = DemoGraphEditor(build_demo_graph())
        self.canvas.set_graph(self._demo_graph_editor.graph())
        QTimer.singleShot(0, self.canvas.fit_all)
        self.statusBar().showMessage("背景をドラッグして移動できます。ノード辺で新規接続、エッジ端で付け替え・削除できます。")

    def _create_actions(self) -> None:
        """メニューとツールバーで共用するアクションを作成する。"""
        self.fit_all_action = QAction("全体を表示", self)
        self.fit_all_action.setShortcut("F")
        self.fit_all_action.triggered.connect(self.canvas.fit_all)

        self.exit_action = QAction("終了", self)
        self.exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self.exit_action.triggered.connect(self.close)

    def _create_menu_bar(self) -> None:
        """ファイル・表示メニューを構築する。"""
        file_menu = self.menuBar().addMenu("ファイル")
        file_menu.addAction(self.exit_action)
        view_menu = self.menuBar().addMenu("表示")
        view_menu.addAction(self.fit_all_action)

    def _create_toolbar(self) -> None:
        """表示操作用のツールバーを構築する。"""
        toolbar = QToolBar("表示", self)
        toolbar.setMovable(False)
        toolbar.addAction(self.fit_all_action)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _create_status_bar(self) -> None:
        """操作結果を表示するステータスバーを設定する。"""
        self.setStatusBar(QStatusBar(self))

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
        self.canvas.node_double_clicked.connect(lambda node_id: self.statusBar().showMessage(f"ノード {node_id} がダブルクリックされました。"))
        self.canvas.edge_double_clicked.connect(lambda edge_id: self.statusBar().showMessage(f"エッジ {edge_id} がダブルクリックされました。"))

    def _show_selection(self, node_ids: list[str], edge_ids: list[str]) -> None:
        """現在のノード・エッジ選択数をステータスバーへ表示する。"""
        if not node_ids and not edge_ids:
            self.statusBar().showMessage("選択なし")
            return
        self.statusBar().showMessage(f"選択中: ノード {len(node_ids)} 件、エッジ {len(edge_ids)} 件")

    def _show_zoom(self, zoom: float) -> None:
        """現在のCanvas倍率をステータスバーへ表示する。"""
        self.statusBar().showMessage(f"ズーム率: {zoom * 100:.0f}%")

    def _show_canvas_context_menu(self, scene_position: QPointF, global_position: QPoint) -> None:
        """背景のコンテキストメニューを表示する。"""
        menu = QMenu(self)
        add_node_action = menu.addAction("ノードを追加（次フェーズ）")
        add_node_action.setEnabled(False)
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
        self.statusBar().showMessage(f"エッジ {edge_id} のコンテキストメニュー要求")

    def _show_node_move(self, node_id: str, old_position: QPointF, new_position: QPointF) -> None:
        """確定したノード位置を外部デモ状態へ反映し、結果を表示する。"""
        self._demo_graph_editor.update_node_position(node_id, new_position.x(), new_position.y())
        self.statusBar().showMessage(
            f"ノード {node_id} を移動: ({old_position.x():.0f}, {old_position.y():.0f}) → ({new_position.x():.0f}, {new_position.y():.0f})"
        )

    def _show_label_move(self, edge_id: str, old_offset: QPointF, new_offset: QPointF) -> None:
        """確定したラベル位置を外部デモ状態へ反映し、結果を表示する。"""
        self._demo_graph_editor.update_edge_label_offset(edge_id, new_offset.x(), new_offset.y())
        self.statusBar().showMessage(
            f"エッジラベル {edge_id} を移動: ({old_offset.x():.0f}, {old_offset.y():.0f}) → ({new_offset.x():.0f}, {new_offset.y():.0f})"
        )

    def _show_delete_request(self, node_ids: list[str], edge_ids: list[str]) -> None:
        """選択対象の削除確認を表示し、外部デモ状態から削除する。"""
        if len(node_ids) == 1 and not edge_ids:
            self._request_node_deletion(node_ids[0])
            return
        message = f"ノード: {len(node_ids)} 件\nエッジ: {len(edge_ids)} 件を削除します。"
        if node_ids:
            message += "\nノードに接続するエッジも削除されます。"
        # 複数選択は再接続せず、確認後にまとめて削除する。
        answer = QMessageBox.question(
            self,
            "削除の確認",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        removed_edge_count = self._demo_graph_editor.remove_edges(edge_ids)
        for node_id in node_ids:
            result = self._demo_graph_editor.remove_node(node_id, reconnect=False)
            removed_edge_count += result.removed_edge_count
        self._refresh_demo_graph()
        self.statusBar().showMessage(f"ノード {len(node_ids)} 件、エッジ {removed_edge_count} 件を削除しました。")

    def _request_node_deletion(self, node_id: str) -> None:
        """親子数に応じた再接続方針を確認し、単一ノードを削除する。"""
        plan = self._demo_graph_editor.deletion_plan(node_id)
        reconnect = False
        # 多対多だけは全組合せでの再接続可否をユーザーに選んでもらう。
        if plan.requires_choice:
            answer = self._ask_many_to_many_deletion(node_id, plan.parent_node_ids, plan.child_node_ids)
            if answer is None:
                return
            reconnect = answer
        else:
            message = self._single_node_deletion_message(node_id, plan.parent_node_ids, plan.child_node_ids)
            answer = QMessageBox.question(
                self,
                "ノード削除の確認",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            reconnect = plan.can_reconnect_automatically
        # 決定した方針で外部状態を更新し、Canvasへ再投入する。
        result = self._demo_graph_editor.remove_node(node_id, reconnect=reconnect)
        self._refresh_demo_graph()
        self.statusBar().showMessage(
            f"ノードを削除しました。削除エッジ: {result.removed_edge_count} 件、再接続: {result.created_edge_count} 件"
        )

    def _insert_node_on_edge(self, edge_id: str) -> None:
        """指定エッジを分割してデモノードを追加し、その位置へ表示を寄せる。"""
        node_id = self._demo_graph_editor.insert_node_on_edge(edge_id)
        self._refresh_demo_graph()
        self.canvas.center_on_node(node_id)
        self.statusBar().showMessage(f"エッジ {edge_id} を分割し、ノードを追加しました。")

    def _create_demo_edge(self, source_node_id: str, target_node_id: str) -> None:
        """Canvasの接続要求を受け、デモ用の既定エッジを外部状態へ追加する。"""
        if self._demo_graph_editor.would_create_directed_cycle(source_node_id, target_node_id):
            self.statusBar().showMessage("主構造の親子関係に閉路ができるため、この接続は追加できません。")
            return
        edge_id = self._demo_graph_editor.add_edge(source_node_id, target_node_id)
        if edge_id is None:
            self.statusBar().showMessage("同一方向の接続がすでにあるため、追加しませんでした。")
            return
        self._refresh_demo_graph()
        self.statusBar().showMessage(f"新しいエッジ {edge_id} を追加しました。")

    def _create_demo_node_from_connection(self, source_node_id: str, scene_position: QPointF) -> None:
        """新規接続を背景で離した場合に、外部デモ状態へノードとエッジを追加する。"""
        node_id = self._demo_graph_editor.create_node_connected_from(
            source_node_id,
            scene_position.x(),
            scene_position.y(),
        )
        if node_id is None:
            self.statusBar().showMessage("新しいノードを追加できませんでした。")
            return
        self._refresh_demo_graph()
        self.statusBar().showMessage(f"ノード {node_id} と新しい接続を追加しました。")

    def _disconnect_demo_edge(self, edge_id: str) -> None:
        """Canvasからの切断要求を受け、外部デモ状態のエッジを削除する。"""
        if self._demo_graph_editor.remove_edges([edge_id]) == 0:
            return
        self._refresh_demo_graph()
        self.statusBar().showMessage(f"エッジ {edge_id} を切断しました。")

    def _reconnect_demo_edge(self, edge_id: str, source_node_id: str, target_node_id: str) -> None:
        """既存エッジの端を別ノードへドロップした結果を、外部デモ状態へ反映する。"""
        if not self._demo_graph_editor.reconnect_edge(edge_id, source_node_id, target_node_id):
            self.statusBar().showMessage("重複または閉路になるため、エッジの付け替えを取り消しました。")
            return
        self._refresh_demo_graph()
        self.statusBar().showMessage(f"エッジ {edge_id} を付け替えました。")

    def _single_node_deletion_message(
        self,
        node_id: str,
        parent_node_ids: tuple[str, ...],
        child_node_ids: tuple[str, ...],
    ) -> str:
        """単一ノード削除時に表示する、再接続方針の説明文を作る。"""
        if parent_node_ids and child_node_ids and (len(parent_node_ids) == 1 or len(child_node_ids) == 1):
            return (
                f"ノード {node_id} を削除します。\n\n"
                f"親: {', '.join(parent_node_ids)}\n"
                f"子: {', '.join(child_node_ids)}\n\n"
                "子ノードを親ノードへ再接続します。"
            )
        return f"ノード {node_id} と、その接続エッジを削除します。"

    def _ask_many_to_many_deletion(
        self,
        node_id: str,
        parent_node_ids: tuple[str, ...],
        child_node_ids: tuple[str, ...],
    ) -> bool | None:
        """多対多ノード削除時に、再接続するかを確認して結果を返す。"""
        dialog = QMessageBox(self)
        dialog.setWindowTitle("ノード削除の確認")
        dialog.setText(
            f"ノード {node_id} には複数の親と子があります。\n\n"
            f"親: {', '.join(parent_node_ids)}\n"
            f"子: {', '.join(child_node_ids)}\n\n"
            "再接続すると、親と子の全組合せでエッジを作成します。"
        )
        reconnect_button = dialog.addButton("全組合せで再接続して削除", QMessageBox.ButtonRole.AcceptRole)
        disconnect_button = dialog.addButton("接続を解除して削除", QMessageBox.ButtonRole.DestructiveRole)
        dialog.addButton(QMessageBox.StandardButton.Cancel)
        dialog.exec()
        if dialog.clickedButton() == reconnect_button:
            return True
        if dialog.clickedButton() == disconnect_button:
            return False
        return None

    def _refresh_demo_graph(self) -> None:
        """外部デモ状態から再構築したViewModelをCanvasへ反映する。"""
        self.canvas.set_graph(self._demo_graph_editor.graph())
