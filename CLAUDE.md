# DeckPad — Projektkontext für Claude

## Was ist das?

**DeckPad** — macOS/Windows Menu-Bar-App für den AJAZZ AKP03E Macro-Pad.
6 Buttons + 3 Knobs + 3 Nav-Buttons. Konfigurierbar über ein Tray-Icon-Menü
und ein Konfigurations-Fenster.

## Tech-Stack

- Python 3 + **PySide6** (migriert von PyQt6)
- HIDAPI für Gerätekommunikation
- Pillow für Icon-Rendering auf dem Gerät
- PyObjC (pyobjc-framework-Cocoa/Quartz) auf macOS
- pyautogui auf Windows

## Architektur

```
app_main.py          — Einstiegspunkt, QApplication zuerst (!)
app/menu_bar.py      — MenuBarApp: QSystemTrayIcon + Signalverdrahtung
app/config_window.py — Konfigurationsfenster (Szenen, Knobs, Buttons, Settings)
app/hid_thread.py    — HIDThread (Main-Thread, SIGBUS-sicher), _run_action
app/button_editor.py — ButtonEditorDialog, KnobEditorDialog, NavButtonEditorDialog
app/scene_widget.py  — SceneWidget: visuelle Darstellung einer Szene
app/library_panel.py — ButtonGridWidget: Button-Bibliothek
app/log_window.py    — LogWindow: Echtzeit-Ereignis-Log (Singleton)
app/styles.py        — Globales Stylesheet (Dark Mode)
actions.py           — Plattformübergreifende Aktionen (shortcuts, media, apps)
log_sink.py          — Globaler Log-Kanal (Signal-basiert, thread-safe)
config/config_manager.py — ConfigManager: config.json laden/speichern
autostart.py         — Autostart bei Login (macOS launchd / Windows Registry)
```

## Copyright-Regel (IMMER beachten)

**Vor jedem Commit und bei jeder Verwendung von Grafiken, Symbolen oder Icons prüfen:**

- SF Symbols (Apple) → lokal generieren, **nie in Git einchecken** (`assets/icons/` ist in `.gitignore`)
- App-Icons aus `.app`-Bundles (z. B. Calendar.app) → ebenfalls nicht einchecken
- Drittanbieter-Icons (App-Logos etc.) → nur verwenden wenn Lizenz es erlaubt
- Bei Unsicherheit über die Nutzungsrechte: **immer zuerst nachfragen**

Icons in diesem Projekt werden beim ersten App-Start automatisch generiert
(`create_library_icons.py` → AppKit/SF Symbols → lokal, nicht auf GitHub).

## Bekannte macOS-Fallstricke in diesem Projekt

### 1. Emoji-Bug (Bus Error) → siehe ~/.claude/CLAUDE.md
Kein Farb-Emoji (U+1F000+) in Qt-Widgets oder QMenu-Items.
**Sichere Symbole im Menü:** `⬤ ⚙ ✓ ✕ ☰ ✦ ▶ ◀`

### 2. QApplication zuerst
`app_main.py` importiert alle App-Module erst NACH `QApplication()` — immer
so beibehalten.

### 3. SIGBUS / NSMenu-Rebuild
`_rebuild_menu()` darf nicht sofort in `_on_menu_hidden()` aufgerufen werden
(GC zerstört QActions vor triggered). Delay: `QTimer.singleShot(200, ...)`.

### 4. HID-Polling pausieren
`pause_polling()` / `resume_polling()` in `aboutToShow` / `aboutToHide` —
niemals HIDAPI im Background-Thread aufrufen.

### 5. NSWindowCollectionBehaviorMoveToActiveSpace
Fenster via `winId()` → NSView → `.window()` auf den aktuellen macOS-Space
bringen (nicht per Titel-Lookup — race-prone).

## System-App-Icon-Extraktion (macOS)

Apps wie Calendar, Notes, Reminders haben kein `.icns` im Bundle — ihr Icon
steckt in `Assets.car`. `_find_icns()` gibt None zurück → alter Code warf
`FileNotFoundError`.

**Lösung:** `_extract_via_nsworkspace(app_path)` in `icons.py`:
- `NSWorkspace.sharedWorkspace().iconForFile_()` → NSImage
- `NSImage.TIFFRepresentation()` → `NSBitmapImageRep` → PNG (kein `lockFocus`)
- Gecacht in `~/Library/Application Support/DeckPad/icons/<AppName>.png`
- Cache-Treffer: < 1 ms

`load_app_icon()` fällt transparent durch:
`_find_icns()` → `_extract_via_nsworkspace()` → `raise FileNotFoundError`

Kein Dateiformat-Change. Kein Change an scene_widget.py oder button_editor.py
(außer einem Hinweis-Label im App-Icon-Panel). Commit: `ad392ed`.

## Aktueller Stand (Mai 2026)

### Fertig
- Grundfunktion: Buttons, Knobs (drehen + drücken), Nav-Buttons
- Konfigurationsfenster: Szenen, Button-Editor, Knob-Editor, Settings
- Button-Bibliothek (library_panel + in ButtonEditorDialog + KnobEditorDialog)
- Autostart (macOS launchd / Windows Registry)
- Knob-Druck-Aktion (press_action) — vollständig implementiert
- Ereignis-Log-Fenster (LogWindow + log_sink)
- Media-Key-Fix: f7–f12 → NX_KEYTYPE via _post_media_key_macos()
- PySide6-Migration (von PyQt6)
- Windows-Kompatibilität (actions.py plattform-aware)
- Scroll-Aktion für Knob (alle drei CGEvent-Delta-Felder, Browser-kompatibel)
- Accessibility-Check beim Start (AXIsProcessTrusted + Dialog mit Link)
- System-App-Icon-Extraktion (NSWorkspace, für Calendar/Notes/Reminders)

### Ausstehend
- App-Bundle bauen (PyInstaller) — nächster geplanter Schritt
- Drag & Drop in Button-Slots
- README-Screenshots für GitHub
- Gatekeeper / Notarisierung
- Bug: Downloads-Ordner-Permission (GitHub Issue #1, low priority)

## Daten

- Config: `data/config.json`
- Button-Bibliothek: `data/library/buttons.json`
- Seiten-Bibliothek: `data/library/pages/`
- Autostart-Plist (macOS): `~/Library/LaunchAgents/app.deckpad.plist`
