"""The refreshing state over the library trees: a spinning wheel, a line of text, a bar and a file count.

Shown by the main window while it reads a library source again after a catalog Add, Reinstall, Update or Remove
(Phase 17 plan 23, owner finding 2 of 17-17, D-18). The text is plain, never markup; the wheel turns only while the
overlay is shown.
"""

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from .theme import ACCENT, BORDER, HEADING_PT, MUTED, SP_MD, SP_SM, SURFACE

REFRESH_TEXT = "Refreshing the library list after {verb} {name}. Large libraries can take a minute."
COUNT_TEXT = "{done} of {total} files"
VERBS = {"add": "adding", "reinstall": "reinstalling", "update": "updating", "remove": "removing"}
WHEEL_SIZE = 112
_BAR_WIDTH = 320
_TEXT_WIDTH = 520
_TRACK = 12  # width of the ring and of the arc, in pixels
_ARC_DEGREES = 300
_OVERLAY_ALPHA = 235
_TICK_MS = 40  # one step every 40 ms ...
_STEP_DEGREES = 12  # ... of 12 degrees: a full turn in 30 steps, about 1.2 s


class SpinnerWheel(QWidget):
    """A thick arc on a ring, turned by a timer that runs only while the wheel is shown.

    The timer starts in showEvent and stops in hideEvent (which a hidden or closed parent window also sends), so
    nothing a timer starts outlives the window (UI-SPEC close rule).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(WHEEL_SIZE, WHEEL_SIZE)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._advance)

    def angle(self) -> int:
        """Where the arc starts, in degrees (0 to 359)."""
        return self._angle

    def is_spinning(self) -> bool:
        return self._timer.isActive()

    def _advance(self):
        self._angle = (self._angle + _STEP_DEGREES) % 360
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        self._timer.start()

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = _TRACK / 2 + 1
        box = self.rect().adjusted(int(inset), int(inset), -int(inset), -int(inset))
        ring = QPen(QColor(BORDER), _TRACK)
        painter.setPen(ring)
        painter.drawEllipse(box)
        arc = QPen(QColor(ACCENT), _TRACK)
        arc.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc)
        # Qt counts angles in sixteenths of a degree, counter-clockwise; a negative span turns clockwise
        painter.drawArc(box, (90 - self._angle) * 16, -_ARC_DEGREES * 16)
        painter.end()


class RefreshOverlay(QWidget):
    """Covers its parent while the main window reads a library source again."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self._parent = parent
        self.setAccessibleName("Refreshing the library list")
        self.wheel = SpinnerWheel()
        self._label = QLabel()
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setMaximumWidth(_TEXT_WIDTH)
        font = self._label.font()
        font.setPointSize(HEADING_PT)
        font.setBold(True)
        self._label.setFont(font)
        self._bar = QProgressBar()
        self._bar.setFixedWidth(_BAR_WIDTH)
        self._bar.setTextVisible(False)
        self._bar.setAccessibleName("Progress of refreshing the library list")
        self._bar.setRange(0, 0)
        self._count = QLabel()
        self._count.setTextFormat(Qt.TextFormat.PlainText)
        self._count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._count.setStyleSheet(f"color: {MUTED};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SP_MD, SP_MD, SP_MD, SP_MD)
        layout.setSpacing(SP_SM)
        layout.addStretch(1)
        layout.addWidget(self.wheel, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._label, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._bar, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._count, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        parent.installEventFilter(self)
        self.hide()

    # -- what the owner sees ---------------------------------------------------------------------

    def text(self) -> str:
        return self._label.text()

    def count_text(self) -> str:
        return self._count.text()

    def bar_value(self) -> int:
        return self._bar.value()

    def bar_maximum(self) -> int:
        return self._bar.maximum()

    def is_indeterminate(self) -> bool:
        return self._bar.minimum() == 0 and self._bar.maximum() == 0

    # -- the three calls of the main window ------------------------------------------------------

    def show_for(self, kind: str, name: str):
        """Cover the parent for a change of kind (add, reinstall, update or remove) to the library called name."""
        self._label.setText(REFRESH_TEXT.format(verb=VERBS.get(kind, "changing"), name=name))
        self._set_indeterminate()
        self.setGeometry(self._parent.rect())
        self.show()
        self.raise_()

    def set_progress(self, done: int, total: int):
        """The files read so far; before the first count (or with no files) the bar only moves."""
        if total <= 0:
            self._set_indeterminate()
            return
        done = max(0, min(done, total))
        self._bar.setRange(0, 100)
        self._bar.setValue(done * 100 // total)
        self._count.setText(COUNT_TEXT.format(done=f"{done:,}", total=f"{total:,}"))

    def finish(self):
        """Uncover the parent."""
        self.hide()

    def _set_indeterminate(self):
        self._bar.setRange(0, 0)
        self._count.setText("")

    # -- following the parent --------------------------------------------------------------------

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._parent and event.type() == QEvent.Type.Resize and not self.isHidden():
            self.setGeometry(self._parent.rect())
        return False

    def paintEvent(self, event):
        painter = QPainter(self)
        colour = QColor(SURFACE)
        colour.setAlpha(_OVERLAY_ALPHA)
        painter.fillRect(self.rect(), colour)
        painter.end()
