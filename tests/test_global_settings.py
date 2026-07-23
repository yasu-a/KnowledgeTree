"""全体設定とエッジ種類編集Widgetを検証する。"""

from knowledge_tree.global_settings import GlobalSettings, NATURAL_PALETTE
from knowledge_tree.ui.edge_type_editor_widget import EdgeTypeEditorWidget


def test_global_settings_provides_fifteen_natural_palette_colors() -> None:
    """RGB入力の代わりに選択できる自然配色を15色用意する。"""
    assert len(NATURAL_PALETTE) == 15
    assert all(color.hex_color.startswith("#") for color in NATURAL_PALETTE)


def test_edge_type_editor_adds_updates_and_removes_a_type(qtbot: object) -> None:
    """専用Widgetからエッジ種類コレクションを追加・編集・削除できる。"""
    settings = GlobalSettings()
    widget = EdgeTypeEditorWidget(settings)
    qtbot.addWidget(widget)

    widget.add_button.click()
    widget.label_edit.setText("支持する")
    widget.label_edit.editingFinished.emit()
    widget.color_combo.setCurrentIndex(3)

    created_type = settings.edge_types()[-1]
    assert (created_type.label, created_type.color_hex) == ("支持する", "#0f766e")

    widget.remove_button.click()
    assert all(edge_type.id != created_type.id for edge_type in settings.edge_types())
