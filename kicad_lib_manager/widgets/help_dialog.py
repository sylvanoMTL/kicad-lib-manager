import html
import re
from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QSplitter, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QTextBrowser,
    QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)
from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPalette

from ..settings import load_help_topic, save_help_topic
from .import_dialog import (
    ADD_MODEL_TEXT, CHANGE_PACKAGE_TEXT, FINISHING_TEXT, HELP_ACTION_TEXT, OFFICIAL_FOOTPRINT_TEXT,
    REMOVE_MODEL_TEXT, VENDOR_FOOTPRINT_TEXT, fit_window,
)
from .migration_dialog import (
    BROWSE_TEXT, CHOOSER_TEXT, DESTINATION_LABEL, FILES_TAB_TEXT, GENERATE_TEXT, GUESS_MARK, LEFTOVERS_TEXT,
    MOVE_FOOTPRINT_TEXT, OPEN_MAP_TEXT, RUN_TEXT, SUGGESTED_MARK,
)
from .theme import (
    ACCENT, AMBER, AMBER_TINT, BORDER, DISPLAY_PT, HEADING_PT, LINK, MONO_FAMILY, MONO_PT,
    SP_MD, SP_SM, SP_XS, SURFACE, SURFACE_BASE, SURFACE_HEADER,
)

# Every colour, size and gap comes from theme.py (UI-01); the body takes the application font and palette
CSS = "\n".join([
    f'body {{ font-family: "Segoe UI", Arial, sans-serif; margin: {SP_MD}px {SP_MD}px {SP_MD}px {SP_MD}px; '
    "line-height: 1.55; }",
    f"h2 {{ color: {LINK}; border-bottom: 2px solid {ACCENT}; padding-bottom: {SP_XS}px; "
    f"margin-top: {SP_SM}px; font-size: {DISPLAY_PT}pt; }}",
    f"h3 {{ margin-top: {SP_MD}px; font-size: {HEADING_PT}pt; }}",
    f"code {{ background: {SURFACE_HEADER}; padding: 0px {SP_XS}px; font-family: {MONO_FAMILY}; "
    f"font-size: {MONO_PT}pt; }}",
    f"pre {{ background: {SURFACE}; border-left: 3px solid {ACCENT}; padding: {SP_SM}px {SP_MD}px; "
    f"font-family: {MONO_FAMILY}; font-size: {MONO_PT}pt; }}",
    f"ul, ol {{ margin-left: {SP_SM}px; }}",
    f"li {{ margin-bottom: {SP_XS}px; }}",
    f"table {{ border-collapse: collapse; margin: {SP_SM}px 0px; }}",
    f"th, td {{ border: 1px solid {BORDER}; padding: {SP_XS}px {SP_SM}px; text-align: left; }}",
    f"th {{ background: {SURFACE_HEADER}; }}",
    f"a {{ color: {ACCENT}; }}",
    f".hint {{ background: {AMBER_TINT}; border-left: 3px solid {AMBER}; padding: {SP_SM}px {SP_MD}px; "
    f"margin: {SP_SM}px 0px; }}",
])


# In the Windows 11 style a selected row (a faint fill and a thin bar at the far left) looks like a row under the
# mouse. The row painter only paints inside the row's cell, so the expand arrows and the indentation stay with the
# tree and the style. The menu has no stylesheet, because Qt's stylesheet engine can redraw those.
class _MenuSelectionDelegate(QStyledItemDelegate):
    """Draws the selected menu row in the accent colour with white text, so it cannot be mistaken for a row under the mouse."""

    def paint(self, painter, option, index):
        if not option.state & QStyle.StateFlag.State_Selected:
            super().paint(painter, option, index)
            return
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        painter.fillRect(opt.rect, QColor(ACCENT))
        opt.state &= ~QStyle.StateFlag.State_Selected
        opt.state &= ~QStyle.StateFlag.State_MouseOver
        opt.palette.setColor(QPalette.ColorRole.Text, QColor(SURFACE_BASE))
        opt.widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)


def _wrap(body: str) -> str:
    return f"<html><head><style>{CSS}</style></head><body>{body}</body></html>"


# ── Help pages ────────────────────────────────────────────────────────

HELP_PAGES: dict[str, str] = {}

HELP_PAGES["overview"] = _wrap(
    "<h2>Overview</h2>"
    "<p>KiCad uses <b>sym-lib-table</b> and <b>fp-lib-table</b> files to locate "
    "symbol and footprint libraries. When you maintain custom parts alongside "
    "third-party libraries (e.g.&nbsp;W&uuml;rth Elektronik), keeping those "
    "tables in sync manually is tedious and error-prone.</p>"
    "<p><b>KiCad External Lib Manager</b> automates the process:</p>"
    "<ul>"
    "<li>Scans your repository and discovers every library automatically</li>"
    "<li>Cross-references symbol&rarr;footprint links to detect broken references</li>"
    "<li>Checks 3D model paths for common issues</li>"
    "<li>Generates the table files in one click, with automatic backups</li>"
    "</ul>"
    "<p>No library paths are hard-coded &mdash; everything is discovered dynamically "
    "from the repository structure.</p>"
)

HELP_PAGES["requirements"] = _wrap(
    "<h2>Requirements</h2>"
    "<ul>"
    "<li><b>Python 3.10</b> or newer</li>"
    "<li><b>PySide6</b> &mdash; install with: <code>pip install PySide6</code></li>"
    "</ul>"
    '<p class="hint"><b>Tip:</b> Use a virtual environment to keep dependencies '
    "isolated:<br>"
    "<code>python -m venv env &amp;&amp; env\\Scripts\\activate &amp;&amp; "
    "pip install PySide6</code></p>"
)

HELP_PAGES["how_to_run"] = _wrap(
    "<h2>How to Run</h2>"
    "<p>From the repository root directory:</p>"
    "<pre>python kicad_lib_manager.py</pre>"
    "<p>The main window opens and immediately starts scanning the repository.</p>"
)

HELP_PAGES["library_folder"] = _wrap(
    "<h2>Library Folder</h2>"
    "<p>The app works on one <b>library folder</b>: the folder that holds your "
    "<code>Custom</code> libraries. It is shown in the <b>Library folder</b> row at the "
    "top of the main window, with a tag that says where it came from, and its name is "
    "in the window title.</p>"
    "<h3>Which folder is used at start</h3>"
    "<p>The app takes the first of these that passes the folder check:</p>"
    "<ol>"
    "<li><code>--library-root</code> on the command line (<code>set by --library-root</code>)</li>"
    "<li>the <code>KICAD_LIBMGR_ROOT</code> environment variable "
    "(<code>set by KICAD_LIBMGR_ROOT</code>)</li>"
    "<li>the folder you chose last time (<code>your choice</code>)</li>"
    "<li>the folder KiCad names in <code>KICAD_LIB_GITHUB</code> (<code>KiCad's folder</code>)</li>"
    "<li>otherwise the setup window opens</li>"
    "</ol>"
    "<p>A folder you chose earlier that has since been deleted is skipped, and the log "
    "says which folder is used instead. If <code>--library-root</code> or "
    "<code>KICAD_LIBMGR_ROOT</code> names a folder that cannot be used, the app does not "
    "start; it says why and stops, so it never works on the wrong folder by accident.</p>"
    "<h3>Changing the library folder</h3>"
    "<ul>"
    "<li><b>File &rarr; New Library Collection...</b> creates a new, empty collection and "
    "switches to it (see New Library Collection below).</li>"
    "<li><b>File &rarr; Open Library Collection...</b> (or the <b>Change Folder...</b> button "
    "in the row) opens a window with a Folder field and <b>Browse...</b>. Rows below it "
    "show whether the folder exists, whether you can write to it and whether it is a "
    "library collection. Only a folder that already holds a collection opens. An empty "
    "folder offers <b>New Library Collection...</b>, and any other folder is refused with "
    "a line that points to New Library Collection... A path of more than 100 characters "
    "gets a warning, because KiCad and git can fail on long Windows paths; the warning "
    "does not block.</li>"
    "<li><b>File &rarr; Use KiCad's Folder</b> switches to the folder KiCad reads. It is "
    "greyed out when KiCad names no folder or when you already use it.</li>"
    "<li><b>File &rarr; Recent Library Collections</b> lists up to 10 folders you used before "
    "that still exist, and also a folder the app started on through "
    "<code>--library-root</code> or <code>KICAD_LIBMGR_ROOT</code> (that folder is not saved "
    "as your choice). Pick one to switch to it with no window.</li>"
    "<li><b>File &rarr; Show Library Folder in Explorer</b> opens the folder. It works "
    "while a scan runs.</li>"
    "</ul>"
    "<p>A switch is refused, with a line in the log and the status bar, while a scan runs, "
    "while the import window or the migration window is open, or while KiCad's settings "
    "are being checked. Nothing is deleted by a switch. Every switch scans the new folder "
    "and starts the selection fresh; each folder keeps its own saved scan. The "
    "<b>Destination</b> box follows the new folder when it showed the previous library "
    "folder or was blank; a Destination elsewhere (such as a KiCad project folder) "
    "stays as it is.</p>"
    "<h3>The setup window</h3>"
    "<p>When no folder resolves, a <b>Set Up Your Library Folder</b> window opens before "
    "the main window, with these choices: <b>Use KiCad's Folder</b>, <b>Open Library "
    "Collection...</b> and <b>New Library Collection...</b>. <b>Quit</b>, the close box and "
    "<code>Esc</code> close the app without saving anything, and the window appears again "
    "at the next start.</p>"
    "<h3>New Library Collection</h3>"
    "<p><b>New Library Collection...</b> asks for a <b>Parent folder</b> and a <b>Name</b>, shows "
    "what it will create and creates nothing until you click <b>Create Collection</b>. It "
    "makes a folder with a <code>Custom</code> folder inside it: <code>Symbols</code>, "
    "<code>Footprints/Atomic_Footprints.pretty</code>, <code>3DModels</code>, a "
    ".gitignore and a README. <code>Custom</code> is its own git repository on branch main. "
    "Empty folders get a <code>.gitkeep</code> file so git keeps them. Nothing is "
    "committed for you: after your first import and commit, the skeleton files show as "
    "other changes that stay uncommitted until you commit them yourself. Git must be "
    "installed.</p>"
    "<h3>KiCad path variables after a switch</h3>"
    "<p>When KiCad's <code>KICAD_LIB_GITHUB</code> names another folder than the library "
    "folder, the row shows an amber <b>KiCad reads a different folder</b> tag. After a "
    "switch, and after Generate Tables or Install Part, the app asks whether to change "
    "KiCad's path variables, listing each old and new value. The question is "
    "separate from Install Part and Generate Tables: they do not need this change, and "
    "your answer does not undo anything they did. Yes makes all your KiCad projects use "
    "the libraries in that folder after KiCad restarts. <b>No is the default</b>; nothing "
    "is written without Yes.</p>"
    "<h3>For development and testing</h3>"
    "<p>Run with <code>--library-root &lt;folder&gt;</code> or set "
    "<code>KICAD_LIBMGR_ROOT</code> to work on another folder, for example a scratch "
    "collection, without touching your real one.</p>"
)

HELP_PAGES["kicad_detection"] = _wrap(
    "<h2>KiCad Detection</h2>"
    "<p>On startup the tool tries to <b>auto-detect</b> your KiCad installation "
    "to locate the default footprint libraries.</p>"
    "<h3>Why it matters</h3>"
    "<p>Many symbols reference KiCad's built-in footprints "
    "(e.g.&nbsp;<code>Resistor_SMD:R_0402_1005Metric</code>). Without knowing "
    "the install path, those perfectly valid references would show up as "
    "<b>false warnings</b>.</p>"
    "<h3>Auto-detection</h3>"
    "<p>The tool looks in standard locations:</p>"
    "<ul>"
    "<li><b>Windows:</b> <code>C:\\Program Files\\KiCad\\&lt;version&gt;"
    "\\share\\kicad\\footprints</code></li>"
    "<li><b>macOS:</b> <code>/Applications/KiCad/footprints</code></li>"
    "<li><b>Linux:</b> <code>/usr/share/kicad/footprints</code></li>"
    "</ul>"
    "<p>If multiple versions are installed, the latest is selected.</p>"
    "<h3>Manual selection</h3>"
    "<p>If auto-detection fails, a folder picker dialog appears. You can also "
    "change the path later via <b>File &rarr; Set KiCad Footprint Path</b> "
    "(<code>Ctrl+K</code>), which triggers a rescan.</p>"
)

HELP_PAGES["repo_scan"] = _wrap(
    "<h2>Repository Scan</h2>"
    "<p>After KiCad detection, the tool scans the entire repository:</p>"
    "<ol>"
    "<li><b>Footprint libraries</b> &mdash; every <code>.pretty</code> folder</li>"
    "<li><b>Symbol libraries</b> &mdash; every <code>.kicad_sym</code> file; each "
    "symbol's <code>Footprint</code> property is parsed to extract references</li>"
    "<li><b>Cross-reference</b> &mdash; each footprint reference is checked against "
    "both the repository and KiCad defaults. Missing links become warnings</li>"
    "<li><b>3D model check</b> &mdash; <code>.kicad_mod</code> files are scanned "
    "for absolute or broken model paths (paths should use "
    "<code>${VARIABLE}</code> notation)</li>"
    "</ol>"
    "<p>Results appear in the library tree. Warnings are logged in the bottom panel "
    "and flagged with an orange icon in the tree.</p>"
    "<p>Every scan is saved. At start the tool shows the last saved scan when no "
    "library file changed since it was saved, and the log says so. <b>Rescan</b> "
    "always runs the whole scan.</p>"
    "<p>While the libraries load, the <b>Loading Libraries</b> window shows a "
    "<b>Skip</b> button as soon as the scan starts reading a library source: first "
    "while the symbols are read, then while the 3D model paths are checked. It names "
    "that source, for example <b>Skip WurthElektronik</b>. Skip stops checking the "
    "3D model paths of that source only, now or when the check reaches them. The "
    "symbols are read in full whatever you press, so its libraries are still listed "
    "and its symbols' footprint links are still read, and Generate Tables keeps them. "
    "The log says which source was skipped. The scan is saved with that note, and the "
    "next start says so until a Rescan checks everything again.</p>"
)

HELP_PAGES["library_tree"] = _wrap(
    "<h2>Library Tree</h2>"
    "<p>The main area is split into two side-by-side panels:</p>"
    "<table>"
    "<tr><th>Left panel</th><th>Right panel</th></tr>"
    "<tr><td>Symbol libraries</td><td>Footprint libraries</td></tr>"
    "</table>"
    "<p>Each panel groups libraries by <b>source</b> (Custom, then each catalog library, "
    "for example WurthElektronik or SparkFun). Source headers are bold and collapsible.</p>"
    "<h3>Columns</h3>"
    "<ul>"
    "<li><b>Library Name</b> &mdash; the nickname used in the table file</li>"
    "<li><b>Source</b> &mdash; which top-level folder the library comes from</li>"
    "<li><b>Linked Footprints</b> (symbols only) &mdash; the footprint references "
    "found in the symbol file</li>"
    "<li><b>Status</b> &mdash; <i>OK</i>, <i>Missing FP</i> or <i>Collision</i> "
    "(same nickname as another library; only one can be selected)</li>"
    "</ul>"
    "<p>Libraries with missing footprint references are highlighted in "
    f"<span style='color:{AMBER};font-weight:bold'>amber</span>.</p>"
    "<h3>Atomic parts</h3>"
    "<p>Libraries whose name starts with <code>Atomic_</code> show one row for each part. "
    f"A part that breaks an atomic rule is shown in <span style='color:{AMBER};font-weight:bold'>"
    "amber</span> with a warning icon, and its Status counts the rules it breaks, "
    "for example <i>Changed &middot; 2 rules</i>. "
    "The library row counts the parts that fail, for example <i>1 of 3 fail</i>.</p>"
    "<p>Parts start collapsed. Expand a part to see one row for each problem, in "
    f"<span style='color:{AMBER};font-weight:bold'>amber</span> with a warning icon, and "
    "one row for each note, such as leftover price or stock data, in plain text with an "
    "information icon. The tooltip of the part lists the same lines.</p>"
    "<p>Parts added or edited since the last Custom commit are marked "
    f"<span style='color:{ACCENT};font-weight:bold'>New</span> or "
    f"<span style='color:{ACCENT};font-weight:bold'>Changed</span> in the Status column. "
    "This works for every library in Custom, not only the atomic ones.</p>"
    "<p>To fix a marked part, double-click the part or one of its problem rows, or press "
    "<code>Ctrl+Shift+A</code>. "
    "<b>Check Atomic Parts</b> lists every problem and offers the safe fixes as ticked rows. "
    "You can type in a missing datasheet or description, or pick a missing 3D model. "
    "You see the exact changes before anything is written, and the libraries are scanned "
    "again afterwards.</p>"
)

HELP_PAGES["selecting"] = _wrap(
    "<h2>Selecting Libraries</h2>"
    "<p>Checkboxes control which libraries are included when generating tables.</p>"
    "<ul>"
    "<li><b>Source group checkbox</b> &mdash; toggles all libraries in that source "
    "(tri-state: checked, unchecked, partial)</li>"
    "<li><b>Individual checkbox</b> &mdash; toggles a single library</li>"
    "<li><b>Select All / Deselect All</b> &mdash; toolbar buttons that affect "
    "everything</li>"
    "</ul>"
    "<h3>Right-click menu</h3>"
    "<p>Right-click on either tree for <b>Expand All</b> / <b>Collapse All</b>.</p>"
    '<p class="hint"><b>Note:</b> Footprint checkboxes are managed automatically '
    "by the footprint filter (see <i>Footprint Filter</i> section). You can still "
    "override them manually after the filter runs.</p>"
)

HELP_PAGES["generating"] = _wrap(
    "<h2>Generating Tables</h2>"
    "<ol>"
    "<li>Select the libraries you want to include</li>"
    "<li>Set the <b>Destination</b> folder (defaults to the repository root). At start the "
    "Destination box offers only folders that still exist</li>"
    "<li>Click <b>Generate Tables</b> (blue button) or press <code>Ctrl+G</code></li>"
    "</ol>"
    "<h3>What happens</h3>"
    "<ul>"
    "<li>Existing <code>sym-lib-table</code> and <code>fp-lib-table</code> are "
    "automatically backed up (e.g.&nbsp;<code>sym-lib-table_backup_1</code>)</li>"
    "<li>New table files are written with only the selected libraries</li>"
    "<li>Backup numbers increment automatically "
    "(<code>_backup_1</code>, <code>_backup_2</code>, ...)</li>"
    "<li>If <code>KICAD_LIB_GITHUB</code> or <code>CUSTOM_3DMODEL_DIR</code> in KiCad's "
    "settings needs to change, the app first checks whether KiCad is open, then shows the "
    "old and new values and asks. When KiCad is open, the question names the open KiCad "
    "programs and offers <b>Retry</b> (close KiCad first, then press it), "
    "<b>Change anyway</b> or <b>Not now</b>. After you answer, the app reads KiCad's "
    "settings again and changes only these two paths, so anything KiCad saved in the "
    "meantime is kept. Answering No or <b>Not now</b> leaves KiCad's settings unchanged "
    "while the tables are still written. "
    "When the library folder is a git worktree the app never changes them, and the log "
    "says why. When <code>KICAD_LIB_GITHUB</code> names another folder, the change is "
    "offered the same way, with No as the default</li>"
    "<li>With an empty Destination box nothing is written, and the log says so</li>"
    "<li>When KiCad reads its libraries from a different folder than this one "
    "(<code>KICAD_LIB_GITHUB</code>), an amber notice above the library tree names "
    "both folders. The tables are still written; nothing is blocked. KiCad will see "
    "them once they exist in the folder it reads: switch with <b>File &rarr; Use "
    "KiCad's Folder</b>, or let the app point KiCad at this folder when Generate "
    "Tables offers to. The notice stays until the next Generate, can be dismissed, "
    "and clears by itself once the two folders match</li>"
    "</ul>"
    "<p>The log panel at the bottom confirms what was written.</p>"
    "<h3>Pin Atomic libraries in KiCad</h3>"
    "<p><b>File &rarr; " + CHOOSER_TEXT + "</b> (<code>Ctrl+Shift+K</code>) pins every "
    "<code>Atomic_</code> library listed in the tables of the Destination folder, and "
    "<code>Atomic_Footprints</code>, at the top of KiCad's library lists (KiCad's Symbol "
    "Chooser and Footprint Chooser). A pin you "
    "added yourself is kept, and a pin of an <code>Atomic_</code> library that no longer "
    "exists is removed. The Symbol Chooser's <b>MPN</b> and <b>Manufacturer</b> columns are "
    "shown right after Description, and the old Manufacturer column some KiCad versions show "
    "on its own is removed.</p>"
    "<p>The app shows every old and new value first and asks before changing anything, and "
    "backs up KiCad's settings the same way as the path variables above. When KiCad is open "
    "it offers <b>Retry</b> (close KiCad first, then press it), <b>Change anyway</b> or "
    "<b>Not now</b>, the same choice as the path-variable change. It never runs on a "
    "library folder that is a git worktree or that is not the folder your KiCad settings "
    "point at, and changes nothing when they are already pinned.</p>"
)

HELP_PAGES["importing"] = _wrap(
    "<h2>Importing Parts</h2>"
    "<p>Import a vendor package (Ultra Librarian, SnapEDA, SamacSys) into a "
    "<code>Custom/</code> library without editing any KiCad file by hand.</p>"
    "<h3>Start</h3>"
    "<p>Open <b>File &rarr; Import Part...</b> (<code>Ctrl+I</code>) or click the "
    "<b>Import Part...</b> toolbar button. You can also drop one <b>.zip</b> file or "
    "one <b>folder</b> onto the main window; the dialog then opens with that package "
    "loaded. The newest zip in your Downloads folder is offered, but it is never "
    "opened by itself.</p>"
    "<p><b>Cancel</b>, next to <b>Browse zip...</b> and <b>Browse folder...</b>, closes the import window "
    "without importing anything, and nothing is written. On the editing step <b>Cancel</b> sits at the "
    "bottom right, to the right of <b>Install Part</b>.</p>"
    "<p>The import window opens small for this step and grows to show the part once a package is open. "
    "It is sized to fit your screen and stays above the taskbar.</p>"
    "<p>Once a package is open, the button <b>" + CHANGE_PACKAGE_TEXT + "</b> at the top right "
    "closes it and goes back to this start step so you can pick another package. "
    "Your edits to the open package are dropped and nothing has been written.</p>"
    "<p>The import window has <b>" + HELP_ACTION_TEXT + "</b> at the top right at every step: on its toolbar "
    "while you choose a package and edit the part, and at the right end of the result line after the install. "
    "Click it, or press <code>F1</code>, at every step (choosing a package, editing the part, the result) to "
    "open this page of the User Guide. The User Guide is its own window. It stays open beside the main window and the "
    "import window, so you can use either one while you read it, and it stays open when the import "
    "window closes.</p>"
    "<h3>Items</h3>"
    "<p>Pick the symbol, one footprint and the 3D model to import. When the package "
    "holds several footprints, only the one you pick is installed; the others are "
    "listed under <b>Not used</b> in the preview.</p>"
    "<p>SnapEDA ships the 3D model as a separate download. Click <b>" + ADD_MODEL_TEXT + "</b> "
    "on the 3D model row and pick the <code>.step</code>, <code>.stp</code> or "
    "<code>.wrl</code> file, or the <code>.zip</code> that holds it. The added model is "
    "checked like a package, and it shows in the preview before anything is written. "
    "If the file is not a usable 3D model, or a <code>.zip</code> holds any file that is not, "
    "nothing from it is added: the 3D model row shows why in red and <b>Install Part</b> "
    "stays blocked. Click <b>" + REMOVE_MODEL_TEXT + "</b> to clear it, or <b>" + ADD_MODEL_TEXT
    + "</b> to pick another file.</p>"
    "<h3>Target library</h3>"
    "<p>Every part goes into a library named <code>Atomic_</code> followed by the name of "
    "a KiCad library, for example <code>Atomic_Transistor_FET</code>. The name says what "
    "kind of part it is, so a part is easy to find next to KiCad's own.</p>"
    "<p>The app suggests a name. It looks first at similar parts in your own "
    "<code>Atomic_</code> libraries, then at similar parts in KiCad's libraries, and then "
    "at the vendor's category and the part's description. Hover the field: the tooltip "
    "says which of these gave the suggestion. Similar parts decide only when they agree: "
    "when they are spread over several libraries, or only the first letters match, the "
    "part's description decides if it names the kind of part. When nothing fits, the "
    "field starts empty and waits for you.</p>"
    "<ul>"
    "<li>The list shows your <code>Atomic_</code> libraries first, then every other name "
    "that is allowed. Typing filters it.</li>"
    "<li>A KiCad library name on its own, such as <code>Transistor_FET</code>, is refused. "
    "So is a name that holds a maker, such as <code>Atomic_TI</code>, and so are the old "
    "library names. The strip under the field gives the reason and, where it can, the "
    "name to use instead.</li>"
    "<li>A wrong letter case is corrected when you leave the field, and a grey note "
    "says so.</li>"
    "<li>A new library creates only its <code>.kicad_sym</code> file. Its footprints go "
    "into the shared library described below.</li>"
    "</ul>"
    "<h3>Footprint</h3>"
    "<p>By default the vendor's footprint is installed into one shared library, "
    "<code>Atomic_Footprints</code>, and the symbol links to it as "
    "<code>Atomic_Footprints:</code> followed by the footprint name.</p>"
    "<p>To use a footprint that KiCad already ships, choose <b>" + OFFICIAL_FOOTPRINT_TEXT
    + "</b>. A list of KiCad's footprints appears, with the best matches for this part "
    "first, and typing filters it. The symbol then links to that official footprint. "
    "The vendor footprint and the vendor 3D model are not installed (the preview lists "
    "them under <b>Not used</b>), and KiCad's own 3D model is used. KiCad's own "
    "footprints are never changed. If the pads of the official footprint differ from the "
    "vendor's, a warning says so. Choose <b>" + VENDOR_FOOTPRINT_TEXT + "</b> to go back. "
    "When the official choice is greyed out, KiCad's footprints were not found; "
    "<b>Set KiCad Footprint Path</b> in the File menu fixes that.</p>"
    "<p>When <code>Atomic_Footprints</code> already holds a footprint of the same name:</p>"
    "<ul>"
    "<li>If the content is the same, it is reused and nothing is written.</li>"
    "<li>If the content differs, the <b>Conflicts</b> section asks you to choose "
    "<b>Overwrite</b>, <b>Rename</b> or <b>Skip</b> (see below). <b>Rename</b> suggests "
    "the footprint name followed by the MPN. <b>Overwrite</b> names the other parts that "
    "use that footprint, so you see what changes for them.</li>"
    "</ul>"
    "<h3>Fields</h3>"
    "<p>Edit the footprint name and the Datasheet, Description, Manufacturer "
    "and MPN fields. The Datasheet, Description and Manufacturer are required: while "
    "one is empty, its box says what to type and <b>Install Part</b> stays blocked "
    "(see Atomic check). The MPN cannot "
    "be empty. Value always equals the MPN, so it is shown but cannot be "
    "edited.</p>"
    "<p>The Manufacturer is written in its standard spelling: <i>TI</i> becomes "
    "<i>Texas Instruments</i>, and the preview lists the correction under the field "
    "changes. When the vendor gave no Manufacturer, it is taken from the Datasheet link "
    "if the company is known.</p>"
    "<p>Three texts are filled in for you: <b>Keywords</b>, <b>Footprint description</b> "
    "and <b>Footprint tags</b>. They are what KiCad's symbol and footprint choosers "
    "search and show. You can edit each one. The small button next to it, whose tooltip "
    "starts with <i>Regenerate</i>, writes it again from the part's details and drops "
    "your edit.</p>"
    "<h3>Atomic check</h3>"
    "<p><b>Install Part</b> stays blocked until the part passes the atomic check. The part "
    "needs an MPN, a Manufacturer, a footprint that exists, a Value equal to the MPN, a "
    "Datasheet link, a Description and a 3D model.</p>"
    "<p>The amber strip lists each problem on its own line. Click a problem to jump to the "
    "field that fixes it. A problem clears as soon as you type a valid value. "
    "A missing 3D model is fixed with <b>" + ADD_MODEL_TEXT + "</b> or by choosing <b>"
    + OFFICIAL_FOOTPRINT_TEXT + "</b>, which brings KiCad's own 3D model.</p>"
    "<h3>Conflicts</h3>"
    "<p>When an item already exists in the library, each conflict is its own row in "
    "the <b>Conflicts</b> section, with <b>Overwrite</b>, <b>Rename</b> and "
    "<b>Skip</b>. None is chosen at first, and <b>Install Part</b> stays blocked "
    "until every row has a choice. There is no overwrite-all.</p>"
    "<ul>"
    "<li><b>Overwrite</b> replaces the existing item and keeps a backup of the "
    "replaced file.</li>"
    "<li><b>Rename</b> installs the new item under the name you type in the row.</li>"
    "<li><b>Skip</b> keeps the existing item and links it instead.</li>"
    "</ul>"
    "<p>Double-click a conflict row to compare the existing file with the incoming "
    "one. While that comparison is being prepared, <b>Install Part</b> waits, and it "
    "becomes available again when the comparison is ready.</p>"
    "<h3>Install and result</h3>"
    "<p>Nothing is written until you click <b>Install Part</b>. <b>Cancel</b>, to its "
    "right, closes the dialog without installing anything, the same as the window's "
    "close button. While it installs, your choices are locked, a progress bar shows "
    "each step, <b>Cancel</b> is greyed out, and the dialog cannot be closed or "
    "cancelled.</p>"
    "<p>The preview is rebuilt in the background when you edit a field. If you press "
    "<b>" + CHANGE_PACKAGE_TEXT + "</b>, pick another package or close the dialog while it is still being "
    "built, the dialog greys out and a strip at the bottom reads <b>" + FINISHING_TEXT
    + "</b> The window stays live. The dialog then carries on by itself once the preview "
    "is ready: it returns to the start page, opens the other package, or closes. Press "
    "<b>Cancel</b> to stay where you are. After 10 seconds the strip adds that "
    "the KiCad command-line tool is slow to respond; it gives up after 60 seconds.</p>"
    "<p>If the install fails, the dialog returns to the preview with a red banner "
    "that lists the reasons. Every file is restored; if a restore itself fails, the "
    "banner names the backup folder that holds the original files. Fix the problem "
    "and click <b>Install Part</b> again.</p>"
    "<p>A successful install shows the result in two columns under one line. That line says "
    "what was installed, sums up the warnings (<i>No warnings.</i>, or how many, with the "
    "<b>Warnings</b> list then at the top of the left column) and has the <b>Help</b> button. "
    "The left column lists <b>Files written</b> (double-click a file to view it), the "
    "<b>Library list</b> and <b>Library tables</b> rows, and the "
    "<b>Backup folder</b> with an <b>Open folder</b> button. "
    "When KiCad is running, a notice there asks you to reopen KiCad's "
    "Symbol and Footprint editors to see the library. The right column holds the "
    "Commit step. The window keeps its width and becomes only as tall as the result needs, never taller "
    "than it was; once you resize it, it keeps your size.</p>"
    "<p>When KiCad reads its libraries from a different folder than this one "
    "(<code>KICAD_LIB_GITHUB</code>), an amber line in the result names both "
    "folders. The installed part is still written; nothing is blocked. KiCad will "
    "see it once it exists in the folder it reads: switch with <b>File &rarr; Use "
    "KiCad's Folder</b>, or let the app point KiCad at this folder when it "
    "offers to.</p>"
    "<h3>Commit</h3>"
    "<p>After a successful install, the result also shows a Commit step. It names the "
    "Custom branch, the parent repo and its branch, and lists <b>Files to commit</b>: "
    "exactly the files the install wrote. None can be left out. The commit message is "
    "editable and already records the vendor, the package file name and the date. "
    "<b>Commit</b> sits beside <b>Close</b> at the bottom of the window, so it is visible "
    "without scrolling, and the message box opens on its first line. A list of more than "
    "three files starts collapsed (press <b>Show</b>), and Files to commit opens by itself "
    "when a file is marked.</p>"
    "<ul>"
    "<li><b>Also commit the Custom ref in the parent repo</b> is ticked by default. The "
    "message for the parent commit is generated and shown.</li>"
    "<li>Amber files also contain uncommitted changes made before this import. They are "
    "committed too. Double-click one to see what it held.</li>"
    "<li>Other changes in Custom stay uncommitted.</li>"
    "<li>In a new collection, where Custom has no parent repository, no parent option "
    "is shown.</li>"
    "<li>A part that breaks the atomic rule stops the commit. The panel names the part "
    "and the rule, and <b>Commit</b> stays off. <b>Open Check Atomic Parts…</b> opens the "
    "check on that part so you can fix it. <b>Check again</b> then takes the files as they "
    "are now: a file changed after the install is marked \"changed since install\", and a "
    "footprint or 3D model that a committed part links but that is not committed yet is "
    "added and marked \"added: linked by a committed part\". Parts "
    "that already failed before the import are listed but do not stop the commit. Check "
    "again never commits; you still click <b>Commit</b>.</li>"
    "<li>When Custom is on a detached HEAD that sits on the history of main, "
    "<b>Switch to main</b> is offered. Any other detached HEAD is refused, and so is a "
    "local main that is behind origin/main.</li>"
    "<li>The hooks of both repos always run.</li>"
    "<li>Your work is never pushed. The result says how many commits each branch is "
    "ahead of its remote.</li>"
    "</ul>"
    "<p>Click <b>Commit</b> to commit. While Commit or Switch to main runs, the dialog "
    "and the main window cannot be closed; they can be closed while the first check "
    "runs. If you close the dialog without committing, the files stay "
    "uncommitted and the log says so.</p>"
    "<h3>Library tables</h3>"
    "<p>After installing, the library list rescans and selects the library. A new "
    "library is added to <code>sym-lib-table</code> and <code>fp-lib-table</code> "
    "without changing any other entry. An existing library that is missing from the "
    "tables shows a hint to press <b>Generate Tables</b>.</p>"
    "<p>If an entry the app added earlier under the same name points at a library that "
    "no longer exists, it is pointed at the installed library, after a backup of the "
    "table. A name that already points at another library that exists, or at an entry "
    "you added by hand, is left alone and a warning says so. With an empty Destination "
    "box no table is written.</p>"
)

HELP_PAGES["catalog"] = _wrap(
    "<h2>Library Catalog</h2>"
    "<p>Add libraries made by other people, such as W&uuml;rth Elektronik or SparkFun, to your collection and "
    "keep them up to date, without copying files by hand. Open the catalog with "
    "<b>File &rarr; Library Catalog...</b> (<code>Ctrl+Shift+L</code>). When the last check found newer versions, "
    "the menu entry says how many, for example <b>Library Catalog... (2 updates)</b>.</p>"
    "<h3>What the catalog is</h3>"
    "<p>Each library is a plain download of a public GitHub repository. It is kept in its own folder under "
    "<code>ThirdParty</code> in your collection, and the file <code>catalog.json</code> in the collection folder "
    "records what you added. Your own libraries in <code>Custom</code> are never part of it. When your collection "
    "is a git repository, the app adds the line <code>/ThirdParty/</code> to its <code>.gitignore</code> so that git "
    "does not treat the downloaded libraries as yours. The app does not commit <code>catalog.json</code> for "
    "you.</p>"
    "<p>KiCad's own Plugin and Content Manager is a separate way to get libraries. The catalog never touches it: "
    "it installs nothing through it and changes none of its packages or settings.</p>"
    "<p>The window stays open beside the main window. Its list has the columns Name, Status, Licence and Size, and "
    "<b>Search libraries</b> narrows it. Select a library to see its details on the right. The status is one of "
    "<i>Not installed</i>, <i>Installed</i> (with a tick when the last check found it current), "
    "<i>Update available</i>, <i>Problem: folder missing</i> or <i>Problem: not in the catalog</i>. "
    "<b>Help</b> and <code>F1</code> in the window open this page.</p>"
    "<p>The catalog downloads with Git, so it needs Git 2.32 or newer. When Git is missing or too old, a note at "
    "the top says so and the buttons that download stay off. A Git older than 2.49.1 still works, with a note "
    "that asks you to update it.</p>"
    "<p>A library can point at a few 3D models that its own repository does not have. The scan shows each one as an "
    "amber warning, the same as for your own libraries, and the library stays <i>Installed</i>. A missing 3D model "
    "is never counted as a problem of the library.</p>"
    "<p>The catalog waits while the main window scans and while the import window or the migration window is "
    "open. The library folder cannot be changed while a catalog job runs or "
    "while a downloaded library waits for your answer. If you close the window during a job, it asks "
    "<b>Stop the current job?</b>.</p>"
    "<h3>Adding a library</h3>"
    "<p>Select a library that is <i>Not installed</i> and press <b>Add This Library</b>. The first page is step 1 "
    "of 2. It shows the repository, the licence with a <b>Read the licence</b> link that opens the licence terms "
    "in your browser, the size to download and the folder it will be installed in. When the licence asks for it, "
    "the tick <b>I have read the licence terms</b> sits right under that link.</p>"
    "<p>Press <b>Download and Check</b>; the button shows the size when it is known, for example "
    "<b>Download and Check (about 69 MB)</b>. It copies the library to a temporary folder and checks it. Nothing "
    "is added yet: on the next page you choose <b>Add Library</b> or <b>Discard Download</b>. When you reinstall a "
    "library whose folder is missing, the page names <b>Reinstall Library</b> in place of <b>Add Library</b>.</p>"
    "<p>The download goes to a temporary folder, with its progress on the strip at the bottom. "
    "<b>Cancel Adding</b> stops it and the downloaded copy is deleted. When the download is complete, the app checks "
    "that it holds KiCad libraries it can use (symbols or footprints for KiCad 6 and newer) and shows the Add "
    "preview:</p>"
    "<ul>"
    "<li><b>What will be added</b> &mdash; the folder under <code>ThirdParty</code>, the record in "
    "<code>catalog.json</code> and the <code>.gitignore</code> line, with the number of symbol and footprint "
    "libraries.</li>"
    "<li><b>Libraries with the same name</b> &mdash; any library that has the same name as one you already have, "
    "including KiCad's own. Names are never changed. These libraries start unticked in the main window, so "
    "Generate Tables never lists two libraries with one name; tick one yourself if you want it.</li>"
    "<li><b>Path variables</b> &mdash; a KiCad path variable the library's 3D models need (see below).</li>"
    "</ul>"
    "<p>Press <b>Add Library</b> to add it, or <b>Discard Download</b> to delete the copy and leave your "
    "collection as it was. Nothing is written to your collection before <b>Add Library</b>. Its last step, the "
    "move into place and the record, takes a moment and cannot be stopped halfway: the strip says so, and "
    "closing the window does nothing until it ends.</p>"
    "<p>After that the app reads only the new library again and ticks its symbol and footprint libraries, except "
    "the ones with the same name as yours. A line in the log says what was added. Press <b>Generate Tables</b> "
    "(on the result line of the window, or <code>Ctrl+G</code>) to write the new libraries into your KiCad library tables. "
    "If KiCad is open, a note asks you to restart it to see the change.</p>"
    "<p>If your collection used the old W&uuml;rth Elektronik folder (<code>WurthElektronik/KiCad-Library</code>), "
    "the W&uuml;rth libraries you had ticked stay ticked after you add it from the catalog: they carry over to "
    "<code>ThirdParty/WurthElektronik</code>, and the log says how many moved. Press <b>Generate Tables</b> so the "
    "tables point at the new folder.</p>"
    "<p>An Add is refused, before or after the download and with the reason on the page, when there is not enough "
    "free disk space, when the folder is already there, when the repository holds no usable library, only the old "
    "KiCad 5 format, or only a Plugin and Content Manager package, or when its 3D models are kept in a way the "
    "catalog does not support. Nothing is added then.</p>"
    "<h3>Adding by web address</h3>"
    "<p>For a library that is not in the list, press <b>Add by URL...</b> and paste the address of its repository "
    "page, for example <code>https://github.com/owner/repository</code>. Press <b>Check Repository</b>. Only "
    "public repositories on github.com can be added. An address that is not from GitHub, a repository that is "
    "private or does not exist, and one the catalog already lists are refused with the reason.</p>"
    "<p>After the check, the licence page, the download, the preview and <b>Add Library</b> work as above. "
    "The app does not know a page for the licence of such a library, so its <b>Read the licence on the repository "
    "page</b> link opens the repository page. The library is listed under its owner and repository name.</p>"
    "<h3>Licences</h3>"
    "<p>Every library keeps its own licence. The catalog does not change it and does not decide whether you may "
    "use the library: nothing is refused for its licence. The Licence column and the licence page show what the "
    "repository says.</p>"
    "<p>For an open licence, such as MIT or BSD, there is nothing to tick. For a share-alike licence (if you share "
    "changed copies, you must share them under the same terms) or a proprietary one (the owner sets the terms), "
    "the page asks you to tick <b>I have read the licence terms</b> before <b>Download and Check</b>. When the "
    "repository states no licence, or one the app cannot name, the licence file is shown after the download, "
    "before <b>Add Library</b>, and the tick is there. The tick only records that you read the terms, with the "
    "date. A reinstall does not ask again.</p>"
    "<h3>Updating</h3>"
    "<p><b>Check for Updates</b> asks GitHub whether the installed libraries have a newer version. It downloads "
    "nothing. A library with a newer version shows <i>Update available</i> and a note with the old and the new "
    "version.</p>"
    "<p>Press <b>Update This Library</b>. The app first shows <i>Looking for changes</i>, then a preview: the "
    "old and the new version, the number of files that changed, the <b>Libraries added</b> and the "
    "<b>Libraries removed</b>. Projects that use a removed library lose those parts. Press <b>Update Library</b> to "
    "update, or <b>Keep Current Version</b> to leave the library as it is. <b>Cancel Updating</b> stops the work, "
    "and the library then stays on its current version.</p>"
    "<p>The libraries of the catalog are managed copies. When you changed a file inside a library's folder, the "
    "update is refused and the changed files are listed, because an update would overwrite your changes. Keep your "
    "own changes in <code>Custom</code> instead.</p>"
    "<p>After an update the app reads only that library again. The libraries the update added are ticked unless "
    "they have the same name as one you have; a selection of a library that is gone is dropped, and the log says "
    "so.</p>"
    "<h3>Removing</h3>"
    "<p>Press <b>Remove This Library</b>. The page asks <i>Remove &lt;name&gt;?</i> and says which folder is "
    "deleted, how much space it uses, which libraries leave your scan, and which path variables the library used. "
    "<b>Keep Library</b> is the button that is chosen when the page opens, and <code>Esc</code> presses it. "
    "<b>Remove Library</b> only deletes when you press it yourself; <code>Ctrl+Return</code> never "
    "does.</p>"
    "<p>Removing cannot be stopped halfway, and if it fails the library stays in the catalog. The path variables stay set in KiCad, and "
    "projects that still use this library's 3D models lose them. The next <b>Generate Tables</b> drops the removed "
    "libraries from your KiCad library tables.</p>"
    "<h3>If a library shows a problem</h3>"
    "<p><b>Problem: folder missing</b> means the catalog lists the library but its folder is gone: it was deleted, "
    "or the collection was copied from another computer without it. <b>Reinstall This Library</b> downloads it "
    "again from the recorded address. <b>Remove This Library</b> drops the entry instead.</p>"
    "<p><b>Problem: not in the catalog</b> means a folder under <code>ThirdParty</code> that the record does not "
    "list, so the app does not know where it came from. Its libraries are still scanned like any other. The app "
    "never deletes it by itself; <b>Remove This Library</b> deletes it after you confirm.</p>"
    "<p>If <code>catalog.json</code> itself cannot be read, a red note at the top says so and nothing is changed. "
    "Fix or delete the file, then open the catalog again.</p>"
    "<h3>Update checks</h3>"
    "<p>The app also looks for updates by itself at every start and after you switch to another library folder. "
    "It runs in the background and never holds up the window. It asks GitHub for the newest version of each "
    "installed library, downloads nothing and writes no file in your collection, so a check never makes your "
    "repository dirty. It is skipped when nothing is installed or Git is missing.</p>"
    "<p>When GitHub cannot be reached, the start check gives no message. A row then stays <i>Installed</i>, and "
    "its tooltip says that updates have not been checked. When updates are found, one line in the log names the "
    "libraries and the menu entry shows the count. <b>Check for Updates</b> in the window does the same on "
    "request, and it does say in the log when GitHub could not be reached.</p>"
    "<h3>Path variables</h3>"
    "<p>The 3D models of some libraries are found through a KiCad path variable, for example "
    "<code>WE_3DMODEL_DIR</code> for W&uuml;rth Elektronik. The <i>Path variables</i> row of the details says "
    "whether it is set, not set or set to a different folder. KiCad's own variables are never changed.</p>"
    "<p>After an add, the app asks <b>Change KiCad path variables?</b> when KiCad needs a new or different value. "
    "No is the default, and nothing is written to KiCad without Yes. <b>Set Path Variables...</b> in the "
    "details asks again later; it shows only for a library whose variable is not set or points elsewhere. After "
    "a change, restart KiCad so that all your projects see it.</p>"
)

HELP_PAGES["migrating"] = _wrap(
    "<h2>Migrating to Atomic Libraries</h2>"
    "<p>Move every part still in an old-style Custom library into the "
    "<code>Atomic_</code> libraries, in one preview-then-run window.</p>"
    "<h3>Before you start</h3>"
    "<p>Open <b>File &rarr; Migrate to Atomic Libraries...</b> (<code>Ctrl+Shift+M</code>). "
    "It is offered only while <code>Custom/</code> still has a library that is not named "
    "<code>Atomic_...</code>, or a leftover <code>.bak</code> file; once everything is "
    "already <code>Atomic_</code>, the menu item is greyed out and says so.</p>"
    "<p>Custom must hold no uncommitted files when the window opens. If it does, the "
    "window lists them and asks you to commit or delete them first, then open the "
    "migration again.</p>"
    "<p>Close KiCad before you run the migration: a locked file stops it. The migration "
    "window checks for KiCad again right before it writes anything.</p>"
    "<p>Before the first write, the app tags the current commit "
    "<code>pre-atomic</code>, so the state before the migration is always recoverable "
    "from that tag, even after the migration commits its own changes.</p>"
    "<h3>The preview</h3>"
    "<p>Parts are grouped by the <code>Atomic_</code> library they would move into. Each "
    "group header shows a pass mark when every part in it is ready, or the number of "
    "problems otherwise. A <b>failure strip</b> above the list names every blocking "
    "problem across all groups; click a line in the failure strip to jump straight to "
    "the part and field it is about.</p>"
    "<p>A library the app only guessed (similar part numbers spread over several KiCad "
    "libraries, or matching only on the first letters, with nothing in the description to "
    "confirm it) is marked <b>" + GUESS_MARK + "</b> in the part list and gets a line in "
    "the failure strip. Pick that library, or another one, from the <b>Library</b> list, "
    "or type one, to confirm it, and the line goes away. A library suggested with "
    "confidence is marked <b>" + SUGGESTED_MARK + "</b> and does not block the run. The "
    "<b>Library</b> list also offers the other libraries that hold similar parts, and the "
    "reason for the suggestion is shown under the field.</p>"
    "<p>Selecting a part shows its detail pane: the <b>Library</b> field with the app's "
    "suggestion, the <b>Symbol name</b> taken from the MPN, and the MPN, Manufacturer, "
    "Datasheet and Description fields, the same as importing a part. The footprint row "
    "offers <b>" + MOVE_FOOTPRINT_TEXT + "</b> or, for a part that can use one of KiCad's "
    "own footprints, " + OFFICIAL_FOOTPRINT_TEXT + ". The 3D model row shows the current "
    "model or lets you add one with <b>" + ADD_MODEL_TEXT + "</b>, exactly as importing "
    "does. Parts that are otherwise identical can be turned into a derived symbol of one "
    "another, so only the one real difference between them is kept. The Keywords and "
    "footprint description and tags are filled in for you; the small button whose "
    "tooltip starts with <i>Regenerate</i> writes each one again from the part's "
    "details.</p>"
    "<p>The <b>" + FILES_TAB_TEXT + "</b> tab lists every file the migration would "
    "write, move, rename or delete, and the <b>" + LEFTOVERS_TEXT + "</b> section lists "
    "the leftover files the migration found but does not need; tick or untick each one "
    "to decide whether it is deleted too.</p>"
    "<p>Your edits are saved as you go, so closing the window and reopening it later "
    "brings the preview back where you left it. If a part changed on disk while the "
    "window was closed, it is marked so you notice before you run.</p>"
    "<h3>Run and result</h3>"
    "<p><b>" + RUN_TEXT + "</b> is enabled only once the failure strip is empty: every "
    "part in every group must be ready first. The whole move runs as one transaction; if "
    "any step fails, every file is restored and the window shows every reason, with the "
    "backup folder named if a restore itself could not be completed.</p>"
    "<p>A successful run shows the old and new name of every part, with a <b>Copy</b> "
    "button and a <b>" + OPEN_MAP_TEXT + "</b> link; the same map is saved as "
    "<code>MIGRATION-ATOMIC.md</code> in <code>Custom/</code>, so it stays available "
    "after the window closes.</p>"
    "<h3>Afterwards</h3>"
    "<p>The result shows the folder the library tables go to (<b>" + DESTINATION_LABEL + "</b>), "
    "with <b>" + BROWSE_TEXT + "</b> to change it; the Destination box of the main window "
    "changes with it. A folder that is not set, or that no longer exists, is pointed out "
    "there. The outcome of <b>" + GENERATE_TEXT + "</b> is shown under the buttons.</p>"
    "<p>From the result, click <b>" + GENERATE_TEXT + "</b> first, so the library tables "
    "list the new <code>Atomic_</code> libraries and drop the old names. Then commit in "
    "the panel below the result: one commit in <code>Custom</code>, plus the usual commit "
    "of its ref in the parent repo. Then click <b>" + CHOOSER_TEXT + "</b> to pin the new "
    "libraries at the top of KiCad's library lists.</p>"
    "<p>Any KiCad project that already used the old library names needs relinking once: "
    "open it, then run <b>Tools &rarr; Edit Symbol Library Links...</b>, then "
    "<b>Update Symbols from Library...</b>, then <b>Update PCB from Schematic...</b>. "
    "<code>MIGRATION-ATOMIC.md</code> lists the old and new names to match up.</p>"
)

HELP_PAGES["restoring"] = _wrap(
    "<h2>Restoring Backups</h2>"
    "<p>Open via <b>File &rarr; Restore Backup</b> or <code>Ctrl+R</code>.</p>"
    "<p>The restore dialog shows all available backup pairs. Each entry restores "
    "<b>both</b> the sym-lib-table and fp-lib-table together to ensure consistency.</p>"
    "<h3>Restore process</h3>"
    "<ol>"
    "<li>Select the folder containing your tables (defaults to the destination)</li>"
    "<li>The dialog lists all backup pairs found (e.g.&nbsp;<i>Backup #1</i>, "
    "<i>Backup #2</i>)</li>"
    "<li>Select a backup and click <b>Restore</b></li>"
    "<li>The current tables are backed up first, then the selected backup is "
    "restored</li>"
    "</ol>"
)

HELP_PAGES["filter"] = _wrap(
    "<h2>Footprint Filter</h2>"
    "<p>Footprint selection is <b>driven by symbols</b> &mdash; you don't need to "
    "manually check footprint libraries.</p>"
    "<h3>How it works</h3>"
    "<ol>"
    "<li>When you select or deselect symbols, the tool reads their footprint "
    "references</li>"
    "<li>It checks which footprint libraries are needed and automatically "
    "checks/unchecks them</li>"
    "<li>A footprint stays selected if <b>any</b> selected symbol from <b>any</b> "
    "source references it</li>"
    "</ol>"
    "<h3>Per-source scoping</h3>"
    "<p>The filter is <b>scoped per source</b>:</p>"
    "<ul>"
    "<li>Deselecting all <i>Custom</i> symbols only affects <i>Custom</i> "
    "footprints</li>"
    "<li>W&uuml;rth footprints remain untouched (and vice versa)</li>"
    "<li>This prevents cross-source interference</li>"
    "</ul>"
    '<p class="hint"><b>Tip:</b> You can manually override any footprint checkbox '
    "after the automatic filter runs. The override persists until the next symbol "
    "change triggers a re-filter.</p>"
)

HELP_PAGES["shortcuts"] = _wrap(
    "<h2>Keyboard Shortcuts</h2>"
    "<table>"
    "<tr><th>Shortcut</th><th>Action</th></tr>"
    "<tr><td><code>Ctrl+I</code></td><td>Import Part</td></tr>"
    "<tr><td><code>Ctrl+G</code></td><td>Generate Tables</td></tr>"
    "<tr><td><code>Ctrl+R</code></td><td>Restore Backup</td></tr>"
    "<tr><td><code>Ctrl+Shift+R</code></td><td>Rescan Libraries</td></tr>"
    "<tr><td><code>Ctrl+Shift+A</code></td><td>Check Atomic Parts</td></tr>"
    "<tr><td><code>Ctrl+Shift+M</code></td><td>Migrate to Atomic Libraries</td></tr>"
    "<tr><td><code>Ctrl+Shift+K</code></td><td>Pin Atomic Libraries in KiCad</td></tr>"
    "<tr><td><code>Ctrl+Shift+L</code></td><td>Library Catalog...</td></tr>"
    "<tr><td><code>Ctrl+K</code></td><td>Set KiCad Footprint Path</td></tr>"
    "<tr><td><code>Ctrl+Q</code></td><td>Exit</td></tr>"
    "<tr><td><code>F1</code></td><td>Open the User Guide in its own window, which stays open beside the other windows. "
    "In the import window it opens on Importing Parts, the same as <b>" + HELP_ACTION_TEXT
    + "</b> on that window's toolbar. From the main window it goes back to the page or section you last chose, "
    "scrolled to that heading; if the guide is already open there, it is only brought to the front.</td></tr>"
    "</table>"
)

HELP_PAGES["roadmap"] = _wrap(
    "<h2>Roadmap</h2>"
    "<ul>"
    "<li><b>Grow the library collection</b> &mdash; continue adding custom symbols "
    "and footprints for new components</li>"
    "<li><b>Standalone executable</b> &mdash; package with PyInstaller or Nuitka "
    "so no Python install is required</li>"
    "<li><b>KiCad plugin</b> &mdash; explore an Action Plugin launcher for "
    "seamless integration inside the KiCad PCB editor</li>"
    "</ul>"
    '<p>Contributions welcome on '
    '<a href="https://github.com/sylvanoMTL/kicad_libraries">'
    "GitHub</a>.</p>"
)


# ── TOC structure ─────────────────────────────────────────────────────

TOC_STRUCTURE: list[tuple[str, str, list[tuple[str, str]]]] = [
    # (key, label, children)
    ("overview", "Overview", []),
    ("_getting_started", "Getting Started", [
        ("requirements", "Requirements"),
        ("how_to_run", "How to Run"),
    ]),
    ("_on_launch", "On Launch", [
        ("library_folder", "Library Folder"),
        ("kicad_detection", "KiCad Detection"),
        ("repo_scan", "Repository Scan"),
    ]),
    ("_how_to_use", "How to Use", [
        ("library_tree", "Library Tree"),
        ("selecting", "Selecting Libraries"),
        ("generating", "Generating Tables"),
        ("importing", "Importing Parts"),
        ("catalog", "Library Catalog"),
        ("migrating", "Migrating to Atomic Libraries"),
        ("restoring", "Restoring Backups"),
    ]),
    ("filter", "Footprint Filter", []),
    ("shortcuts", "Keyboard Shortcuts", []),
    ("roadmap", "Roadmap", []),
]


# ── Menu outline ──────────────────────────────────────────────────────

_H2_RE = re.compile(r"<h2>")
_H3_RE = re.compile(r"<h3>(.*?)</h3>", re.DOTALL)


@dataclass(frozen=True)
class HelpEntry:
    """One row of the User Guide menu: a group, a page, or a section of a page."""

    key: str
    number: str
    label: str
    parent: str | None  # the parent entry's key, None at top level
    page: str | None  # the HELP_PAGES key this entry shows, None for a group
    anchor: str | None = None  # set for sections only

    @property
    def text(self) -> str:
        return f"{self.number} {self.label}"


def section_anchor(label: str) -> str:
    """The anchor name of a heading: lower case, every run of other characters one hyphen, ends trimmed."""
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def page_sections(key: str) -> list[tuple[str, str]]:
    """The (anchor, label) pairs of a page's <h3> headings, in page order. The page text is the only source."""
    sections = []
    for inner in _H3_RE.findall(HELP_PAGES[key]):
        label = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", inner))).strip()
        sections.append((section_anchor(label), label))
    return sections


def help_outline() -> list[HelpEntry]:
    """Every menu row in menu order, numbered from its place: 1, 4.4, 4.4.7."""
    outline: list[HelpEntry] = []

    def add(key: str, number: str, label: str, parent: str | None, is_page: bool) -> None:
        outline.append(HelpEntry(key, number, label, parent, key if is_page else None))
        if is_page:
            for n, (anchor, section) in enumerate(page_sections(key), 1):
                outline.append(HelpEntry(f"{key}#{anchor}", f"{number}.{n}", section, key, key, anchor))

    for i, (key, label, children) in enumerate(TOC_STRUCTURE, 1):
        add(key, str(i), label, None, key in HELP_PAGES)
        for j, (child_key, child_label) in enumerate(children, 1):
            add(child_key, f"{i}.{j}", child_label, key, child_key in HELP_PAGES)
    return outline


def render_page(key: str) -> str:
    """A page's HTML with its menu number before the title and each section heading, and an anchor per section.

    The anchor is an empty named anchor before the heading text, never a wrapper around it: a wrapper would
    take the stylesheet's link colour. HELP_PAGES itself stays unnumbered.
    """
    numbers = {entry.key: entry.number for entry in help_outline()}
    page = HELP_PAGES[key]
    page = _H2_RE.sub(f"<h2>{numbers[key]} ", page, count=1)
    sections = iter(enumerate(page_sections(key), 1))

    def number_section(match: re.Match) -> str:
        n, (anchor, _label) = next(sections)
        return f'<h3><a name="{anchor}"></a>{numbers[key]}.{n} {match.group(1)}</h3>'

    return _H3_RE.sub(number_section, page)


class HelpDialog(QDialog):
    def __init__(self, parent=None, *, topic: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("User Guide — KiCad External Lib Manager")
        self.resize(860, 620)
        self._page_key: str | None = None  # the page the browser shows
        self._quiet = 0  # above 0 while the code, not the owner, moves the selection; such moves are not saved
        self._on_asked_topic = False  # True while a caller's topic is shown and the owner has not chosen since
        self._entries = {entry.key: entry for entry in help_outline()}

        layout = QVBoxLayout(self)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: TOC tree
        self._toc = QTreeWidget()
        self._toc.setHeaderHidden(True)
        self._toc.setMinimumWidth(200)
        self._toc.setMaximumWidth(300)
        self._menu_delegate = _MenuSelectionDelegate(self._toc)  # kept on the dialog so the Python object stays alive
        self._toc.setItemDelegate(self._menu_delegate)
        # A left press on the menu holds it: pages fold and open only after the release (see _on_topic_selected)
        self._menu_held = False
        self._fold_after_release = False
        self._menu_viewport = self._toc.viewport()  # kept so the event filter compares the same Python wrapper
        self._menu_viewport.installEventFilter(self)  # mouse events go to the viewport
        self._toc.installEventFilter(self)  # key events go to the menu itself
        self._build_toc()
        self._toc.currentItemChanged.connect(self._on_topic_selected)
        self._toc.itemClicked.connect(self._on_item_clicked)
        splitter.addWidget(self._toc)

        # Right: content browser
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(True)
        splitter.addWidget(self._browser)

        splitter.setSizes([240, 600])
        layout.addWidget(splitter)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

        # Open on the asked topic, else where the owner left off; the first topic when neither is known
        if topic is None:
            self.show_remembered()
        else:
            self._quiet += 1
            try:
                if not self.show_topic(topic):
                    self._toc.setCurrentItem(self._toc.topLevelItem(0))
            finally:
                self._quiet -= 1

    def showEvent(self, event):
        super().showEvent(event)
        # Bounded by the screen's free area and moved fully inside it, however the guide is opened
        fit_window(self, self.size())
        # The browser applies a pending anchor in its own show, before this showEvent, and fit_window can then
        # narrow the guide and reflow the page under that scroll; a reused guide also keeps its old scroll.
        # A spontaneous show (restored from the taskbar) is skipped, so a page being read does not jump.
        if not event.spontaneous():
            self._show_current_heading()
            QTimer.singleShot(0, self, self._show_current_heading)

    def hideEvent(self, event):
        super().hideEvent(event)
        # A release lost while the guide closes must not leave the menu waiting. Qt still reports a button that
        # was down when the window hid, so the live button check in _on_topic_selected does not cover this path.
        self._menu_held = False
        if self._fold_after_release:
            self._fold_after_release = False
            self._sync_expansion()

    def eventFilter(self, watched, event):
        kind = event.type()
        if watched is self._menu_viewport:
            if kind in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
                # Only the left button drag-selects, so only it holds the menu
                if event.button() == Qt.MouseButton.LeftButton:
                    self._menu_held = True
            elif kind == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                self._menu_held = False
                if self._fold_after_release:
                    self._fold_after_release = False
                    # After the view has handled the release, so it still sees the rows where they were pressed
                    QTimer.singleShot(0, self, self._sync_expansion)
        elif watched is self._toc and kind == QEvent.Type.KeyPress:
            # A key press means the owner is using the keyboard, so a press whose release never arrived (a popup
            # or modal opened during it) must not keep the menu waiting
            self._menu_held = False
            if self._fold_after_release:
                self._fold_after_release = False
                QTimer.singleShot(0, self, self._sync_expansion)
        return super().eventFilter(watched, event)

    def show_remembered(self) -> None:
        """Show the place the owner last chose, quietly: the saved key, else its page, else the first menu item."""
        saved = load_help_topic()
        self._quiet += 1
        try:
            if saved is None or not (self.show_topic(saved) or self.show_topic(saved.partition("#")[0])):
                self._toc.setCurrentItem(self._toc.topLevelItem(0))
        finally:
            self._quiet -= 1
        self._on_asked_topic = False

    def shows_asked_topic(self) -> bool:
        """True while the guide shows a topic a caller asked for and the owner has not chosen a place since."""
        return self._on_asked_topic

    def _show_current_heading(self) -> None:
        """Bring the current menu entry's heading into view: a section to its anchor, a page to its title."""
        current = self._toc.currentItem()
        if current is None:
            return
        entry = self._entries.get(current.data(0, Qt.ItemDataRole.UserRole))
        if entry is None or entry.page is None:
            return
        if entry.anchor is not None:
            self._browser.scrollToAnchor(entry.anchor)
        else:
            self._browser.verticalScrollBar().setValue(0)

    def show_topic(self, key: str) -> bool:
        """Select the topic with this key and show its page; False (nothing changes) when there is none.

        A topic shown this way is not remembered; only the owner's own moves in the menu are.
        """
        self._quiet += 1
        try:
            stack = [self._toc.topLevelItem(i) for i in range(self._toc.topLevelItemCount())]
            while stack:
                item = stack.pop(0)
                if item.data(0, Qt.ItemDataRole.UserRole) == key:
                    self._toc.setCurrentItem(item)
                    self._sync_expansion()
                    self._toc.scrollToItem(item)
                    # The item may already be current, so no currentItemChanged runs _on_topic_selected; this is
                    # the path of show_remembered on a reused guide
                    self._show_current_heading()
                    self._on_asked_topic = True
                    return True
                stack.extend(item.child(i) for i in range(item.childCount()))
            return False
        finally:
            self._quiet -= 1

    def _build_toc(self):
        bold_font = self._toc.font()
        bold_font.setBold(True)

        items = self._items = {}
        for entry in self._entries.values():
            item = QTreeWidgetItem([entry.text])
            item.setData(0, Qt.ItemDataRole.UserRole, entry.key)
            items[entry.key] = item
            if entry.parent is None:
                item.setFont(0, bold_font)
                self._toc.addTopLevelItem(item)
            else:
                items[entry.parent].addChild(item)
        for entry in self._entries.values():
            if entry.page is None:
                items[entry.key].setExpanded(True)

    def _on_topic_selected(self, current: QTreeWidgetItem | None, _previous):
        if current is None:
            return
        entry = self._entries.get(current.data(0, Qt.ItemDataRole.UserRole))
        if entry is None:
            return
        if entry.page is None:
            # Group header without own page: show its first child
            if current.childCount() > 0:
                self._toc.setCurrentItem(current.child(0))
            return
        if entry.anchor is None or entry.page != self._page_key:
            self._browser.setHtml(render_page(entry.page))
            self._page_key = entry.page
        if entry.anchor is not None:
            self._browser.scrollToAnchor(entry.anchor)
        # Saved on every owner move, not on close: Escape and a deleted parent fire no close event
        if not self._quiet:
            save_help_topic(entry.key)
            self._on_asked_topic = False
        # Folding or opening pages moves the rows. With the left button still down, Qt's drag-select picks the row
        # now under the cursor and the wrong place is saved, so the menu waits for the release. A hold whose
        # release was lost ends here when Qt reports the button up, so keyboard moves and instant clicks fold at once.
        if self._menu_held and QGuiApplication.mouseButtons() & Qt.MouseButton.LeftButton:
            self._fold_after_release = True
        else:
            self._menu_held = False
            self._fold_after_release = False
            QTimer.singleShot(0, self, self._sync_expansion)

    def _sync_expansion(self):
        """Open the sections of the page shown and fold the other pages' sections, so the menu stays short.

        Groups keep their state.
        """
        for entry in self._entries.values():
            if entry.page == entry.key and self._items[entry.key].childCount() > 0:
                self._items[entry.key].setExpanded(entry.key == self._page_key)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int):
        # A click on the current item emits no currentItemChanged, so scroll back to the section here
        entry = self._entries.get(item.data(0, Qt.ItemDataRole.UserRole))
        if entry is not None and entry.anchor is not None and item is self._toc.currentItem():
            self._browser.scrollToAnchor(entry.anchor)
