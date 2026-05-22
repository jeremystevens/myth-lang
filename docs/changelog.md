# MyLang Changelog

All notable changes to MyLang are documented here.

---

## v0.8.0 — Current

### Language Runtime — Phase 4: Error System Expansion

- **Structured tracebacks** — runtime errors now produce multi-line, boxed call-stack traces showing the full function call chain from outermost to innermost frame
- **Source line display** — each traceback frame shows the actual source code line that triggered the error
- **Local variable snapshots** — each frame in the traceback includes the values of local variables at the time of the call
- **Module import tracing** — errors inside imported modules display the full import chain (which file imported which, at which line)
- **Syntax error carets** — syntax errors display the offending line with a `^` caret pointing to the error position
- **`TraceFrame` class** — new internal class representing one frame in a call stack
- **`MyLangRuntimeError.format_traceback()`** — renders the full formatted traceback as a string
- **`MyLangSyntaxError.format_traceback()`** — renders a formatted syntax error with source and caret
- **`ASTInterpreter.set_source()`** — new public method to supply source text and file path before `run()`, enabling source-line annotation in tracebacks
- **`ASTInterpreter._enrich_error()`** — new internal method that attaches the current call stack to any `MyLangRuntimeError` before it propagates
- Call stack maintenance is now unconditional — previously only active during debug sessions; now always tracked for error reporting
- `main.py` updated to call `set_source()` and use `format_traceback()` for all error output

---

## v0.7.0

### Language Runtime — Phase 3: File I/O System

- **`read_file(path)`** — read entire file contents as a string
- **`write_file(path, content)`** — create or overwrite a file; creates intermediate directories automatically
- **`append_file(path, content)`** — append to a file; creates if missing
- **`file_exists(path)`** — returns `True`/`False`; never raises
- **`delete_file(path)`** — delete a file with a clear error if not found
- **Path sandbox safety** — all file paths are resolved relative to the script's directory; paths that escape the sandbox (e.g. `../../etc/passwd`) are blocked at runtime with a descriptive error
- **`\n`, `\t`, `\\` escape sequences** in string literals — previously `\n` was stored as two characters; now correctly processed to the actual escape character
- **`ASTInterpreter.file_root`** — new parameter; the directory all file I/O is sandboxed to
- `main.py` updated to pass `file_root=script_dir` to the interpreter

---

## v0.6.0

### Language Runtime — Phase 2: Standard Library Expansion

#### String functions (new)
`trim`, `replace`, `split`, `contains`, `starts_with`, `ends_with`, `repeat_str`, `reverse`

#### Math functions (new)
`abs`, `max`, `min`, `pow`, `floor`, `ceil`, `sqrt`, `clamp`

#### List functions (new)
`first`, `last`, `reverse_list`, `slice`, `contains_item`, `sort`, `index_of`, `flatten`

#### Dictionary functions (new)
`delete`, `merge`, `get`

#### Type conversion functions (new)
`to_int`, `to_str`, `to_bool`, `type_of`

#### I/O
`input` — now supports 0 or 1 arguments (optional prompt string)

#### Arity system
- Built-in function arity is now specified as `(fn, min, max)` tuples supporting optional arguments; legacy `(fn, n)` exact-arity tuples still work
- Error messages now say `"expected 0-1 argument(s)"` for variadic functions

#### Parser: negative number literals
- `abs(-42)`, `clamp(-5, 0, 100)` and similar calls now parse correctly
- Fixed: `find_operator_outside` no longer treats a leading `-` at position 0 as a binary subtraction operator
- `parse_primary` now handles multi-digit integers and negative integer literals

---

## v0.5.0

### Language Runtime — Phase 1: Module / Import System

- **`import` keyword** — loads `.my` files by name; `.my` extension is optional
- **`ImportNode`** — new AST node type
- **`IMPORT` token** — new lexer token type
- **`ASTInterpreter.module_search_paths`** — list of directories searched when resolving imports; the script's directory is always added as the final fallback
- **Import caching** — each file is executed at most once per run regardless of how many times it is imported; circular imports are safe
- **Shared global function registry** — functions defined in an imported module become immediately available to the importer; top-level variable assignments do not leak across module boundaries
- **Child interpreter architecture** — each imported module runs in its own interpreter instance that shares the function registry and import cache with the parent but has its own variable scope
- `main.py` updated to pass `module_search_paths=[script_dir]` to the interpreter

---

## v0.4.0

### IDE — Phase 5: Full Ecosystem

- **Package Manager** — install/uninstall `.my` packages from local paths or URLs; packages stored in `~/.mylang/packages/` and automatically added to import search paths
- **Plugin System** — Python plugins in `~/.mylang/plugins/`; each exposes `register(ide)` and receives the full IDE instance; enable/disable state persisted in `plugin_state.json`
- **Integrated Terminal** — tabbed with the output console; runs real shell commands via `subprocess`; supports command history (Up/Down arrows); working directory syncs to the open file
- **Project Templates** — six built-in templates (Hello World, Calculator, File Logger, Data Processor, Module Library, Interactive Input); user templates loaded from `~/.mylang/templates/`
- **Export / Build Tools** — four export modes: Standalone Script (with launcher), ZIP Package, Markdown Documentation, JSON Syntax Report
- **Ecosystem Toolbar** — dedicated toolbar row for ecosystem tools; hidden by default, toggle via View menu (Ctrl+Shift+W)
- UI audit fixes: main toolbar stripped to 12 essential buttons; terminal tabified with console instead of separate bottom dock; ecosystem toolbar hidden by default

---

## v0.3.0

### IDE — Phase 4: Advanced Tooling

- **`SymbolTable`** — live extraction of functions, variables, imports, and call sites from the parsed AST after every analysis pass
- **Autocomplete popup** — triggers after 2 characters or Ctrl+Space; populated from the symbol table; keywords (blue), builtins (purple), user symbols (normal)
- **Function hint bar** — appears when cursor is inside a function call; shows full signature with current argument underlined and bolded
- **Find References** — Shift+F12 or right-click; finds all uses of the word under the cursor
- **Go to Definition** — F12; jumps to function or variable definition; shows description for builtins
- **Code Formatter** — Shift+Alt+F; normalises indentation, spacing, blank lines between functions, comment style
- **Symbol panel** — second tab in the project dock showing all functions, variables, and imports with jump-to-line
- **Right-click context menu** — Find References and Go to Definition available on any identifier
- **`AnalysisWorker` upgraded** — now emits `SymbolTable` alongside tokens and AST
- **`CodeEditor` upgraded** — emits `autocomplete_requested` and `hint_requested` signals; `word_at_cursor()` method added
- Tools menu added to menu bar

---

## v0.2.0

### IDE — Phase 3: Runtime Integration

- **Integrated debugger** with `DebugController` — shared object between background interpreter thread and UI
- **Breakpoints** — click the line-number gutter to set/clear red breakpoint dots
- **Green execution arrow** — `▶` painted in the gutter on the currently executing line
- **Variable Inspector** — live snapshot of all variables at each pause, colour-coded by type
- **Call Stack panel** — function frame hierarchy with parameter sub-items
- **Exception Viewer** — formatted runtime exceptions with source line context; shown on any error during debug
- **Step Over** (F10) — execute exactly one statement then pause
- **Continue** (F5 in debug) — run until next breakpoint
- **Debug toolbar** — dedicated second toolbar row, visible only during debug sessions
- **`ASTInterpreter.set_debug_controller()`** — added in language runtime Phase 3
- **Debug hooks in `run()`** — `on_line()` called before every statement when controller attached
- **Call stack push/pop in `call_function()`** — available when debug controller attached
- `DebugSignals` — `paused`, `resumed`, `exception` signals
- Status bar debug state label — `⬤ Paused Ln N` during breakpoints

### IDE — Phase 2: Language Services

- **`MyLangHighlighter`** — full QSyntaxHighlighter implementation with separate colour rules per theme
- **Live analysis** — `AnalysisWorker` (QThread) runs lexer + parser 400ms after every keystroke
- **Red squiggly underlines** on syntax error lines using `QTextCharFormat.SpellCheckUnderline`
- **Error status indicator** in status bar — `✓ No errors` / `✗ Ln N: message`
- **Token Viewer** — three-column table (Line / Type / Value) with colour-coded token types
- **AST Viewer** — expandable tree built recursively from AST nodes; colour-coded by node category
- **Jump to Line** — Ctrl+G; modal dialog with spin box
- **Force re-analyse** — Ctrl+Shift+P
- Language menu added to menu bar

### IDE — Phase 1: Core Editor

- **PySide6 rewrite** — replaced original Tkinter implementation
- **Three themes** — Dark (navy), Light (white), QBasic (royal blue + yellow); full QSS stylesheets covering every widget
- **`CodeEditor`** (`QPlainTextEdit`) — custom painted line-number gutter; current-line highlight; unlimited undo/redo
- **Gutter** — line numbers with current-line accent colour
- **Output console** — read-only `QTextEdit`; colour-coded output (normal / error / info)
- **File Explorer** dock — left side; shows `.my` files; double-click to open
- **Toolbar** — New, Open, Save, Run, Debug, Stop, Clear, Analyse, Jump, Tokens; theme selector
- **Status bar** — file path, error status, cursor position, runtime state
- **Run system** — `RunWorker` (QThread); output streamed in real time; UI never blocks
- **Keyboard shortcuts** — Ctrl+N/O/S, F5/F6/F7, Ctrl+G/T/K/D

---

## v0.1.0 — Initial Release

### Language Runtime — Core

- Variables (integer, string, boolean)
- Arithmetic operators: `+`, `-`, `*`, `/`, `%`
- Comparison operators: `==`, `>`, `<`
- Logical operators: `and`, `or`, `not`
- `print` statement
- `if / else / end` blocks
- `while` loops
- `for i = N to M` loops
- `foreach item in list` loops
- `function / return / end` — user-defined functions with parameters
- Lists `[...]` with index access and index assignment
- Dictionaries `{key: value}` with key access and key assignment
- Built-in functions: `upper`, `lower`, `length`, `append`, `remove`, `random`, `keys`, `values`, `exists`
- Comment syntax: `#`
- AST-based interpreter (full lexer → parser → AST → interpreter pipeline)
- `MyLangRuntimeError` and `MyLangSyntaxError` exception types
- `main.py` CLI runner with `--script` argument support
- REPL (`repl.py`)

