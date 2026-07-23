"""Canvas の見た目を style_key ごとに集約する。"""

from dataclasses import dataclass

from PyQt6.QtGui import QColor


@dataclass(frozen=True)
class NodeStyle:
    """ノード描画に必要な色。"""

    background: QColor
    border: QColor
    text: QColor
    secondary_text: QColor
    selection_border: QColor


@dataclass(frozen=True)
class EdgeStyle:
    """エッジ描画に必要な色。"""

    line: QColor
    selection_line: QColor
    label_background: QColor


class StyleRegistry:
    """意味ではなくキーだけでスタイルを取り出す。"""

    _node_styles = {
        "default": NodeStyle(QColor("#f8fafc"), QColor("#64748b"), QColor("#1e293b"), QColor("#475569"), QColor("#2563eb")),
        "question": NodeStyle(QColor("#eff6ff"), QColor("#3b82f6"), QColor("#172554"), QColor("#1d4ed8"), QColor("#1d4ed8")),
        "literature": NodeStyle(QColor("#f0fdf4"), QColor("#22c55e"), QColor("#14532d"), QColor("#166534"), QColor("#15803d")),
        "note": NodeStyle(QColor("#fffbeb"), QColor("#f59e0b"), QColor("#78350f"), QColor("#92400e"), QColor("#d97706")),
        "warning": NodeStyle(QColor("#fef2f2"), QColor("#ef4444"), QColor("#7f1d1d"), QColor("#991b1b"), QColor("#dc2626")),
    }
    _edge_styles = {
        "default": EdgeStyle(QColor("#64748b"), QColor("#2563eb"), QColor("#ffffff")),
        "note": EdgeStyle(QColor("#d97706"), QColor("#b45309"), QColor("#fffbeb")),
        "warning": EdgeStyle(QColor("#dc2626"), QColor("#b91c1c"), QColor("#fef2f2")),
    }

    @classmethod
    def node_style(cls, style_key: str) -> NodeStyle:
        """未知のキーには既定スタイルを返す。"""
        return cls._node_styles.get(style_key, cls._node_styles["default"])

    @classmethod
    def edge_style(cls, style_key: str) -> EdgeStyle:
        """未知のキーには既定スタイルを返す。"""
        return cls._edge_styles.get(style_key, cls._edge_styles["default"])

    @classmethod
    def set_edge_type_color(cls, style_key: str, color_hex: str) -> None:
        """設定画面で選んだ色を、指定エッジ種類用の描画スタイルとして登録する。"""
        color = QColor(color_hex)
        # 色相は残しつつ白へ寄せ、エッジラベルの文字コントラストを確保する。
        label_background = QColor(
            round(color.red() * 0.12 + 255 * 0.88),
            round(color.green() * 0.12 + 255 * 0.88),
            round(color.blue() * 0.12 + 255 * 0.88),
        )
        cls._edge_styles[style_key] = EdgeStyle(color, color.darker(130), label_background)
