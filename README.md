# Wiktionary Lookup

A standalone Windows word-definition app, similar to "Definition for Command
Palette" but as its own window rather than a PowerToys extension — and with
definitions that scroll and wrap properly instead of getting clipped.

## What it does

- Type a word, press Enter (or click Search).
- **Definition** tab: numbered senses grouped by part of speech, with usage
  examples and related words, pulled from Wiktionary's structured API and
  rendered in a scrolling panel — no truncation, however long the entry is.
- **Wiktionary Page** tab: the actual `en.wiktionary.org` page for that word,
  embedded in the app — covers pronunciation audio, etymology, and anything
  else the structured data doesn't include.
- Click any linked word inside a definition to look *that* word up instead
  of leaving the app.
- Remembers your recent searches for autocomplete (stored in `history.json`
  next to the script).
- `Ctrl+L` jumps focus to the search box from anywhere in the window.

## Setup

1. Install Python 3.10+ from [python.org](https://www.python.org/) (check "Add to PATH").
2. In this folder, install dependencies:

   ```
   pip install -r requirements.txt
   ```

3. Run it:

   ```
   python main.py
   ```

The first run may take a moment longer while Qt's WebEngine component
initializes — that's normal.

## Notes on the data

- Definitions, examples, and related words come from Wiktionary's public
  REST API (`/api/rest_v1/page/definition/`). Coverage of synonyms/antonyms
  varies by word — some entries have them, some don't — since that depends
  on how thoroughly the word's page has been edited. When they're missing
  from the Definition tab, the Wiktionary Page tab will still show whatever
  exists on the source page (e.g. under "Synonyms" as a Wikitext section
  the API doesn't structure).
- Requires an internet connection.

## Packaging as a standalone .exe

PyInstaller has to run on Windows to produce a Windows `.exe` (it doesn't
cross-compile), so pick whichever of these fits how you work:

**Option A — build it yourself on Windows**

Double-click `build.bat` in this folder. It creates a virtual environment,
installs everything needed, and runs PyInstaller for you. When it finishes,
your exe is at `dist\WiktionaryLookup.exe`.

**Option B — build it in the cloud via GitHub Actions**

If you push this folder to a GitHub repo, `.github/workflows/build.yml` will
build the exe on a real Windows runner automatically. Go to the repo's
**Actions** tab after pushing (or after running the workflow manually) and
download the `WiktionaryLookup-windows-exe` artifact — no Windows machine
or local Python setup required on your end.

Either way, Qt WebEngine adds noticeably to the build size (~150–200 MB)
since it bundles a Chromium runtime — that's expected.

## Running it at startup (optional)

Press `Win+R`, type `shell:startup`, hit Enter. Create a shortcut there to
`pythonw.exe main.py` (use `pythonw.exe` so no console window appears),
with "Start in" set to this folder.

## Ideas for extending it

- Add a keyboard shortcut to jump straight from the Definition tab to the
  Wiktionary tab for the same word (they already load in parallel).
- Cache recent lookups locally so repeat searches don't need the network.
- Add a dark/light theme toggle.
- Support other Wiktionary language editions (currently hardcoded to `en.wiktionary.org`).
