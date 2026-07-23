"""プロジェクト内の文献マスタを表形式で編集するダイアログ。"""

from dataclasses import replace

from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtGui import QWheelEvent
from PyQt6.QtWidgets import QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel, QTabWidget, QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout, QWidget

from knowledge_tree.reference_catalog import Book, Paper, ReferenceCatalog, ReferenceKind, ReferenceLink, Website
from knowledge_tree.ui.save_cancel_dialog import SaveCancelDialog


class ShiftScrollableTableWidget(QTableWidget):
    """Shift+ホイールで横スクロールできるテーブル。"""

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Shift修飾時はホイール量を水平スクロールバーへ渡す。"""
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - event.angleDelta().y())
            event.accept()
            return
        super().wheelEvent(event)


class ReferenceCatalogDialog(SaveCancelDialog):
    """論文・書籍・WebサイトのCSV列を、種類別テーブルで編集する。"""

    catalog_changed = pyqtSignal()

    _columns_by_kind = {
        ReferenceKind.PAPER: (
            ("title", "title", 240, True), ("authors", "authors", 180, True),
            ("year", "year", 80, False), ("doi", "doi", 160, False), ("url", "url", 240, True), ("notes", "notes", 220, True),
        ),
        ReferenceKind.BOOK: (
            ("title", "title", 240, True), ("authors", "authors", 180, True),
            ("year", "year", 80, False), ("isbn", "isbn", 160, False), ("publisher", "publisher", 150, True), ("notes", "notes", 220, True),
        ),
        ReferenceKind.WEBSITE: (
            ("title", "title", 240, True), ("site_name", "site_name", 160, True),
            ("published_at", "published_at", 110, False), ("accessed_at", "accessed_at", 110, False), ("url", "url", 260, True), ("notes", "notes", 220, True),
        ),
    }

    def __init__(self, catalog: ReferenceCatalog, active_reference_link: ReferenceLink | None = None, parent: QWidget | None = None) -> None:
        """指定カタログの編集用コピーを、関連文献を選択した状態で初期化する。"""
        self._catalog = catalog
        self._papers = list(catalog.papers())
        self._books = list(catalog.books())
        self._websites = list(catalog.websites())
        self._original_records = (tuple(self._papers), tuple(self._books), tuple(self._websites))
        self._active_reference_link = active_reference_link
        self._is_loading = False
        self.tables: dict[ReferenceKind, QTableWidget] = {}
        super().__init__(self._is_dirty, parent)
        self.setWindowTitle("文献を管理")
        self.resize(1050, 600)
        self._build_layout()
        self._reload_tables()

    def _build_layout(self) -> None:
        """文献種別ごとの上部タブ、追加削除、Save/Cancelボタンを配置する。"""
        self.tab_widget = QTabWidget(self)
        for kind in ReferenceKind:
            table = ShiftScrollableTableWidget(self)
            columns = self._columns_by_kind[kind]
            table.setColumnCount(len(columns))
            table.setHorizontalHeaderLabels([header for header, _, _, _ in columns])
            table.setWordWrap(True)
            table.setAlternatingRowColors(True)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
            table.cellChanged.connect(lambda row, column, table_kind=kind: self._update_record_from_cell(table_kind, row, column))
            for column, (_, _, width, _) in enumerate(columns):
                table.setColumnWidth(column, width)
            self.tables[kind] = table
            self.tab_widget.addTab(table, kind.value.title())

        self.add_button = QToolButton(self)
        self.add_button.setText("+")
        self.add_button.setToolTip("現在の種別に文献を追加")
        self.remove_button = QToolButton(self)
        self.remove_button.setText("−")
        self.remove_button.setToolTip("選択中の文献を削除")
        self.add_button.clicked.connect(self._add_record)
        self.remove_button.clicked.connect(self._remove_selected_records)
        actions = QHBoxLayout()
        actions.addWidget(QLabel("文献", self))
        actions.addWidget(self.add_button)
        actions.addWidget(self.remove_button)
        actions.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.discard)
        layout = QVBoxLayout(self)
        layout.addLayout(actions)
        layout.addWidget(self.tab_widget)
        layout.addWidget(buttons)

    def _reload_tables(self) -> None:
        """編集用レコードを3種類のテーブルへ読み込み、関連文献があれば選択する。"""
        self._is_loading = True
        for kind, table in self.tables.items():
            blocker = QSignalBlocker(table)
            records = self._records_for_kind(kind)
            table.setRowCount(len(records))
            for row, record in enumerate(records):
                for column, (_, attribute, _, _) in enumerate(self._columns_by_kind[kind]):
                    item = QTableWidgetItem(str(getattr(record, attribute)))
                    item.setData(Qt.ItemDataRole.UserRole, record.id)
                    table.setItem(row, column, item)
                if ReferenceLink(kind, record.id) == self._active_reference_link:
                    self.tab_widget.setCurrentWidget(table)
                    table.selectRow(row)
            table.resizeRowsToContents()
            del blocker
        self._is_loading = False

    def _add_record(self) -> None:
        """現在のタブ種別で未保存の文献レコードを追加する。"""
        kind = self._current_kind()
        record = Paper(self._next_id(kind), "無題の文献") if kind == ReferenceKind.PAPER else Book(self._next_id(kind), "無題の文献") if kind == ReferenceKind.BOOK else Website(self._next_id(kind), "無題の文献")
        self._replace_records_for_kind(kind, (*self._records_for_kind(kind), record))
        self._active_reference_link = ReferenceLink(kind, record.id)
        self._reload_tables()
        table = self.tables[kind]
        table.setCurrentCell(table.rowCount() - 1, 1)
        table.editItem(table.item(table.rowCount() - 1, 1))

    def _remove_selected_records(self) -> None:
        """現在のタブで選択された行の文献を、編集用一覧から削除する。"""
        table = self.tables[self._current_kind()]
        record_ids = {table.item(index.row(), 0).data(Qt.ItemDataRole.UserRole) for index in table.selectionModel().selectedRows()}
        if not record_ids:
            return
        kind = self._current_kind()
        self._replace_records_for_kind(kind, tuple(record for record in self._records_for_kind(kind) if record.id not in record_ids))
        self._active_reference_link = None
        self._reload_tables()

    def _update_record_from_cell(self, kind: ReferenceKind, row: int, column: int) -> None:
        """セル編集を対応する編集用文献レコードの属性へ反映する。"""
        if self._is_loading:
            return
        table = self.tables[kind]
        id_item = table.item(row, 0)
        value_item = table.item(row, column)
        if id_item is None or value_item is None:
            return
        reference_id = id_item.data(Qt.ItemDataRole.UserRole)
        record = next((item for item in self._records_for_kind(kind) if item.id == reference_id), None)
        if record is None:
            return
        _, attribute, _, _ = self._columns_by_kind[kind][column]
        updated = replace(record, **{attribute: value_item.text()})
        self._replace_records_for_kind(kind, tuple(updated if item.id == record.id else item for item in self._records_for_kind(kind)))
        table.resizeRowToContents(row)

    def _save_and_accept(self) -> None:
        """編集用一覧を種類別CSVへ確定保存して、成功時だけダイアログを閉じる。"""
        changed = self._is_dirty()
        self._catalog.replace_papers(tuple(self._papers))
        self._catalog.replace_books(tuple(self._books))
        self._catalog.replace_websites(tuple(self._websites))
        self._original_records = (tuple(self._papers), tuple(self._books), tuple(self._websites))
        if changed:
            self.catalog_changed.emit()
        self.accept()

    def _is_dirty(self) -> bool:
        """編集用一覧がダイアログ開始時の文献一覧と異なるかを返す。"""
        return (tuple(self._papers), tuple(self._books), tuple(self._websites)) != self._original_records

    def _current_kind(self) -> ReferenceKind:
        """現在選択されているタブに対応する文献種別を返す。"""
        return tuple(ReferenceKind)[self.tab_widget.currentIndex()]

    def _next_id(self, kind: ReferenceKind) -> str:
        """編集用一覧の同一種別に重複しない文献IDを発行する。"""
        prefix = f"{kind.value}-"
        numbers = [int(record.id.removeprefix(prefix)) for record in self._records_for_kind(kind) if record.id.removeprefix(prefix).isdigit()]
        return f"{prefix}{max(numbers, default=0) + 1:03d}"

    def _records_for_kind(self, kind: ReferenceKind) -> tuple[Paper, ...] | tuple[Book, ...] | tuple[Website, ...]:
        """指定種別の独立した文献ドメイン一覧を返す。"""
        return tuple(self._papers) if kind == ReferenceKind.PAPER else tuple(self._books) if kind == ReferenceKind.BOOK else tuple(self._websites)

    def _replace_records_for_kind(self, kind: ReferenceKind, records: tuple[Paper, ...] | tuple[Book, ...] | tuple[Website, ...]) -> None:
        """指定種別の編集用文献一覧だけを置き換える。"""
        if kind == ReferenceKind.PAPER:
            self._papers = list(records)
        elif kind == ReferenceKind.BOOK:
            self._books = list(records)
        else:
            self._websites = list(records)
