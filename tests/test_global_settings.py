"""プロジェクト設定とエッジ種類編集Widgetを検証する。"""

from knowledge_tree.color_palette import ColorPalette, ColorToken
from knowledge_tree.project_settings import ProjectSettings
from knowledge_tree.ui.edge_type_editor_widget import EdgeTypeEditorWidget


def test_color_tokens_provide_fifteen_stable_palette_choices() -> None:
    """RGB入力の代わりに、安定した15個の色トークンを用意する。"""
    assert len(ColorToken) == 15
    assert [color_token.display_name for color_token in ColorToken] == ["Slate", "Blue", "Cyan", "Teal", "Emerald", "Green", "Lime", "Amber", "Orange", "Red", "Rose", "Pink", "Fuchsia", "Purple", "Indigo"]
    assert all(ColorPalette.color_hex(color_token).startswith("#") for color_token in ColorToken)


def test_edge_type_editor_adds_updates_and_removes_a_type(qtbot: object) -> None:
    """専用Widgetからエッジ種類コレクションを追加・編集・削除できる。"""
    settings = ProjectSettings()
    widget = EdgeTypeEditorWidget(settings)
    qtbot.addWidget(widget)

    widget.add_button.click()
    widget.label_edit.setText("支持する")
    widget.label_edit.editingFinished.emit()
    widget.color_combo.setCurrentIndex(3)

    created_type = settings.edge_types()[-1]
    assert (created_type.label, created_type.color_token) == ("支持する", ColorToken.TEAL)

    widget.remove_button.click()
    assert all(edge_type.id != created_type.id for edge_type in settings.edge_types())
