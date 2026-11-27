# KiCad Library Manager

A PySide6 app that manages a KiCad library collection: it imports vendor parts (Ultra Librarian, SnapEDA, SamacSys and loose files), generates the library tables, checks the atomic rule and pins your libraries in KiCad.
It works on a collection folder you choose and ships no libraries.

## Install

Windows 11 is the main platform. You need standard CPython 3.14 from python.org (not the MSYS2 Python, because PySide6 does not run on it).

```powershell
git clone https://github.com/sylvanoMTL/kicad-lib-manager.git
cd kicad-lib-manager
py -3.14 -m venv env
.\env\Scripts\python.exe -m pip install -r requirements.txt
```

Start the app:

```powershell
.\env\Scripts\python.exe kicad_lib_manager.py
```

## First run

The app works on one library collection: a folder that holds `Custom/` with `Symbols/` or `Footprints/` in it. Library tables, imported parts and 3D models all live in that folder.

When the app finds no usable folder it opens the **Set Up Your Library Folder** window before the main window. It offers four buttons:

- **Use KiCad's Folder** takes the folder KiCad's `KICAD_LIB_GITHUB` path variable names.
- **Open Library Collection...** picks a collection folder you already have.
- **New Library Collection...** creates an empty collection.
- **Quit** closes the app and saves nothing.

KiCad finds the libraries through two path variables (KiCad > Preferences > Configure Paths):

- `KICAD_LIB_GITHUB` points to the collection folder.
- `CUSTOM_3DMODEL_DIR` points to `Custom/3DModels/` inside it.

After you switch to another folder the app asks `Change KiCad path variables?`. No is the default, and nothing is written to KiCad without Yes. When you say Yes, restart KiCad so that all your projects use the libraries in the new folder.

## Choosing or creating a collection

- **Open Library Collection...** (File menu) opens a folder that is a collection. **Change Folder...** next to the folder path above the toolbar runs the same window.
- **New Library Collection...** (File menu) asks for a parent folder and a name and creates `<Name>/Custom/` with `Symbols/`, `Footprints/Atomic_Footprints.pretty/`, `3DModels/`, a `.gitignore` and a `README.md`. `Custom` is its own git repository on branch `main`, and nothing is committed for you.
- **Use KiCad's Folder** and **Recent Library Collections** switch to a folder in one step. **Show Library Folder in Explorer** opens it.

At start the app takes the first of these that passes the folder check: `--library-root`, `KICAD_LIBMGR_ROOT`, the folder you chose last time, KiCad's `KICAD_LIB_GITHUB`. When none does, the first-run window opens.

## Development

Install the test dependencies into the virtual environment you run the tests from:

```powershell
.\env\Scripts\python.exe -m pip install -r requirements-dev.txt
```

```powershell
.\env\Scripts\python.exe -m pytest          # quick parallel run, skips the slow tests
.\env\Scripts\python.exe -m pytest --full   # full run, includes the slow tests
.\env\Scripts\python.exe -m pytest -n 0     # serial run, for --pdb, -s and breakpoint()
```

The suite needs no collection: the tests build their own scratch collections. The corpus tests run only when `KICAD_TEST_CORPUS` names a collection folder; otherwise they are deselected and the run reports the count.

To point the app at a scratch or another collection, use `--library-root PATH` or the `KICAD_LIBMGR_ROOT` environment variable. When both are set, the command line wins.

```powershell
.\env\Scripts\python.exe kicad_lib_manager.py --library-root <folder>
```

To keep the app's settings, saved scans, backups and KiCad's settings out of your real ones for a trial, add `--scratch-root PATH` (or set `KICAD_LIBMGR_SCRATCH_ROOT`; the command line wins). The folder must exist and be writable, a bad value stops the start with exit code 2, and the first log line names the folder.

Enable the repository hooks once per clone with `git config core.hooksPath .githooks`. See `CLAUDE.md` for the developer guide and `tests/README.md` for markers, timeouts and the isolation rules.

## Libraries and licences

This tool ships no libraries. The libraries you add to a collection keep their own licences: KiCad's official libraries are CC-BY-SA, and Würth Elektronik's library has its own terms. The test fixtures in this repository are synthetic, built by the tests themselves, not copied from any vendor.

Third-party libraries, such as those of Würth Elektronik or SparkFun, are added with **File > Library Catalog...** (`Ctrl+Shift+L`). The catalog downloads a public GitHub repository into `ThirdParty/` of your collection and records it in `catalog.json` there. The catalog also lists the libraries of KiCad's add-on list, reviewed by the KiCad team: it reads that list live, keeps the last copy for offline use (marked with its date), and falls back to its own list when it has none. A library of that list gets the names KiCad gives add-on libraries (`PCM_` in front) unless its own links use its own names; a library that cannot be added yet says why. Each library keeps its own licence: the catalog shows it before you add the library and never changes it. The app does not commit `catalog.json` for you, and KiCad's own Plugin and Content Manager is left alone. Downloading needs Git 2.32 or newer.

## Licence

MIT, see the `LICENSE` file. It covers the code of this repository only, not any library you manage with it.
