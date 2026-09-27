"""
Wiktionary Lookup
A standalone word-definition app styled after compact "quick lookup" tools:
each definition, example, synonym set, and antonym set is its own row with
an icon and a type badge, and rows wrap to fit their full content instead
of clipping. A second tab embeds the real Wiktionary page for anything the
structured data doesn't cover (pronunciation audio, etymology, etc).

Run with:  python main.py
"""

import os
import sys
import json
from pathlib import Path
from urllib.parse import quote, unquote

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTabWidget, QListWidget, QListWidgetItem,
    QLabel, QCompleter
)
from PySide6.QtCore import Qt, QUrl, QStringListModel, QTimer
from PySide6.QtGui import QAction, QKeySequence, QIcon
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWebEngineWidgets import QWebEngineView

API_URL = "https://api.dictionaryapi.dev/api/v2/entries/en/{}"
PAGE_URL = "https://en.wiktionary.org/wiki/{}"

MAX_HISTORY = 50

# visual style per row "kind"
KIND_STYLE = {
    "definition": {"icon": "Aa", "color": "#89b4fa"},
    "example":    {"icon": "\u275d",  "color": "#a6adc8"},   # ❝
    "synonyms":   {"icon": "\u2194",  "color": "#a6e3a1"},   # ↔
    "antonyms":   {"icon": "\u21c4",  "color": "#f38ba8"},   # ⇄
}


def resource_path(relative_path):
    """Resolve a bundled resource whether running from source or from a
    PyInstaller --onefile exe (which unpacks assets into a temp folder)."""
    base_path = getattr(sys, "_MEIPASS", os.path.abspath(os.path.dirname(__file__)))
    return os.path.join(base_path, relative_path)


def get_app_data_dir():
    """A per-user, always-writable folder -- works whether the exe lives in
    Program Files, Downloads, or anywhere else that might be read-only."""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    app_dir = Path(base) / "WiktionaryLookup"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


HISTORY_PATH = get_app_data_dir() / "history.json"


class ResultRow(QWidget):
    """One row: an icon, a line of rich text that wraps freely, and a badge."""

    def __init__(self, kind, label_html, badge_text, on_word_link=None):
        super().__init__()
        style = KIND_STYLE.get(kind, KIND_STYLE["definition"])
        color = style["color"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(10)

        icon = QLabel(style["icon"])
        icon.setFixedSize(28, 28)
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet(
            f"background-color: {color}2A; color: {color}; border-radius: 14px; "
            f"font-weight: 600; font-size: 13px;"
        )
        layout.addWidget(icon, 0, Qt.AlignTop)

        text = QLabel(label_html)
        text.setTextFormat(Qt.RichText)
        text.setWordWrap(True)
        text.setOpenExternalLinks(False)
        text.setStyleSheet("font-size: 13px; color: #cdd6f4;")
        if on_word_link:
            text.linkActivated.connect(on_word_link)
        layout.addWidget(text, 1)

        badge = QLabel(badge_text)
        badge.setStyleSheet(
            f"background-color: {color}22; color: {color}; border: 1px solid {color}66; "
            f"border-radius: 9px; padding: 2px 10px; font-size: 11px;"
        )
        badge.setAlignment(Qt.AlignCenter)
        layout.addWidget(badge, 0, Qt.AlignTop)


class ResultsList(QListWidget):
    """A QListWidget whose rows re-wrap (and grow taller) when the window
    is resized, instead of clipping their content."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self.viewport().width()
        for i in range(self.count()):
            item = self.item(i)
            widget = self.itemWidget(item)
            if widget:
                widget.setFixedWidth(width)
                item.setSizeHint(widget.sizeHint())


class DictionaryWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wiktionary Lookup")
        self.resize(760, 560)
        icon_path = resource_path("icon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.nam = QNetworkAccessManager(self)
        self.history = self._load_history()

        self.debounce_timer = QTimer(self)
        self.debounce_timer.setSingleShot(True)
        self.debounce_timer.timeout.connect(self.on_search)

        self._build_ui()
        self.search_input.setFocus()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # -- search bar --------------------------------------------------
        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type a word and press Enter…")
        self.search_input.returnPressed.connect(self._search_now)
        self.search_input.textChanged.connect(self._on_text_changed)
        self.completer_model = QStringListModel(self.history)
        completer = QCompleter(self.completer_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.search_input.setCompleter(completer)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.on_search)

        search_row.addWidget(self.search_input)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        # -- tabs: rendered definition / live wiktionary page ------------
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.results_list = ResultsList()
        self.results_list.setStyleSheet("""
            QListWidget { background-color: #1e1e2e; border: none; }
            QListWidget::item { border-bottom: 1px solid #313244; }
            QListWidget::item:selected { background-color: transparent; }
        """)
        self.results_list.setSelectionMode(QListWidget.NoSelection)
        self.results_list.setFocusPolicy(Qt.NoFocus)
        self.tabs.addTab(self.results_list, "Definition")

        self.web_view = QWebEngineView()
        self.tabs.addTab(self.web_view, "Wiktionary Page")

        # -- status line ---------------------------------------------------
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #7f849c; font-size: 12px;")
        layout.addWidget(self.status_label)

        self._show_placeholder()

        # keep global focus shortcut: Ctrl+L jumps to the search box
        focus_action = QAction(self)
        focus_action.setShortcut(QKeySequence("Ctrl+L"))
        focus_action.triggered.connect(lambda: (self.search_input.setFocus(), self.search_input.selectAll()))
        self.addAction(focus_action)

    def _show_placeholder(self):
        self._set_rows([("definition", "<span style='color:#7f849c;'>Search for a word to see its definition here.</span>", "")])

    # ------------------------------------------------------------- history
    def _load_history(self):
        try:
            with open(HISTORY_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save_history(self):
        try:
            with open(HISTORY_PATH, "w", encoding="utf-8") as f:
                json.dump(self.history[-MAX_HISTORY:], f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _remember(self, word):
        if word in self.history:
            self.history.remove(word)
        self.history.append(word)
        self.history = self.history[-MAX_HISTORY:]
        self.completer_model.setStringList(self.history)
        self._save_history()

    # -------------------------------------------------------------- search
    def _on_text_changed(self, text):
        text = text.strip()
        if not text:
            self.debounce_timer.stop()
            self._show_placeholder()
            self.status_label.setText("")
            return
        self.debounce_timer.start(400)  # wait for a pause in typing

    def _search_now(self):
        self.debounce_timer.stop()
        self.on_search()

    def on_search(self):
        word = self.search_input.text().strip()
        if word:
            self.do_search(word)

    def on_word_link_clicked(self, href):
        word = unquote(href)
        if word:
            self.search_input.blockSignals(True)
            self.search_input.setText(word)
            self.search_input.blockSignals(False)
            self.debounce_timer.stop()
            self.do_search(word)

    def do_search(self, word):
        self.status_label.setText(f"Looking up “{word}”…")
        self._set_rows([("definition", "<span style='color:#7f849c;'>Loading…</span>", "")])

        # load the real page in the second tab straight away
        self.web_view.load(QUrl(PAGE_URL.format(quote(word))))

        req = QNetworkRequest(QUrl(API_URL.format(quote(word))))
        reply = self.nam.get(req)
        reply.finished.connect(lambda: self._handle_reply(reply, word))

    def _handle_reply(self, reply: QNetworkReply, word: str):
        reply.deleteLater()
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

        if reply.error() != QNetworkReply.NoError or status == 404:
            self.status_label.setText(f"No entry found for “{word}”.")
            self._set_rows([(
                "definition",
                f"<b>{word}</b> &nbsp; <span style='color:#7f849c;'>"
                f"No definition found. Check the <b>Wiktionary Page</b> tab — "
                f"it may still have relevant content.</span>",
                ""
            )])
            self._remember(word)
            return

        try:
            data = json.loads(bytes(reply.readAll().data()).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.status_label.setText(f"Could not parse response for “{word}”.")
            return

        rows = self._build_rows(data, word)
        self._set_rows(rows)
        self.status_label.setText(f"“{word}” — {len(rows)} results")
        self._remember(word)

    # ---------------------------------------------------------- row building
    def _build_rows(self, data, word):
        """Returns a list of (kind, label_html, badge_text) tuples, mirroring
        the compact row-per-fact style: a row per definition, a row per
        example, and one merged row each for synonyms/antonyms per part
        of speech."""
        if not isinstance(data, list) or not data:
            return [("definition", f"<b>{word}</b> &nbsp; <span style='color:#7f849c;'>No entries found.</span>", "")]

        entry = data[0]
        phonetic = entry.get("phonetic") or ""
        if not phonetic:
            for p in entry.get("phonetics", []):
                if p.get("text"):
                    phonetic = p["text"]
                    break

        rows = []
        for meaning in entry.get("meanings", []):
            pos = meaning.get("partOfSpeech", "")
            pos_label = pos.capitalize() if pos else "Word"

            all_synonyms, all_antonyms = [], []
            for m_syn in meaning.get("synonyms", []):
                if m_syn not in all_synonyms:
                    all_synonyms.append(m_syn)
            for m_ant in meaning.get("antonyms", []):
                if m_ant not in all_antonyms:
                    all_antonyms.append(m_ant)

            for defn in meaning.get("definitions", []):
                header = f"<b>{word}</b>"
                if phonetic:
                    header += f" <span style='color:#7f849c;'>{phonetic}</span>"
                header += f" <span style='color:#7f849c;'>({pos})</span>"
                rows.append((
                    "definition",
                    f"{header} &nbsp;&nbsp; {defn.get('definition', '')}",
                    pos_label,
                ))

                if defn.get("example"):
                    rows.append((
                        "example",
                        f"<b>Example ({pos})</b> &nbsp;&nbsp; \u201c{defn['example']}\u201d",
                        "example",
                    ))

                for s in defn.get("synonyms", []):
                    if s not in all_synonyms:
                        all_synonyms.append(s)
                for a in defn.get("antonyms", []):
                    if a not in all_antonyms:
                        all_antonyms.append(a)

            if all_synonyms:
                links = ", ".join(
                    f"<a href='{quote(w)}' style='color:#a6e3a1; text-decoration:none;'>{w}</a>"
                    for w in all_synonyms
                )
                rows.append((
                    "synonyms",
                    f"<b>Synonyms ({pos})</b> &nbsp;&nbsp; {links}",
                    "synonyms",
                ))

            if all_antonyms:
                links = ", ".join(
                    f"<a href='{quote(w)}' style='color:#f38ba8; text-decoration:none;'>{w}</a>"
                    for w in all_antonyms
                )
                rows.append((
                    "antonyms",
                    f"<b>Antonyms ({pos})</b> &nbsp;&nbsp; {links}",
                    "antonyms",
                ))

        if not rows:
            rows = [("definition", f"<b>{word}</b> &nbsp; <span style='color:#7f849c;'>No definitions found.</span>", "")]
        return rows

    def _set_rows(self, rows):
        self.results_list.clear()
        width = self.results_list.viewport().width()
        for kind, label_html, badge_text in rows:
            item = QListWidgetItem()
            widget = ResultRow(kind, label_html, badge_text, on_word_link=self.on_word_link_clicked)
            if width > 0:
                widget.setFixedWidth(width)
            item.setSizeHint(widget.sizeHint())
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, widget)


def main():
    app = QApplication(sys.argv)
    icon_path = resource_path("icon.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    window = DictionaryWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
