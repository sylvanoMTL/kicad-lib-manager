# CLAUDE.md

## Collection Overview
This private repository is a KiCad library collection. It gathers the owner's own parts and open-source libraries through git submodules and holds no application code. The library manager app (part importer, library table generator, migration to the atomic scheme) lives in the public repository `sylvanoMTL/kicad-lib-manager`; it works on a folder like this one, so this folder is what the app calls the library folder.

## Repository Structure
- `Custom/` — submodule: `sylvanoMTL/kicad_custom_library` (personal parts)
  - `Symbols/` — the `Atomic_<stem>.kicad_sym` libraries
  - `Footprints/Atomic_Footprints.pretty` — every footprint of the own parts
  - `3DModels/` — the 3D model files, one per part, named `<MPN>.<ext>`
- `WurthElektronik/KiCad-Library/` — submodule: open-source Wurth Elektronik library
- `downloaded_examples/` — vendor downloads kept on this machine only (licence-restricted, ignored by git)
- `README.md`, `CLAUDE.md`, `.gitmodules`, `.gitignore` — the only files the collection tracks itself

## KiCad Path Variables
These must be set in KiCad: Preferences > Configure Paths:
- `KICAD_LIB_GITHUB` — points to this folder (the collection root); the generated library tables write every URI as `${KICAD_LIB_GITHUB}/...`
- `CUSTOM_3DMODEL_DIR` — points to `Custom/3DModels/` for the custom 3D model files
- `WE_3DMODEL_DIR` — used by the WurthElektronik footprints (set by their library)

The concrete folders on a given machine are not written in this file; they differ per checkout.

## Library Naming Convention
Own symbol libraries are named `Atomic_<official KiCad symbol library stem>`
(examples: `Atomic_Connector`, `Atomic_Battery_Management`, `Atomic_Transistor_FET`,
`Atomic_Oscillator`), filed by what the device is — never by manufacturer. Every
footprint lives in the one shared `Custom/Footprints/Atomic_Footprints.pretty` (or the
part links an official KiCad footprint instead), so symbol and footprint libraries no
longer pair by name.

Every part in an `Atomic_` library must pass the atomic rule:
- `MPN` and `Manufacturer` fields are set
- `Footprint` resolves to exactly one `Lib:FP`
- `Value` = `MPN`
- `Datasheet` is set (not empty or `~`)
- `Description` is set
- its 3D model file exists

Symbol name = sanitised MPN. 3D models live in `Custom/3DModels/` named `<MPN>.<ext>`
and are linked as `${CUSTOM_3DMODEL_DIR}/<file>`.

## Importing Parts
File > Import Part... (`Ctrl+I`) in the library manager app (`sylvanoMTL/kicad-lib-manager`) is the way in for Ultra Librarian, SnapEDA, SamacSys and loose files — it extracts the package, places the symbol, footprint and 3D model, and rewrites names and paths to the atomic scheme before any write.

Manual route (rare — when the importer can't be used):
1. Move the `.kicad_mod` into `Atomic_Footprints.pretty`
2. Add the symbol to the matching `Atomic_<stem>` library via KiCad Symbol Editor
   (copy/paste), with fields filled per the atomic rule above
3. Fix 3D model paths to use `${CUSTOM_3DMODEL_DIR}/<filename>.step`
4. Commit in the Custom submodule first, then update the parent repo

## Adding a New Library Submodule
```
git submodule add <repo-url> <VendorName>/<LibName>
```
Then run the library manager app on this folder to scan and generate the updated library tables.

## Git Workflow
- Always commit submodule changes separately (cd into the submodule, commit, push, then update the parent gitlink)
- Use descriptive commit messages with component category context
- The generated `sym-lib-table` and `fp-lib-table` are machine-specific and not committed (`.gitignore` excludes them, with `env/`, `venv/`, `.venv/` and `__pycache__/`)
- Vendor downloads under `downloaded_examples/` stay local: they are ignored and never committed
