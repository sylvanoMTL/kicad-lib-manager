# KiCad Libraries

A private collection of KiCad libraries: the owner's own parts and open-source libraries, gathered with git submodules. The collection holds no application code. The library manager app that imports parts and generates the KiCad library tables lives in its own public repository, [`sylvanoMTL/kicad-lib-manager`](https://github.com/sylvanoMTL/kicad-lib-manager).

## Contents

```
KiCad_Libraries/
├── Custom/                       ← Own parts (submodule: kicad_custom_library)
│   ├── Symbols/                  ← Atomic_<stem>.kicad_sym libraries
│   ├── Footprints/
│   │   └── Atomic_Footprints.pretty
│   └── 3DModels/                 ← <MPN>.<ext> model files
├── WurthElektronik/
│   └── KiCad-Library/            ← Wurth Elektronik library (submodule)
├── README.md
└── CLAUDE.md
```

`sym-lib-table` and `fp-lib-table` are generated on each machine and are not committed. Vendor downloads kept for reference live in `downloaded_examples/`, which git ignores.

## Setup

Clone the collection with its submodules:

```bash
git clone --recurse-submodules <url of this repository>
```

If you already cloned without `--recurse-submodules`:

```bash
git submodule update --init --recursive
```

`Custom` and the other libraries are separate repositories, so fetching them needs access to each one.

## KiCad configuration

In KiCad open **Preferences > Configure Paths** and add:

| Name | Path |
|------|------|
| `KICAD_LIB_GITHUB` | the folder you cloned this collection into |
| `CUSTOM_3DMODEL_DIR` | `Custom/3DModels/` inside that folder |

`WE_3DMODEL_DIR` is used by the Wurth Elektronik footprints and is set by their library.

Then make KiCad read the libraries: the library manager app generates `sym-lib-table` and `fp-lib-table` for the folder, or you add the libraries by hand under **Preferences > Manage Symbol Libraries** and **Manage Footprint Libraries**. Restart KiCad after changing a path variable.

## Working with the library manager

The app in [`sylvanoMTL/kicad-lib-manager`](https://github.com/sylvanoMTL/kicad-lib-manager) works on this folder:

- **Import Part...** takes a package from Ultra Librarian, SnapEDA, SamacSys or loose files and places the symbol, footprint and 3D model in `Custom/`, named by the atomic scheme.
- **Generate Tables** writes the KiCad library tables for the libraries you select.
- **Commit** records an imported part in the `Custom` submodule after you confirm.

Start the app with `--library-root <this folder>` or let it find the folder through `KICAD_LIB_GITHUB`. Commit in `Custom` first, push it, then commit the updated gitlink here.

## Naming and the atomic rule

Own symbol libraries are `Atomic_<official KiCad symbol library stem>` (for example `Atomic_Connector`), filed by what the device is. Every footprint of the own parts is in `Custom/Footprints/Atomic_Footprints.pretty`.

A part in an `Atomic_` library passes the atomic rule when:

- `MPN` and `Manufacturer` are set;
- `Footprint` resolves to exactly one `Lib:FP`;
- `Value` equals `MPN`;
- `Datasheet` and `Description` are set;
- its 3D model `Custom/3DModels/<MPN>.<ext>` exists, linked as `${CUSTOM_3DMODEL_DIR}/<file>`.

`CLAUDE.md` holds the full convention and the manual import route.

## Updating submodules

Pull the latest changes from all upstream libraries:

```bash
git submodule update --remote --merge
```

Add a library with `git submodule add <repo-url> <VendorName>/<LibName>`.

## Licences

Each third-party library keeps its own licence: the Wurth Elektronik library is under Wurth's own terms, which you find in that submodule. `Custom` holds the owner's own parts. Vendor downloads under `downloaded_examples/` stay on the machine that fetched them.
