"""Child process for tests/test_dialog_geometry.py (a plain script, not a test module).

QT_SCALE_FACTOR must be set before the QApplication exists, so the 175 percent run is a separate process.
Usage: dialoggeometrychild.py WORKDIR. It builds every dialog case, shows it offscreen, settles it and prints one
ASCII JSON line per case; it exits 0 when every case was measured and 3 when a check did not answer in time.
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

import geometryfixtures as gf  # noqa: E402


CASES = (
    "nc-setup", "nc-choose", "nc-issues",
    "choose-main",
    "choose-setup",
    "choose-failure",
)


def measure(case: str, dialog, settled: bool) -> dict:
    """One JSON-able record: the scale, the overlaps, the clipped labels and the missing height."""
    record = {"case": case, "dpr": dialog.devicePixelRatioF()}
    if not settled:
        record["timeout"] = True
        return record
    record["overlaps"] = gf.overlapping_children(dialog)
    record["clipped"] = gf.clipped_wrapped_labels(dialog)
    record["missing_height"] = gf.missing_height(dialog)
    record["height"] = dialog.height()
    if hasattr(dialog, "_preview"):
        record["preview_bottom"] = dialog._preview.geometry().bottom()
        record["footnote_top"] = dialog._footnote.geometry().top()
    labels = dialog._issue_labels() if hasattr(dialog, "_issue_labels") else dialog._row_labels()
    record["rows"] = [[label.height(), label.heightForWidth(label.width())] for label in labels]
    return record


def main() -> int:
    work = Path(sys.argv[1])
    app = QApplication(sys.argv[:1])

    def pump():
        app.processEvents()
        time.sleep(0.01)

    assert CASES == gf.ALL_CASES  # the cases the test expects are the cases this script builds
    status = 0
    for case in CASES:
        if case.startswith("nc-"):
            dialog = gf.new_collection_case(case, work / case)
            dialog.show()
            settled = gf.settle_new_collection(dialog, pump)
        else:
            dialog = gf.choose_case(case, work / case)
            dialog.show()
            settled = gf.settle_choose(dialog, pump)
        for _ in range(5):
            pump()
        print(json.dumps(measure(case, dialog, settled)), flush=True)
        if not settled:
            status = 3
        dialog.close()
        dialog.deleteLater()
        app.processEvents()
    return status


if __name__ == "__main__":
    sys.exit(main())
