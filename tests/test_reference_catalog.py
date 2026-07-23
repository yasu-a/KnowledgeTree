"""独立した文献ドメインと文献一覧ダイアログを検証する。"""

from pathlib import Path

import pytest

from knowledge_tree.reference_catalog import Book, Paper, ReferenceCatalog, ReferenceKind, ReferenceLink, Website
from knowledge_tree.ui.reference_catalog_dialog import ReferenceCatalogDialog


def test_catalog_persists_each_reference_domain_in_its_own_cp932_csv(tmp_path: Path) -> None:
    """Paper・Book・Websiteは共通レコード化せず、それぞれのCSV列で保存する。"""
    catalog = ReferenceCatalog(tmp_path)
    catalog.replace_papers((Paper("paper-001", "論文", doi="10.1/example"),))
    catalog.replace_books((Book("book-001", "書籍", isbn="978-1", publisher="出版社"),))
    catalog.replace_websites((Website("website-001", "Webサイト", site_name="サイト", accessed_at="2026-01-01"),))

    assert catalog.papers()[0].doi == "10.1/example"
    assert catalog.books()[0].publisher == "出版社"
    assert catalog.websites()[0].site_name == "サイト"
    assert catalog.find(ReferenceLink(ReferenceKind.BOOK, "book-001")) == catalog.books()[0]


def test_csv_save_is_atomic_and_preserves_previous_file_when_cp932_encoding_fails(tmp_path: Path) -> None:
    """CP932へ保存できない文字があっても、既存のCSVを一時ファイル置換前に壊さない。"""
    catalog = ReferenceCatalog(tmp_path)
    catalog.replace_papers((Paper("paper-001", "保存済み文献"),))
    paper_path = tmp_path / "references" / "papers.csv"
    previous_contents = paper_path.read_text(encoding="cp932")

    with pytest.raises(ValueError, match="papers.csv"):
        catalog.replace_papers((Paper("paper-001", "😀を含む文献"),))

    assert paper_path.read_text(encoding="cp932") == previous_contents
    assert len(tuple((tmp_path / "references").iterdir())) == 1


def test_reference_catalog_dialog_cancels_or_saves_each_domain(qtbot: object, tmp_path: Path) -> None:
    """文献一覧のCancelは各CSVを変えず、Saveで現在の種類別一覧を保存する。"""
    catalog = ReferenceCatalog(tmp_path)
    catalog.create_paper("既存文献")
    canceled_dialog = ReferenceCatalogDialog(catalog)
    qtbot.addWidget(canceled_dialog)
    canceled_dialog.add_button.click()
    canceled_dialog.discard()
    assert len(catalog.papers()) == 1

    saved_dialog = ReferenceCatalogDialog(catalog)
    qtbot.addWidget(saved_dialog)
    saved_dialog.add_button.click()
    saved_dialog._save_and_accept()
    assert len(catalog.papers()) == 2


def test_reference_catalog_dialog_adds_edits_and_saves_every_reference_domain(qtbot: object, tmp_path: Path) -> None:
    """Paper・Book・Websiteの各タブで、追加とセル編集を安全に保存できる。"""
    catalog = ReferenceCatalog(tmp_path)
    dialog = ReferenceCatalogDialog(catalog)
    qtbot.addWidget(dialog)
    edit_values = {
        ReferenceKind.PAPER: ("論文タイトル", "10.1/example"),
        ReferenceKind.BOOK: ("書籍タイトル", "978-1"),
        ReferenceKind.WEBSITE: ("サイトタイトル", "研究サイト"),
    }

    for tab_index, kind in enumerate(ReferenceKind):
        dialog.tab_widget.setCurrentIndex(tab_index)
        dialog.add_button.click()
        table = dialog.tables[kind]
        title, specific_value = edit_values[kind]
        table.item(0, 0).setText(title)
        table.item(0, 3 if kind != ReferenceKind.WEBSITE else 1).setText(specific_value)

    dialog._save_and_accept()

    assert catalog.papers()[0] == Paper("paper-001", "論文タイトル", doi="10.1/example")
    assert catalog.books()[0] == Book("book-001", "書籍タイトル", isbn="978-1")
    assert catalog.websites()[0] == Website("website-001", "サイトタイトル", site_name="研究サイト")


def test_reference_catalog_dialog_shows_domain_csv_columns_in_separate_top_tabs(qtbot: object, tmp_path: Path) -> None:
    """文献一覧は3種類を上部タブに分け、それぞれ固有のCSV列を表示する。"""
    dialog = ReferenceCatalogDialog(ReferenceCatalog(tmp_path))
    qtbot.addWidget(dialog)
    assert [dialog.tab_widget.tabText(index) for index in range(dialog.tab_widget.count())] == ["Paper", "Book", "Website"]
    assert [dialog.tables[ReferenceKind.WEBSITE].horizontalHeaderItem(index).text() for index in range(dialog.tables[ReferenceKind.WEBSITE].columnCount())] == ["title", "site_name", "published_at", "accessed_at", "url", "notes"]
    dialog.discard()
