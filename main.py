"""
Wiktionary Lookup
A standalone word-definition app: type a word, see its full definitions
(part of speech, numbered senses, examples, related words) in a panel
that scrolls and wraps instead of clipping, plus a second tab with the
real Wiktionary page embedded for anything the structured API doesn't
cover (pronunciation audio, etymology, etc).

Run with:  python main.py
"""

import sys
import json
from urllib.parse import quote, unquote, urlparse

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLineEdit, QPushButton, QTabWidget, QTextBrowser, QLabel, QCompleter
)
from PySide6.QtCore import Qt, QUrl, QStringListModel
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWebEngineWidgets import QWebEngineView

API_URL = "https://en.wiktionary.org/api/rest_v1/page/definition/{}"
PAGE_URL = "https://en.wiktionary.org/wiki/{}"

HISTORY_PATH = "history.json"
MAX_HISTORY = 50


class DictionaryWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Wiktionary Lookup")
        self.resize(760, 560)

        self.nam = QNetworkAccessManager(self)
        self.history = self._load_history()

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
        self.search_input.returnPressed.connect(self.on_search)
        self.completer_model = QStringListModel(self.history)
        completer = QCompleter(self.completer_model, self)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.search_input.setCompleter(completer)

        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self.on_search)

        search_row.addWidget(self.search_input)
        search_row.addWidget(search_btn)
        layout.addLayout(search_row)

        # -- status line ---------------------------------------------------
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)

        # -- tabs: rendered definition / live wiktionary page ------------
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.definition_view = QTextBrowser()
        self.definition_view.setOpenLinks(False)  # intercept, don't navigate away
        self.definition_view.anchorClicked.connect(self.on_definition_link_clicked)
        self.definition_view.setStyleSheet("font-size: 14px;")
        self.tabs.addTab(self.definition_view, "Definition")

        self.web_view = QWebEngineView()
        self.tabs.addTab(self.web_view, "Wiktionary Page")

        self._show_placeholder()

        # keep global focus shortcut: Ctrl+L jumps to the search box
        focus_action = QAction(self)
        focus_action.setShortcut(QKeySequence("Ctrl+L"))
        focus_action.triggered.connect(lambda: (self.search_input.setFocus(), self.search_input.selectAll()))
        self.addAction(focus_action)

    def _show_placeholder(self):
        self.definition_view.setHtml(
            "<p style='color:#888;'>Search for a word to see its definition here.</p>"
        )

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
    def on_search(self):
        word = self.search_input.text().strip()
        if word:
            self.do_search(word)

    def on_definition_link_clicked(self, url: QUrl):
        """A word inside a definition was clicked -- look it up instead of navigating away."""
        path = url.path()  # e.g. /wiki/example
        candidate = unquote(path.rsplit("/", 1)[-1]) if path else ""
        if candidate:
            self.search_input.setText(candidate)
            self.do_search(candidate)

    def do_search(self, word):
        self.status_label.setText(f"Looking up “{word}”…")
        self.definition_view.setHtml("<p style='color:#888;'>Loading…</p>")

        # load the real page in the second tab straight away
        self.web_view.load(QUrl(PAGE_URL.format(quote(word))))

        # fetch structured definition data
        req = QNetworkRequest(QUrl(API_URL.format(quote(word))))
        reply = self.nam.get(req)
        reply.finished.connect(lambda: self._handle_reply(reply, word))

    def _handle_reply(self, reply: QNetworkReply, word: str):
        reply.deleteLater()
        status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)

        if reply.error() != QNetworkReply.NoError or status == 404:
            self.status_label.setText(f"No entry found for “{word}”.")
            self.definition_view.setHtml(
                f"<h2>{word}</h2>"
                f"<p style='color:#888;'>No definition found. "
                f"Check the <b>Wiktionary Page</b> tab — it may still have relevant "
                f"content (alternate spelling, redirect, etc).</p>"
            )
            self._remember(word)
            return

        try:
            data = json.loads(bytes(reply.readAll().data()).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.status_label.setText(f"Could not parse response for “{word}”.")
            return

        self.status_label.setText(f"Showing results for “{word}”.")
        self.definition_view.setHtml(self._render_html(data, word))
        self._remember(word)

    # -------------------------------------------------------------- render
    def _render_html(self, data: dict, word: str) -> str:
        entries = data.get("en") or (next(iter(data.values())) if data else [])
        if not entries:
            return f"<h2>{word}</h2><p style='color:#888;'>No English entry found.</p>"

        html = [f"<h2>{word}</h2>"]
        for entry in entries:
            pos = entry.get("partOfSpeech", "")
            html.append(f"<h3 style='margin-bottom:2px;'>{pos}</h3>")
            html.append("<ol style='margin-top:4px;'>")
            for d in entry.get("definitions", []):
                definition_text = d.get("definition", "")
                html.append(f"<li style='margin-bottom:10px;'>{definition_text}")

                for ex in d.get("parsedExamples") or []:
                    ex_text = ex.get("example") if isinstance(ex, dict) else ex
                    if ex_text:
                        html.append(f"<br><span style='color:#888;'><i>e.g. {ex_text}</i></span>")

                for rel in d.get("relatedWords") or []:
                    rtype = (rel.get("relationshipType") or "").capitalize()
                    words = ", ".join(rel.get("words", []))
                    if words:
                        html.append(f"<br><b>{rtype}s:</b> {words}")

                html.append("</li>")
            html.append("</ol>")
        return "".join(html)


def main():
    app = QApplication(sys.argv)
    window = DictionaryWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
