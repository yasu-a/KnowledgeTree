"""エッジ種類コレクションを編集する専用Widget。"""

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QToolButton, QVBoxLayout, QWidget

from knowledge_tree.color_palette import ColorPalette, ColorToken
from knowledge_tree.project_settings import EdgeType, ProjectSettings


class EdgeTypeEditorWidget(QWidget):
    """エッジ種類の追加・削除と、ラベル・自然配色の変更を提供する。"""

    edge_types_changed = pyqtSignal()

    def __init__(self, settings: ProjectSettings, parent: QWidget | None = None) -> None:
        """指定設定を編集するリストと詳細フォームを初期化する。"""
        super().__init__(parent)
        self._settings = settings
        self._is_loading = False
        self.list_widget = QListWidget(self)
        self.add_button = QToolButton(self)
        self.add_button.setText("+")
        self.remove_button = QToolButton(self)
        self.remove_button.setText("−")
        self.label_edit = QLineEdit(self)
        self.color_combo = QComboBox(self)
        self._populate_palette()
        self._build_layout()
        self._connect_events()
        self.reload()

    def reload(self) -> None:
        """設定コレクションからリストを再構築し、先頭項目を選択する。"""
        self._is_loading = True
        blocker = QSignalBlocker(self.list_widget)
        self.list_widget.clear()
        for edge_type in self._settings.edge_types():
            item = QListWidgetItem(self._edge_type_icon(edge_type.color_token), edge_type.label)
            item.setData(Qt.ItemDataRole.UserRole, edge_type.id)
            self.list_widget.addItem(item)
        del blocker
        self._is_loading = False
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)
        else:
            self._show_selected_type(None)

    def _populate_palette(self) -> None:
        """RGB入力を使わず、定義済み自然配色だけをコンボボックスへ追加する。"""
        for color_token in ColorToken:
            self.color_combo.addItem(
                self._edge_type_icon(color_token),
                color_token.display_name,
                color_token,
            )

    def _build_layout(self) -> None:
        """リスト、追加削除ボタン、詳細フォームを縦に配置する。"""
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addStretch()
        form_layout = QFormLayout()
        form_layout.addRow("ラベル", self.label_edit)
        form_layout.addRow("色", self.color_combo)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("エッジの種類", self))
        layout.addWidget(self.list_widget)
        layout.addLayout(button_layout)
        layout.addLayout(form_layout)

    def _connect_events(self) -> None:
        """リスト選択、追加削除、詳細フォームの変更を設定更新へ接続する。"""
        self.list_widget.currentItemChanged.connect(lambda current, previous: self._show_selected_type(current))
        self.add_button.clicked.connect(self._add_edge_type)
        self.remove_button.clicked.connect(self._remove_selected_type)
        self.label_edit.editingFinished.connect(self._update_selected_type)
        self.color_combo.currentIndexChanged.connect(self._update_selected_type)

    def _show_selected_type(self, item: QListWidgetItem | None) -> None:
        """選択中のエッジ種類を詳細フォームへ表示する。"""
        edge_type = self._selected_edge_type(item)
        self._is_loading = True
        blockers = [QSignalBlocker(self.label_edit), QSignalBlocker(self.color_combo)]
        self.label_edit.setEnabled(edge_type is not None)
        self.color_combo.setEnabled(edge_type is not None)
        self.remove_button.setEnabled(edge_type is not None)
        if edge_type is not None:
            self.label_edit.setText(edge_type.label)
            self.color_combo.setCurrentIndex(self.color_combo.findData(edge_type.color_token))
        else:
            self.label_edit.clear()
        del blockers
        self._is_loading = False

    def _add_edge_type(self) -> None:
        """既定のエッジ種類を追加して、直後にその項目を選択する。"""
        edge_type = self._settings.add_edge_type()
        self.reload()
        for row in range(self.list_widget.count()):
            if self.list_widget.item(row).data(Qt.ItemDataRole.UserRole) == edge_type.id:
                self.list_widget.setCurrentRow(row)
                break
        self.edge_types_changed.emit()

    def _remove_selected_type(self) -> None:
        """選択中のエッジ種類を削除し、リスト表示を更新する。"""
        edge_type = self._selected_edge_type(self.list_widget.currentItem())
        if edge_type is None:
            return
        self._settings.remove_edge_type(edge_type.id)
        self.reload()
        self.edge_types_changed.emit()

    def _update_selected_type(self) -> None:
        """詳細フォームの値を選択中のエッジ種類へ反映する。"""
        if self._is_loading:
            return
        edge_type = self._selected_edge_type(self.list_widget.currentItem())
        if edge_type is None:
            return
        label = self.label_edit.text().strip() or "新しい関係"
        color_token = self.color_combo.currentData()
        if not isinstance(color_token, ColorToken):
            return
        self._settings.update_edge_type(edge_type.id, label, color_token)
        self.list_widget.currentItem().setText(label)
        self.list_widget.currentItem().setIcon(self._edge_type_icon(color_token))
        self.edge_types_changed.emit()

    def _selected_edge_type(self, item: QListWidgetItem | None) -> EdgeType | None:
        """リスト項目に対応する設定上のエッジ種類を返す。"""
        if item is None:
            return None
        edge_type_id = item.data(Qt.ItemDataRole.UserRole)
        return next((edge_type for edge_type in self._settings.edge_types() if edge_type.id == edge_type_id), None)

    def _edge_type_icon(self, color_token: ColorToken) -> QIcon:
        """指定色トークンを示す小さな四角形アイコンを作成する。"""
        pixmap = QPixmap(14, 14)
        pixmap.fill(QColor(ColorPalette.color_hex(color_token)))
        return QIcon(pixmap)
