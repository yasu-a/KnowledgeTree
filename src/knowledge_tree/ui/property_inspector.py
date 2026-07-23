"""選択中の質問ノードまたは関係エッジを編集する右側インスペクタ。"""

from PyQt6.QtCore import QSignalBlocker, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QComboBox, QFormLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from knowledge_tree.color_palette import ColorPalette, ColorToken
from knowledge_tree.demo_graph_editor import ChildCombination
from knowledge_tree.project_settings import ProjectSettings
from knowledge_tree.reference_catalog import ReferenceLink
from knowledge_tree.viewmodels.graph_viewmodels import GraphEdgeViewModel, GraphNodeViewModel


class PropertyInspector(QWidget):
    """Canvasの選択対象に応じて、質問またはエッジの編集フォームを表示する。"""

    question_changed = pyqtSignal(str, str, str, object)
    memo_changed = pyqtSignal(str, str, str)
    edge_type_changed = pyqtSignal(str, object)
    reference_changed = pyqtSignal(str, object)
    reference_catalog_requested = pyqtSignal(str)

    def __init__(self, settings: ProjectSettings, parent: QWidget | None = None) -> None:
        """選択なし・質問・エッジ用のフォームを持つインスペクタを初期化する。"""
        super().__init__(parent)
        self._settings = settings
        self._node_id: str | None = None
        self._edge_id: str | None = None
        self._is_loading = False
        self._allowed_edge_type_ids: tuple[str, ...] = ()
        self._stack = QStackedWidget(self)
        self._empty_page = self._create_empty_page()
        self._node_page = self._create_node_page()
        self._memo_page = self._create_memo_page()
        self._reference_page = self._create_reference_page()
        self._edge_page = self._create_edge_page()
        self._stack.addWidget(self._empty_page)
        self._stack.addWidget(self._node_page)
        self._stack.addWidget(self._memo_page)
        self._stack.addWidget(self._reference_page)
        self._stack.addWidget(self._edge_page)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self._stack)
        self.clear()

    def clear(self) -> None:
        """選択対象を解除し、操作案内ページを表示する。"""
        self._node_id = None
        self._edge_id = None
        self._stack.setCurrentWidget(self._empty_page)

    def show_question(self, node: GraphNodeViewModel, combination: ChildCombination) -> None:
        """指定質問ノードの値をフォームへ表示する。"""
        self._node_id = node.id
        self._edge_id = None
        self._is_loading = True
        blockers = [QSignalBlocker(self.title_edit), QSignalBlocker(self.body_edit), QSignalBlocker(self.combination_combo)]
        self.title_edit.setText(node.text)
        self.body_edit.setPlainText(node.secondary_text or "")
        self.combination_combo.setCurrentIndex(self.combination_combo.findData(combination))
        del blockers
        self._is_loading = False
        self._stack.setCurrentWidget(self._node_page)

    def show_edge(self, edge: GraphEdgeViewModel, allowed_edge_type_ids: tuple[str, ...]) -> None:
        """指定エッジの種類をフォームへ表示する。"""
        self._node_id = None
        self._edge_id = edge.id
        self._allowed_edge_type_ids = allowed_edge_type_ids
        self._is_loading = True
        blocker = QSignalBlocker(self.edge_type_combo)
        self._populate_edge_type_combo()
        self.edge_type_combo.setCurrentIndex(self._edge_type_index_for(edge))
        del blocker
        self._is_loading = False
        self._stack.setCurrentWidget(self._edge_page)

    def reload_edge_types(self) -> None:
        """プロジェクト設定の変更後に、エッジ種類コンボボックスの候補を更新する。"""
        blocker = QSignalBlocker(self.edge_type_combo)
        self._populate_edge_type_combo()
        del blocker

    def show_memo(self, node: GraphNodeViewModel) -> None:
        """指定メモノードのタイトルと本文をフォームへ表示する。"""
        self._node_id = node.id
        self._edge_id = None
        self._is_loading = True
        blockers = [QSignalBlocker(self.memo_title_edit), QSignalBlocker(self.memo_body_edit)]
        self.memo_title_edit.setText(node.text)
        self.memo_body_edit.setPlainText(node.secondary_text or "")
        del blockers
        self._is_loading = False
        self._stack.setCurrentWidget(self._memo_page)

    def show_reference(self, node: GraphNodeViewModel, choices: tuple[tuple[ReferenceLink, str], ...]) -> None:
        """指定文献ノードの参照先を選択できるフォームへ表示する。"""
        self._node_id = node.id
        self._edge_id = None
        self._is_loading = True
        blocker = QSignalBlocker(self.reference_combo)
        self.reference_combo.clear()
        self.reference_combo.addItem("（未選択）", None)
        for link, title in choices:
            self.reference_combo.addItem(f"[{link.kind.value.title()}] {title}", link)
        selected_index = next(
            (
                index
                for index in range(self.reference_combo.count())
                if self.reference_combo.itemData(index) == node.reference_link
            ),
            0,
        )
        self.reference_combo.setCurrentIndex(selected_index)
        del blocker
        self._is_loading = False
        self._stack.setCurrentWidget(self._reference_page)

    def _create_empty_page(self) -> QWidget:
        """選択なしのときに表示する操作案内ページを作る。"""
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.addWidget(QLabel("ノードまたはエッジを選択すると、ここで編集できます。", page))
        layout.addStretch()
        return page

    def _create_node_page(self) -> QWidget:
        """質問ノードのタイトル・本文・AND/ORを編集するページを作る。"""
        page = QWidget(self)
        layout = QFormLayout(page)
        self.title_edit = QLineEdit(page)
        self.title_edit.setPlaceholderText("質問のタイトル")
        self.body_edit = QPlainTextEdit(page)
        self.body_edit.setPlaceholderText("補足・本文")
        self.combination_combo = QComboBox(page)
        self.combination_combo.addItem("なし", ChildCombination.NONE)
        self.combination_combo.addItem("すべて満たす (AND)", ChildCombination.ALL)
        self.combination_combo.addItem("いずれかでよい (OR)", ChildCombination.ANY)
        layout.addRow("タイトル", self.title_edit)
        layout.addRow("本文", self.body_edit)
        layout.addRow("子の条件", self.combination_combo)
        self.title_edit.editingFinished.connect(self._emit_question_changed)
        self.body_edit.textChanged.connect(self._emit_question_changed)
        self.combination_combo.currentIndexChanged.connect(self._emit_question_changed)
        return page

    def _create_edge_page(self) -> QWidget:
        """関係エッジの種類を選択するページを作る。"""
        page = QWidget(self)
        layout = QFormLayout(page)
        self.edge_type_combo = QComboBox(page)
        self._populate_edge_type_combo()
        layout.addRow("関係", self.edge_type_combo)
        self.edge_type_combo.currentIndexChanged.connect(self._emit_edge_type_changed)
        return page

    def _create_memo_page(self) -> QWidget:
        """メモノードのタイトルと本文を編集するページを作る。"""
        page = QWidget(self)
        layout = QFormLayout(page)
        self.memo_title_edit = QLineEdit(page)
        self.memo_body_edit = QPlainTextEdit(page)
        layout.addRow("タイトル", self.memo_title_edit)
        layout.addRow("本文", self.memo_body_edit)
        self.memo_title_edit.editingFinished.connect(self._emit_memo_changed)
        self.memo_body_edit.textChanged.connect(self._emit_memo_changed)
        return page

    def _create_reference_page(self) -> QWidget:
        """文献ノードが参照する文献マスタを選択するページを作る。"""
        page = QWidget(self)
        layout = QFormLayout(page)
        self.reference_combo = QComboBox(page)
        self.reference_catalog_button = QPushButton("文献を管理…", page)
        layout.addRow("文献", self.reference_combo)
        layout.addRow("", self.reference_catalog_button)
        self.reference_combo.currentIndexChanged.connect(self._emit_reference_changed)
        self.reference_catalog_button.clicked.connect(self._emit_reference_catalog_requested)
        return page

    def _emit_question_changed(self) -> None:
        """フォーム入力から、現在の質問ノードの編集要求を送る。"""
        if self._is_loading or self._node_id is None:
            return
        combination = self.combination_combo.currentData()
        if isinstance(combination, ChildCombination):
            self.question_changed.emit(self._node_id, self.title_edit.text(), self.body_edit.toPlainText(), combination)

    def _emit_edge_type_changed(self) -> None:
        """フォーム選択から、現在のエッジ種類変更要求を送る。"""
        if not self._is_loading and self._edge_id is not None:
            self.edge_type_changed.emit(self._edge_id, self.edge_type_combo.currentData())

    def _emit_memo_changed(self) -> None:
        """メモフォーム入力から、現在のメモノードの編集要求を送る。"""
        if not self._is_loading and self._node_id is not None:
            self.memo_changed.emit(self._node_id, self.memo_title_edit.text(), self.memo_body_edit.toPlainText())

    def _emit_reference_changed(self) -> None:
        """選択した文献IDを、現在の文献ノードへ反映する要求として送る。"""
        if not self._is_loading and self._node_id is not None:
            self.reference_changed.emit(self._node_id, self.reference_combo.currentData())

    def _emit_reference_catalog_requested(self) -> None:
        """現在の文献ノードを起点に、文献マスタ管理画面を開く要求を送る。"""
        if self._node_id is not None:
            self.reference_catalog_requested.emit(self._node_id)

    def _populate_edge_type_combo(self) -> None:
        """現在の両端ノードに許可された関係種類を色見本付きで追加する。"""
        self.edge_type_combo.clear()
        for edge_type in self._settings.edge_types():
            if self._allowed_edge_type_ids and edge_type.id not in self._allowed_edge_type_ids:
                continue
            self.edge_type_combo.addItem(
                self._color_icon(edge_type.color_token),
                edge_type.label,
                edge_type.id,
            )

    def _edge_type_index_for(self, edge: GraphEdgeViewModel) -> int:
        """エッジのスタイルキーに一致するエッジ種類のコンボボックス位置を返す。"""
        prefix = "global-edge-type:"
        edge_type_id = edge.style_key.removeprefix(prefix) if edge.style_key.startswith(prefix) else None
        index = self.edge_type_combo.findData(edge_type_id)
        return index if index >= 0 else 0

    def _color_icon(self, color_token: ColorToken) -> QIcon:
        """エッジ種類の色トークンを示す小さな四角形アイコンを作る。"""
        pixmap = QPixmap(14, 14)
        pixmap.fill(QColor(ColorPalette.color_hex(color_token)))
        return QIcon(pixmap)
