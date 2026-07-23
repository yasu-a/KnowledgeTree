"""種類ごとに独立した文献ドメインとCP932 CSVリポジトリ。"""

import csv
import os
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from tempfile import NamedTemporaryFile


class ReferenceKind(StrEnum):
    """グラフから文献を特定するための文献種別。"""

    PAPER = "paper"
    BOOK = "book"
    WEBSITE = "website"


@dataclass(frozen=True)
class ReferenceLink:
    """グラフノードが参照する文献の種別とIDの組。"""

    kind: ReferenceKind
    id: str


@dataclass(frozen=True)
class Paper:
    """論文CSVの一行に対応する論文ドメインモデル。"""

    id: str
    title: str
    authors: str = ""
    year: str = ""
    doi: str = ""
    url: str = ""
    notes: str = ""


@dataclass(frozen=True)
class Book:
    """書籍CSVの一行に対応する書籍ドメインモデル。"""

    id: str
    title: str
    authors: str = ""
    year: str = ""
    isbn: str = ""
    publisher: str = ""
    notes: str = ""


@dataclass(frozen=True)
class Website:
    """WebサイトCSVの一行に対応するWebサイトドメインモデル。"""

    id: str
    title: str
    site_name: str = ""
    published_at: str = ""
    accessed_at: str = ""
    url: str = ""
    notes: str = ""


class ReferenceCatalog:
    """3つの独立した文献リポジトリへアクセスするアプリケーション窓口。"""

    _headers_by_kind = {
        ReferenceKind.PAPER: ("id", "title", "authors", "year", "doi", "url", "notes"),
        ReferenceKind.BOOK: ("id", "title", "authors", "year", "isbn", "publisher", "notes"),
        ReferenceKind.WEBSITE: ("id", "title", "site_name", "published_at", "accessed_at", "url", "notes"),
    }

    def __init__(self, project_directory: Path) -> None:
        """プロジェクト配下のreferencesディレクトリを設定する。"""
        self._directory = project_directory / "references"

    def papers(self) -> tuple[Paper, ...]:
        """papers.csvの論文一覧を返す。"""
        return self._read_papers()

    def books(self) -> tuple[Book, ...]:
        """books.csvの書籍一覧を返す。"""
        return self._read_books()

    def websites(self) -> tuple[Website, ...]:
        """websites.csvのWebサイト一覧を返す。"""
        return self._read_websites()

    def find(self, link: ReferenceLink) -> Paper | Book | Website | None:
        """文献リンクが示す種類別リポジトリから対象を取得する。"""
        records = self.papers() if link.kind == ReferenceKind.PAPER else self.books() if link.kind == ReferenceKind.BOOK else self.websites()
        return next((record for record in records if record.id == link.id), None)

    def create_paper(self, title: str) -> Paper:
        """論文をpapers.csvへ追加して返す。"""
        paper = Paper(self._next_id(ReferenceKind.PAPER), title)
        self.replace_papers((*self.papers(), paper))
        return paper

    def replace_papers(self, papers: tuple[Paper, ...]) -> None:
        """論文一覧をpapers.csvへまとめて保存する。"""
        self._write_rows(ReferenceKind.PAPER, [paper.__dict__ for paper in papers])

    def replace_books(self, books: tuple[Book, ...]) -> None:
        """書籍一覧をbooks.csvへまとめて保存する。"""
        self._write_rows(ReferenceKind.BOOK, [book.__dict__ for book in books])

    def replace_websites(self, websites: tuple[Website, ...]) -> None:
        """Webサイト一覧をwebsites.csvへまとめて保存する。"""
        self._write_rows(ReferenceKind.WEBSITE, [website.__dict__ for website in websites])

    def ensure_files(self) -> None:
        """未作成の種類別CSVへExcel互換ヘッダを作成する。"""
        self._directory.mkdir(parents=True, exist_ok=True)
        for kind in ReferenceKind:
            if not self._path_for(kind).exists():
                self._write_rows(kind, [])

    def _read_papers(self) -> tuple[Paper, ...]:
        """論文CSVをPaperの組として読み込む。"""
        return tuple(Paper(**row) for row in self._read_rows(ReferenceKind.PAPER))

    def _read_books(self) -> tuple[Book, ...]:
        """書籍CSVをBookの組として読み込む。"""
        return tuple(Book(**row) for row in self._read_rows(ReferenceKind.BOOK))

    def _read_websites(self) -> tuple[Website, ...]:
        """WebサイトCSVをWebsiteの組として読み込む。"""
        return tuple(Website(**row) for row in self._read_rows(ReferenceKind.WEBSITE))

    def _read_rows(self, kind: ReferenceKind) -> tuple[dict[str, str], ...]:
        """指定種類のCSVを、その種類固有の列名を保った辞書として読み込む。"""
        path = self._path_for(kind)
        if not path.exists():
            return ()
        with path.open(encoding="cp932", newline="") as file:
            return tuple({header: row.get(header, "") for header in self._headers_by_kind[kind]} for row in csv.DictReader(file) if row.get("id") and row.get("title"))

    def _write_rows(self, kind: ReferenceKind, rows: list[dict[str, str]]) -> None:
        """種類固有の列を保ったCSV全体を一時ファイル経由で原子的に置換する。"""
        self._directory.mkdir(parents=True, exist_ok=True)
        headers = self._headers_by_kind[kind]
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile("w", encoding="cp932", newline="", dir=self._directory, delete=False) as file:
                temporary_path = Path(file.name)
                writer = csv.DictWriter(file, fieldnames=headers, lineterminator="\r\n")
                writer.writeheader()
                writer.writerows({header: row.get(header, "") for header in headers} for row in rows)
                file.flush()
                os.fsync(file.fileno())
            temporary_path.replace(self._path_for(kind))
        except (OSError, UnicodeEncodeError) as error:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()
            raise ValueError(f"{kind.value}s.csvをCP932で保存できません。") from error

    def _next_id(self, kind: ReferenceKind) -> str:
        """指定種類内で重複しない文献IDを発行する。"""
        prefix = f"{kind.value}-"
        records = self.papers() if kind == ReferenceKind.PAPER else self.books() if kind == ReferenceKind.BOOK else self.websites()
        numbers = [int(record.id.removeprefix(prefix)) for record in records if record.id.removeprefix(prefix).isdigit()]
        return f"{prefix}{max(numbers, default=0) + 1:03d}"

    def _path_for(self, kind: ReferenceKind) -> Path:
        """指定種類のCSVパスを返す。"""
        return self._directory / f"{kind.value}s.csv"
