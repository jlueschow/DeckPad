"""
Globaler Log-Kanal für DeckPad — von überall importierbar.

Verwendung:
    from log_sink import log
    log("Ereignis: ...")

Das LogWindow in app/log_window.py verbindet sich mit emitter.message
und zeigt alle Nachrichten in Echtzeit an.
"""

from PySide6.QtCore import QObject, Signal, QDateTime


class _LogEmitter(QObject):
    message = Signal(str)


# Singleton — wird nach QApplication-Start instanziiert (Import läuft erst dann)
emitter = _LogEmitter()


def log(msg: str):
    """
    Thread-safe: sendet eine Log-Zeile mit Zeitstempel.
    Qt leitet das Signal automatisch in den Main-Thread (queued connection).
    """
    ts = QDateTime.currentDateTime().toString("hh:mm:ss.zzz")
    emitter.message.emit(f"[{ts}]  {msg}")
