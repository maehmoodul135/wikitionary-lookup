# Wiktionary Lookup

A standalone Windows word-definition app, similar to "Definition for Command
Palette" but as its own window rather than a PowerToys extension — and with
definitions that scroll and wrap properly instead of getting clipped.

## What it does

- Type a word, press Enter (or click Search).
- **Definition** tab: a compact row per fact — one row for each sense
  (with part-of-speech badge), one row for each usage example, and one
  merged row each for synonyms and antonyms per part of speech. Rows wrap
  and grow to fit their full content — nothing gets clipped, however long
  the definition is. Click a synonym or antonym to look that word up too.
- **Wiktionary Page** tab: the actual `en.wiktionary.org` page for that
  word, embedded in the app — covers pronunciation audio, etymology, and
  anything else the structured data doesn't include.
- Remembers your recent searches for autocomplete (stored in `history.json`
  in a per-user app-data folder, so it works no matter where the exe lives).
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

- Definitions, phonetics, examples, synonyms, and antonyms come from the
  [Free Dictionary API](https://dictionaryapi.dev) (`api.dictionaryapi.dev`),
  which is itself built on Wiktionary content — this gives structured
  synonyms/antonyms per sense reliably, unlike Wiktionary's own raw API.
  Coverage still varies by word (some entries have fuller data than others,
  since it depends on how thoroughly that word's Wiktionary page has been
  edited). When something's missing from the Definition tab, the Wiktionary
  Page tab shows the full original source page as a fallback.
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

## Where to put the exe

You don't need `Program Files` for this to work like a "real" app — that
folder is Windows-protected and requires admin rights to write to, which
can cause headaches for portable single-file exes like this one (the app
now stores its search history in `%LOCALAPPDATA%\WiktionaryLookup\` instead
of next to the exe, specifically so it works fine no matter where the exe
lives). A simple, low-friction setup:

1. Create a folder like `C:\Apps\WiktionaryLookup\` and put `WiktionaryLookup.exe` there.
2. Right-click the exe → **Show more options** → **Create shortcut**.
3. Move that shortcut into your Start Menu folder (`Win+R`, type
   `shell:programs`, hit Enter, drop the shortcut in there) so it shows up
   when you search the Start Menu.
4. Right-click the Start Menu entry → **Pin to taskbar**, if you want it there too.

If you'd still rather use `Program Files`, it works the same way — just
expect a UAC ("do you want to allow this app...") prompt when you copy
files into it, since that folder needs admin approval to write to.

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
