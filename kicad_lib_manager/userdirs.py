"""The scratch folder for owner checks (Phase 17, D-35): one folder that holds the app's own user state.

While a scratch folder is set, the app's settings (PATH/settings), its backups (PATH/backups) and the folder it
reads and writes KiCad's settings in (PATH/kicad) are all under it, so a rehearsal never touches the real ones.
Qt-free and imports nothing of the package, so fsutil and library_scanner can use it.
"""

from pathlib import Path

SETTINGS_FOLDER = "settings"
BACKUPS_FOLDER = "backups"
KICAD_FOLDER = "kicad"

_scratch_root: Path | None = None


def set_scratch_root(folder: Path | None) -> None:
    """Set the scratch folder, or None to go back to the real user folders."""
    global _scratch_root
    _scratch_root = None if folder is None else Path(folder)


def scratch_root() -> Path | None:
    """The scratch folder while the switch is set, else None."""
    return _scratch_root


def settings_base() -> Path | None:
    """Where the settings ini goes (PATH/settings) while the switch is set."""
    return None if _scratch_root is None else _scratch_root / SETTINGS_FOLDER


def kicad_config_base() -> Path | None:
    """The folder that holds KiCad's version folders (PATH/kicad) while the switch is set."""
    return None if _scratch_root is None else _scratch_root / KICAD_FOLDER


def backup_base() -> Path | None:
    """The folder of the app's backups (PATH/backups) while the switch is set."""
    return None if _scratch_root is None else _scratch_root / BACKUPS_FOLDER
