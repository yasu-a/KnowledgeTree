"""テーマから解決する固定の色トークンと標準パレット。"""

from enum import StrEnum


class ColorToken(StrEnum):
    """テーマをまたいで安定する、選択可能な色の識別子。"""

    SLATE = "slate"
    BLUE = "blue"
    CYAN = "cyan"
    TEAL = "teal"
    EMERALD = "emerald"
    GREEN = "green"
    LIME = "lime"
    AMBER = "amber"
    ORANGE = "orange"
    RED = "red"
    ROSE = "rose"
    PINK = "pink"
    FUCHSIA = "fuchsia"
    PURPLE = "purple"
    INDIGO = "indigo"

    @property
    def display_name(self) -> str:
        """色選択UI向けの英語表示名を返す。"""
        return self.value.title()


class ColorPalette:
    """現在のテーマでColorTokenを実際の色へ解決する。"""

    _color_hex_by_token = {
        ColorToken.SLATE: "#64748b",
        ColorToken.BLUE: "#2563eb",
        ColorToken.CYAN: "#0891b2",
        ColorToken.TEAL: "#006d77",
        ColorToken.EMERALD: "#059669",
        ColorToken.GREEN: "#65a30d",
        ColorToken.LIME: "#84a80b",
        ColorToken.AMBER: "#d97706",
        ColorToken.ORANGE: "#ea580c",
        ColorToken.RED: "#dc2626",
        ColorToken.ROSE: "#e11d48",
        ColorToken.PINK: "#db2777",
        ColorToken.FUCHSIA: "#c026d3",
        ColorToken.PURPLE: "#7c3aed",
        ColorToken.INDIGO: "#4f46e5",
    }

    @classmethod
    def color_hex(cls, color_token: ColorToken) -> str:
        """指定トークンを現在のテーマの16進数カラーへ解決する。"""
        return cls._color_hex_by_token[color_token]

    @classmethod
    def color_token_for_hex(cls, color_hex: str) -> ColorToken | None:
        """旧設定の16進数カラーに対応する色トークンを返す。"""
        normalized_color_hex = color_hex.lower()
        for color_token, palette_color_hex in cls._color_hex_by_token.items():
            if normalized_color_hex == palette_color_hex:
                return color_token
        if normalized_color_hex == "#0f766e":
            return ColorToken.TEAL
        return None
