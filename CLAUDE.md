# DeckPad — Projektkontext für Claude

## Vault – Single Source of Truth

Das gesamte Projektwissen lebt im Obsidian Vault. Claude Code liest und schreibt dort direkt.

**Vault-Basis:**
`/Users/johannesluschow/kDrive/00 zweites Gehirn Obsidian/Zweites Gehirn/`

### Wichtigste Regel: Vault zuerst
Bei **jeder** projektbezogenen Anfrage (Status, offene Aufgaben, Bugs, Entscheidungen) **immer zuerst die Vault-Dateien lesen** — nie zuerst den Code durchsuchen. Der Vault ist die einzige Quelle der Wahrheit. Quellcode nur lesen wenn eine konkrete Implementierungsaufgabe vorliegt.

### Beim Session-Start immer lesen
- `03 Projekte/Privat/AJAZZ AKP03E.md` — aktueller Status, offene Aufgaben, bekannte Bugs, Architektur
- `03 Projekte/Privat/AJAZZ AKP03E – GitHub Vorbereitung.md` — GitHub-Entscheidungen, Branding

### Bei Bedarf lesen
| Kontext | Datei |
|---|---|
| Bekannte macOS/PySide6 Bugs | `05 Ressourcen/macOS PySide6 Qt Bug Patterns.md` |
| Dante-Integration (DDM API) | `03 Projekte/TH OWL/Doktorarbeit/Prototyp – Dante Voice Control.md` |
| Copyright-Regeln Icons/Symbole | Abschnitt „Copyright-Regel" in `AJAZZ AKP03E.md` |

### Vault schreiben
- Neuen Bug gefunden → in `AJAZZ AKP03E.md` unter „Bekannte Bugs & Fixes" eintragen
- Task erledigt → Checkbox in `AJAZZ AKP03E.md` auf `[x]` setzen
- Session beendet → „Wo wir beim nächsten Mal weitermachen" und „Prompt für nächste Session" aktualisieren

---

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

## Task-Synchronisierung mit Vault

**Wenn während dieser CC-Session neue Tasks entstehen oder sich bestehende Tasks ändern:**

Dokumentiere am Session-Ende:
```
Tasks entstanden/geändert:
- [todo/in_progress/done] Task-Name
- [todo/in_progress/done] Task-Name
```

→ **Claudian synchronisiert automatisch** in [[03 Projekte/Privat/DeckPad – Dante Voice Control Integration]]

Einfach aufzählen, die Automation macht den Rest.

---

## Automatische Task-Status-Prüfung

### Beim Session-Start (automatisch)
1. Lese die Vault-Projektdatei: `[[03 Projekte/Privat/DeckPad – Dante Voice Control Integration]]`
2. Parse die `tasks:` Array
3. Rapportiere: "Aktuelle Tasks im Dashboard:"
   ```
   ☐ Todo (X Tasks):  Task A, Task B, …
   🟡 In Progress (Y Tasks): Task C, …
   ✅ Done (Z Tasks): Task D, …
   ```
4. Kurze Analyse: "Was ist der aktuelle Code-Status zu diesen Tasks?"

### Während der Session
- Wenn Code-Änderungen gemacht werden: kontinuierlich prüfen „Ist diese Task jetzt erledigt?"
- Rapportiere: `✅ Task X implementiert & getestet → Status wird auf 'done' gesetzt`
- Oder: `🟡 Task Y begonnen → Status: 'in_progress'`

### Am Ende der Session (automatisch)
Generiere einen Task-Update-Report:
```
Task-Status-Änderungen:
- Task A: todo → in_progress
- Task B: in_progress → done
- Task C: todo (nicht gestartet)
```

→ **Claudian synchronisiert diese Updates automatisch ins Vault**

---

## Aktueller Stand (Juni 2026, Phase 6 + 7)

### ✅ Fertig
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
- **App-Bundle bauen (PyInstaller)** — v0.1.0 gebaut + installiert ✅
- **Drag & Drop in Button-Slots** — LCD-Buttons und Knobs tauschbar ✅ (Commit 599e237)
- **README-Screenshots** — 3 Screenshots in docs/screenshots/ ✅ (Commit 0c46178)
- **Phase 6 — Dante DDM Integration** ✅
  - `dante_route` Aktionstyp mit Multi-Routen per Button
  - Settings-Tab mit Host/API-Key + Validierung ("Verbindung testen")
  - Button-Bibliothek erweitert: Kategorie "Dante" (Voice Chat + 3 Route-Templates)
  - 7 Commits gepusht zu GitHub (2026-06-03)
- **Phase 7 — Dante Voice Control Integration** ✅ (Grundgerüst)
  - `dante_voice_toggle()` Action für TCP-Socket (localhost:9999)
  - UI: neuer Action-Typ "Dante Voice Control" im Button-Editor

### ⏳ Ausstehend
- **Windows-Build** — PyInstaller `.exe` + Test
- **Gatekeeper / Notarisierung** — Codesignatur + macOS Notarisierung
- **Phase 7 Ausbau:**
  - Status-IPC: dante_app.py sendet REC/BEREIT/FEHLER zu DeckPad
  - Button-Display zeigt Status per Farbe/Label
  - Preset-Buttons: feste Routing-Presets ohne Sprache
  - "Disconnect All"-Taste
- **Bug 13:** Downloads-Ordner-Permission (GitHub Issue #1, niedrige Prio)

## Daten

- Config: `data/config.json`
- Button-Bibliothek: `data/library/buttons.json`
- Seiten-Bibliothek: `data/library/pages/`
- Autostart-Plist (macOS): `~/Library/LaunchAgents/app.deckpad.plist`

## Projekt-Pfad

```
/Users/johannesluschow/kDrive/01 Eigene Programme/DeckPad/
```

```bash
# Starten
cd "/Users/johannesluschow/kDrive/01 Eigene Programme/DeckPad"
python3 app_main.py
```
