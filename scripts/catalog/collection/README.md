# KiCad Libraries

A private collection of KiCad libraries: the owner's own parts in `Custom/` and third-party libraries downloaded through the library manager app. The collection holds no application code. The library manager app that imports parts, manages the third-party libraries and generates the KiCad library tables lives in its own public repository, [`sylvanoMTL/kicad-lib-manager`](https://github.com/sylvanoMTL/kicad-lib-manager).

## Contents

```
KiCad_Libraries/
├── Custom/                       ← Own parts (submodule: kicad_custom_library)
│   ├── Symbols/                  ← Atomic_<stem>.kicad_sym libraries
│   ├── Footprints/
│   │   └── Atomic_Footprints.pretty
│   └── 3DModels/                 ← <MPN>.<ext> model files
├── ThirdParty/                   ← Third-party libraries, one folder per library (not tracked by git)
│   └── WurthElektronik/          ← Wurth Elektronik library
├── catalog.json                  ← The list of the third-party libraries (written by the app)
├── README.md
└── CLAUDE.md
```

`Custom` is the only submodule. Everything in `ThirdParty/` is a plain download that the app's Library Catalog manages and records in `catalog.json`; git ignores the folder itself. `sym-lib-table` and `fp-lib-table` are generated on each machine and are not committed. Vendor downloads kept for reference live in `downloaded_examples/`, which git ignores.

## Setup

Clone the collection, then fetch `Custom`:

```bash
git clone <url of this repository>
cd <the cloned folder>
git submodule update --init -- Custom
```

`Custom` is a separate repository, so fetching it needs access to it. The third-party libraries do not come with the clone: open the library manager on the folder, choose **File > Library Catalog...** (`Ctrl+Shift+L`) and reinstall the libraries it lists with **Problem: folder missing**.

## KiCad configuration

In KiCad open **Preferences > Configure Paths** and add:

| Name | Path |
|------|------|
| `KICAD_LIB_GITHUB` | the folder you cloned this collection into |
| `CUSTOM_3DMODEL_DIR` | `Custom/3DModels/` inside that folder |

`WE_3DMODEL_DIR` is used by the Wurth Elektronik footprints. The Library Catalog sets it for you: when you add or reinstall the library it asks to set the variable to a folder inside `ThirdParty/WurthElektronik/`.

Then make KiCad read the libraries: the library manager app generates `sym-lib-table` and `fp-lib-table` for the folder, or you add the libraries by hand under **Preferences > Manage Symbol Libraries** and **Manage Footprint Libraries**. Restart KiCad after changing a path variable.

## Working with the library manager

The app in [`sylvanoMTL/kicad-lib-manager`](https://github.com/sylvanoMTL/kicad-lib-manager) works on this folder:

- **Import Part...** takes a package from Ultra Librarian, SnapEDA, SamacSys or loose files and places the symbol, footprint and 3D model in `Custom/`, named by the atomic scheme.
- **Library Catalog...** downloads, updates and removes the third-party libraries in `ThirdParty/` and keeps `catalog.json` current.
- **Generate Tables** writes the KiCad library tables for the libraries you select.
- **Commit** records an imported part in the `Custom` submodule after you confirm.

Start the app with `--library-root <this folder>` or let it find the folder through `KICAD_LIB_GITHUB`. Commit in `Custom` first, push it, then commit the updated gitlink here. The app writes `catalog.json` but never commits it: commit it here by hand after you add or remove a third-party library.

## Third-party libraries

Each library lives in its own folder `ThirdParty/<name>/`, a plain copy of the library's public repository at the version recorded in `catalog.json`. Use the Library Catalog to add, update or remove one; do not edit the files inside, because an update replaces them. On another computer the catalog shows **Problem: folder missing** for a library that is listed in `catalog.json` but not downloaded yet, and **Reinstall** downloads it again.

## Naming and the atomic rule

Own symbol libraries are `Atomic_<official KiCad symbol library stem>` (for example `Atomic_Connector`), filed by what the device is. Every footprint of the own parts is in `Custom/Footprints/Atomic_Footprints.pretty`. The libraries in `ThirdParty/` keep their own names and are not held to the atomic rule.

A part in an `Atomic_` library passes the atomic rule when:

- `MPN` and `Manufacturer` are set;
- `Footprint` resolves to exactly one `Lib:FP`;
- `Value` equals `MPN`;
- `Datasheet` and `Description` are set;
- its 3D model `Custom/3DModels/<MPN>.<ext>` exists, linked as `${CUSTOM_3DMODEL_DIR}/<file>`.

`CLAUDE.md` holds the full convention and the manual import route.

## Licences

Each third-party library keeps its own licence: the Wurth Elektronik library is under Wurth's own terms, which you find in its folder in `ThirdParty/WurthElektronik/`, and the app asks you to confirm a library's licence before it downloads it. `Custom` holds the owner's own parts. Vendor downloads under `downloaded_examples/` stay on the machine that fetched them.
