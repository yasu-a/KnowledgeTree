"""プロジェクト設定とエッジ種類編集Widgetを検証する。"""

from knowledge_tree.color_palette import ColorPalette, ColorToken
from knowledge_tree.project_settings import ProjectSettings
from knowledge_tree.node_kind import NodeKind
import pytest
from PyQt6.QtWidgets import QTabWidget
from knowledge_tree.ui.edge_type_editor_widget import EdgeTypeEditorWidget


def test_color_tokens_provide_fifteen_stable_palette_choices() -> None:
    """RGB入力の代わりに、安定した15個の色トークンを用意する。"""
    assert len(ColorToken) == 15
    assert [color_token.display_name for color_token in ColorToken] == ["Slate", "Blue", "Cyan", "Teal", "Emerald", "Green", "Lime", "Amber", "Orange", "Red", "Rose", "Pink", "Fuchsia", "Purple", "Indigo"]
    assert all(ColorPalette.color_hex(color_token).startswith("#") for color_token in ColorToken)


def test_edge_type_editor_updates_relation_color_and_allowed_endpoints(qtbot: object) -> None:
    """専用Widgetから関係種類の色と接続可能なノード種別を変更できる。"""
    settings = ProjectSettings()
    widget = EdgeTypeEditorWidget(settings)
    qtbot.addWidget(widget)

    widget.list_widget.setCurrentRow(1)
    widget.color_combo.setCurrentIndex(3)

    contributes = next(item for item in settings.edge_types() if item.id == "contributes-to")
    assert contributes.color_token == ColorToken.TEAL
    widget.endpoint_checks[(NodeKind.MEMO, NodeKind.QUESTION)].setChecked(False)
    widget.endpoint_checks[(NodeKind.QUESTION, NodeKind.MEMO)].setChecked(True)

    contributes = next(item for item in settings.edge_types() if item.id == "contributes-to")
    assert contributes.allowed_endpoints == ((NodeKind.QUESTION, NodeKind.MEMO), (NodeKind.REFERENCE, NodeKind.QUESTION))


def test_edge_type_editor_adds_edits_and_removes_relation_types(qtbot: object) -> None:
    """専用Widgetから関係種類を追加、編集、削除できる。"""
    settings = ProjectSettings()
    widget = EdgeTypeEditorWidget(settings)
    qtbot.addWidget(widget)

    widget.add_button.click()
    widget.label_edit.setText("commentsOn")
    widget.label_edit.editingFinished.emit()
    created = settings.edge_types()[-1]

    assert created.label == "commentsOn"
    assert created.allowed_endpoints == ((NodeKind.QUESTION, NodeKind.QUESTION),)
    widget.remove_button.click()
    assert all(edge_type.id != created.id for edge_type in settings.edge_types())


def test_edge_type_labels_are_unique_relation_identifiers() -> None:
    """エッジ種類ラベルは、グラフ上の関係種類を一意に識別する。"""
    settings = ProjectSettings()
    created = settings.add_edge_type()

    with pytest.raises(ValueError, match="重複"):
        settings.update_edge_type(created.id, "refines", ColorToken.SLATE, ((NodeKind.QUESTION, NodeKind.QUESTION),))


def test_edge_type_editor_updates_node_colors(qtbot: object) -> None:
    """プロジェクト設定Widgetからノード種類ごとの色を変更できる。"""
    settings = ProjectSettings()
    widget = EdgeTypeEditorWidget(settings)
    qtbot.addWidget(widget)

    widget.node_color_combos[NodeKind.MEMO].setCurrentIndex(9)

    assert settings.node_color(NodeKind.MEMO) == ColorToken.RED


def test_edge_type_editor_uses_left_side_tabs_for_relation_and_node_settings(qtbot: object) -> None:
    """設定Widgetは関係種類とノード色を左側タブへ分けて表示する。"""
    widget = EdgeTypeEditorWidget(ProjectSettings())
    qtbot.addWidget(widget)

    assert widget.tab_widget.tabPosition() == QTabWidget.TabPosition.West
    assert [widget.tab_widget.tabText(index) for index in range(widget.tab_widget.count())] == ["エッジの種類", "ノードの色"]
