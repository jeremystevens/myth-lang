# MyLang Changelog

All notable changes to MyLang are documented here.

---

## v1.1.0 — Current

### Language Runtime — Phase 7: Advanced Runtime Features

#### Runtime Optimisation (`ast_interpreter.py`)

- **Type-keyed fast-path dispatch** — profiling showed `isinstance()` was responsible for ~41% of interpreter CPU time, being called ~8 times per `evaluate()` invocation; replaced cascading `isinstance` checks for the five most common node types (`NumberNode`, `StringNode`, `VariableNode`, `BinaryOperationNode`, `CompareNode`) with `type(node) is NodeType` comparisons at the top of `evaluate()`, reducing overhead significantly on all inner-loop workloads

#### Constant Folding (`optimizer.py` — new file)

- **`ASTOptimiser` class** — single-pass AST rewriter that runs between the parser and the interpreter, pre-evaluating pure constant expressions so they are never re-evaluated at runtime
- **Arithmetic folding** — `BinaryOperationNode(NumberNode(2), '*', NumberNode(3))` → `NumberNode(6)` at parse time
- **String concat folding** — `"Hello " + "World"` → `StringNode("Hello World")` at parse time
- **Chained folding** — `10 + 5 + 2` folds left-to-right across the entire chain → `NumberNode(17)`
- **Comparison folding** — `1 == 1` → `NumberNode(True)`, `5 > 10` → `NumberNode(False)`
- **Unary NOT folding** — `not false` → `NumberNode(True)`
- **Short-circuit logical folding** — `true and X` → `X`, `false and X` → `False`, `true or X` → `True`, `false or X` → `X`
- **Dead branch elimination** — `if true` discards the false branch entirely; `if false` discards the true branch; reduces the node list the interpreter ever sees
- **`ASTOptimiser.report()`** — returns a summary string of nodes visited, binary ops folded, comparisons folded, and dead branches cut
- Optimiser is non-destructive — always returns a new node list, never mutates the original AST

#### Bytecode Compiler (`compiler.py` — new file)

- **`Compiler` class** — walks a MyLang AST and emits a flat `Chunk` of `Instruction` objects; does not execute any code
- **`Instruction` dataclass** — holds `opcode`, `operand`, and `line` number
- **`Chunk` class** — a compiled execution unit with an instruction list, sub-chunks for function/method bodies, and `disassemble()` for human-readable output
- **Complete instruction set** covering: stack operations (`PUSH_INT`, `PUSH_STR`, `PUSH_BOOL`, `PUSH_NULL`, `POP`, `DUP`), variables (`LOAD_VAR`, `STORE_VAR`), arithmetic (`ADD`, `SUB`, `MUL`, `DIV`, `MOD`), comparisons (`EQ`, `GT`, `LT`, `LE`, `GE`, `NE`), logic (`NOT`, `NEG`), control flow (`JUMP`, `JUMP_IF_FALSE`, `JUMP_IF_TRUE`), functions (`CALL`, `CALL_BUILTIN`, `RETURN`, `MAKE_FUNCTION`), classes (`MAKE_CLASS`, `CALL_METHOD`, `LOAD_ATTR`, `STORE_ATTR`), collections (`BUILD_LIST`, `BUILD_DICT`, `INDEX_GET`, `INDEX_SET`), modules (`IMPORT`, `FROM_IMPORT`, `EXPORT`), and output (`PRINT`, `HALT`)
- **Back-patching** — `JUMP*` instructions are emitted with placeholder targets then patched once the target offset is known; enables correct `if/else` and loop compilation in a single pass
- **Sub-chunk architecture** — each function and method body compiles into its own named `Chunk`, stored in the parent chunk's `sub_chunks` dict

#### Optional VM Architecture (`vm.py` — new file)

- **`VM` class** — a working stack-based virtual machine that executes compiled `Chunk`s
- **`Frame` class** — represents one call frame with its own `Chunk`, program counter, and local variable dict
- **`VMObject`** — VM-native object instance (mirrors `MyLangObject`)
- **`VMNamespace`** — VM-native module namespace (mirrors `MyLangNamespace`)
- **Opcode dispatch table** — opcodes are dispatched via a `_dispatch` dict built automatically from `_op_*` methods; eliminates `isinstance` chains and makes adding new opcodes trivial
- **Full built-in function table** — all 40+ stdlib functions implemented as lambdas inside the VM
- **`_run_until_return()`** — helper for synchronous constructor execution during class instantiation
- The VM is an optional execution backend; the AST interpreter remains the default executor

#### Garbage Collection Planning (`docs/gc_plan.md` — new file)

- **GC design document** — full analysis of the current memory model, identified weaknesses (scope leaks, no allocation visibility), and a concrete implementation plan
- **Proposed strategy: scope-aware reference tracking** — generation counter on `MyLangObject`, freed when creating scope exits; mark-and-sweep pass handles object graph cycles
- **`gc_stats()` built-in sketched** — planned function to expose allocation counts, live object count, and current scope depth for debugging and profiling
- Marked as low priority until a native VM becomes the default executor

#### `main.py` updates

- **`ASTOptimiser` wired in** — runs automatically between parse and execution on every script
- **`--bytecode` flag** — prints the disassembled chunk for the script before running it
- **`--no-opt` flag** — skips the optimiser for debugging purposes
- **Version bumped** to `1.1.0`
- Default script changed from `dictionary_builtin_test.my` to `regression_test.my`
- Token and AST debug output removed from default run; now only shown when explicitly requested

---

## v1.0.0

### Language Runtime — Phase 6: Namespaces & Modules

- **`module.function()` syntax** — `import utils` now creates a `MyLangNamespace` stored under the module alias in the caller's variables; functions are accessed via `utils.double(x)` rather than being merged into the global scope
- **`MyLangNamespace` runtime class** — new type wrapping a module alias and its exported names dict; accessible via dot notation through the existing `PropertyAccessNode` / `MethodCallNode` evaluation paths
- **Namespace isolation** — each imported module now runs in its own child interpreter with its own function dict; nothing pollutes the caller's global scope automatically
- **`export` keyword** — marks a name as part of the module's public API; only exported names are accessible via namespace dot notation; modules with no `export` statements export everything (backwards compatible)
- **`ExportNode`** — new AST node representing an `export name` statement
- **`EXPORT` lexer token** — triggered by lines beginning with `export `
- **`from X import Y` syntax** — selective import; brings named exports directly into the caller's scope without creating a namespace object
- **`from X import Y, Z` syntax** — multiple names can be selectively imported in one statement
- **`FromImportNode`** — new AST node holding the module path and list of names to import
- **`FROM_IMPORT` lexer token** — triggered by `from ... import ...` lines
- **`_apply_selective()`** — new interpreter method resolving selective imports against a namespace and registering names into `self.functions`
- **`_namespaces` dict** — new interpreter state field mapping module alias → `MyLangNamespace`; shared with child interpreters so nested imports and circular guards work correctly
- **`_export_names` list** — new interpreter state field; populated by `ExportNode` execution; used by `load_module()` to build the public API
- **Circular import protection fixed** — `_import_cache` is now correctly shared across all child interpreters regardless of whether they were created in namespace mode or legacy mode; prevents infinite recursion on mutually-importing modules
- **`load_module()` rewritten** — new parameters: `namespace_mode` (default `True`) and `selective_names`; supports all three import modes (namespace, selective, legacy)
- **`type_name()` updated** — `MyLangNamespace` returns `"module:name"` from `type_of()`
- **`import_test.my` updated** — rewritten to use Phase 6 namespace syntax throughout
- **New example files** — `mathlib.my` (with explicit exports), `greetlib.my` (no exports — all public), `namespace_test.my`

---

## v0.9.0

### Language Runtime — Phase 5: Object System / Classes

- **`class / init / method / end` syntax** — full class definition support
- **`ClassNode`** — new AST node representing a class definition (name, constructor params, init body, methods dict)
- **`MethodCallNode`** — new AST node for `obj.method(args)` expressions
- **`PropertyAccessNode`** — new AST node for `obj.property` read access
- **`PropertyAssignNode`** — new AST node for `obj.property = value` and `this.property = value`
- **`MyLangObject`** — new runtime class wrapping a `ClassNode` and an instance property dict
- **`_call_method()`** — new interpreter method; binds `this`, runs method body, restores caller scope; fully integrated with Phase 4 call stack tracing
- **Class instantiation** — calling a class name like a function (`Player("Jeremy", 100)`) creates a `MyLangObject` and runs the `init` body
- **`this` reference** — inside `init` and `method` bodies, `this` refers to the current instance; properties are read and written via `this.name`
- **Object mutation** — properties can be updated inside methods (`this.hp = this.hp - amount`) and from outside (`p.hp = 50`)
- **`type_of(obj)`** returns the class name (e.g. `"Player"`) for object instances
- **Objects in collections** — objects can be stored in lists and dictionaries
- **`METHOD_CALL` lexer token** — standalone `obj.method(args)` lines on their own produce this token
- **`PROP_ASSIGN` lexer token** — `obj.prop = value` lines produce this token
- **`CLASS`, `INIT`, `METHOD` lexer tokens** — new token types for class block parsing

### Parser Bug Fixes (shipped alongside Phase 5)

- **`then` keyword stripping** — the lexer now strips the optional trailing `then` from `if` and `while` conditions; `if x < y then` and `if x < y` now produce identical token values and ASTs
- **Boolean literals `true` / `false`** — now parsed as proper boolean values in `parse_primary`; previously fell through to `VariableNode` causing `Undefined variable: true` errors
- **Left-associative binary expressions** — `find_operator_outside` now scans right-to-left so `a + b + c` produces `(a + b) + c` instead of `a + (b + c)`
- **Function call name validation** — `parse_primary` now validates the function name is a plain identifier before treating an expression as a call; prevents `"rolled" + to_str` from being interpreted as a function name in chained string concatenation
- **Return propagation inside control flow** — `return` inside `if`, `while`, `for`, and `foreach` blocks now correctly halts the enclosing function; previously the outer body continued executing after the return, overwriting the return value
- **`_find_dot_outside()` helper** — new parser method finds the first `.` outside strings and brackets for property/method expression detection

### Standardisation (shipped alongside Phase 5)

- **Parentheses required for all function calls** — `greet "Jeremy"` now raises a clear `SyntaxError` with a suggestion: `greet("Jeremy")`; previously produced a generic `Unknown syntax` error
- **`print(...)` style accepted** — `print("hello")` is now reclassified as a `PRINT` token so both `print "hello"` and `print("hello")` work identically
- **BASIC-style call detection** — the lexer's `UNKNOWN` fallback now detects `identifier whitespace args` patterns and raises a specific error with the corrected parenthesized form
- **`MyLangSyntaxError` now raised by lexer** — previously the lexer raised bare `Exception`; now always raises `MyLangSyntaxError` so errors feed into the Phase 4 traceback formatter

### Lint / Code Quality

- **`# ruff: noqa: F403, F405`** added to `ast_interpreter.py` and `parser.py` above the `from ast_nodes import *` wildcard import to suppress ruff F403/F405 lint errors on GitHub CI

---

## v0.8.0

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

---

## v1.2.0

### REPL — Phase 8a: Advanced REPL System

- **Full rewrite of `repl.py`** — 674 lines replacing the original 100-line prototype; now a true interactive development environment
- **`ReplSession` class** — holds all persistent REPL state; a single `ASTInterpreter` instance lives for the entire session so variables, functions, classes, namespaces, and imported modules all survive between evaluations
- **Persistent scope** — variables, functions, classes, objects, and namespaces defined in one input are available in all subsequent inputs
- **Multiline block support** — if / else / while / for / foreach / function / class blocks are collected automatically using a depth counter; `..` prompt shown during continuation; nested blocks handled correctly
- **Command history** — arrow-key history via `readline`; saved to `~/.mylang/repl_history` across sessions; `readline.set_history_length(500)`
- **Tab autocomplete** — `ReplCompleter` provides completions for: REPL commands, all built-in functions, session variables, functions, class names, namespace names, and dot-notation namespace members (`utils.<tab>`)
- **`:variables`** — lists all current session variables with pretty-printed values
- **`:functions`** — lists all user-defined functions with parameter signatures and definition lines
- **`:classes`** — lists all defined classes with constructor params and method names
- **`:modules`** — lists all imported namespaces and their exported names
- **`:history`** — shows all commands entered this session
- **`:ast`** — toggles AST display mode; shows the parse tree for every input before executing
- **`:bytecode`** — toggles bytecode display mode; shows compiled instructions before executing
- **`:opt`** — toggles optimiser display mode; shows original AST, optimised AST, and fold statistics
- **`:vm on/off`** — switches execution backend between the AST interpreter and the bytecode VM
- **`:reset`** — clears all session state (variables, functions, classes, namespaces, history)
- **`:clear`** — clears the terminal screen
- **`:help`** — shows a formatted command reference table with current mode status
- **`:quit`** — exits the REPL (also `Ctrl-D`)
- **`Ctrl-C`** — cancels current input without ending the session
- **Error recovery** — all `MyLangRuntimeError` and `MyLangSyntaxError` exceptions are caught and displayed with full formatted tracebacks; session state is fully preserved after any error
- **`pretty()` function** — custom formatter for lists (compact for short, multiline for long), dicts, `MyLangObject` (shows class name and all properties), `MyLangNamespace` (shows alias and exports), and booleans (`true`/`false`)
- **Welcome banner** — box-drawn banner showing version, available commands, and keyboard shortcuts
- **`~/.mylang/`** — home directory is created automatically on first launch for history and future config storage

---

## v1.3.0

### Source Maps & Runtime Debug Mapping — Phase 8b

#### `source_map.py` (new file — 288 lines)

- **`SourceLocation`** — dataclass mapping one bytecode instruction index back to its source origin: `instruction_idx`, `source_file`, `line`, `ast_node_type`, `was_optimised`, `origin_line`
- **`SourceMap`** — lookup table from instruction index → `SourceLocation`; built by the `Compiler` as it emits instructions; travels with the `Chunk` it belongs to; methods: `record()`, `get()`, `lookup_line()`, `lookup_file()`, `all_entries()`, `summary()`
- **`VMTraceFrame`** — one frame in a VM call-stack traceback: `chunk_name`, `source_file`, `line`, `instruction_idx`, `source_line_text`
- **`VMRuntimeError`** — VM runtime error with a full `frames` list, `source_file`, and `line`; has `format_traceback()` producing a professional boxed display with call stack and source line annotations
- **`format_vm_traceback()`** — renders a `VMRuntimeError` in the style: `at calculate()  game.my : 42  ▶  total = hp / 0`
- **`build_source_index()`** — splits source text into a list of lines for fast 1-based lookup
- **`source_line_text()`** — safely retrieves the text of a 1-based source line

#### `ast_nodes.py` changes

- **`source_file` field added to all 22 AST node types** — every node now accepts `source_file=None` and stores `self.source_file`; enables the compiler to carry file origin through the full AST → bytecode pipeline
- Compact `__init__` signatures in `ExportNode` and `FromImportNode` also updated

#### `compiler.py` changes

- **`Instruction` extended** — two new fields: `source_file: str` and `ast_node_type: str`; every emitted instruction now carries its origin file and the AST node type that produced it
- **`Chunk` extended** — `source_file` constructor parameter; `source_map: SourceMap` instance built alongside the instruction list; `disassemble()` now shows `filename:line <NodeType> [opt]` annotations on every instruction
- **`Chunk.emit()` extended** — new parameters: `source_file`, `ast_node_type`, `was_optimised`, `origin_line`; records every emission in the source map automatically
- **`Compiler(source_file=)` parameter** — compiler now accepts the source file path and propagates it to all emitted instructions and sub-chunks
- **`Compiler._emit()` helper** — new method that wraps `chunk.emit()` and extracts `line`, `source_file`, `ast_node_type`, `_was_optimised`, and `_origin_line` from AST nodes automatically; all statement and expression compile methods updated to use `_emit` instead of `chunk.emit`

#### `optimizer.py` changes

- **`_make_literal()` extended** — now accepts `origin_line` parameter and attaches `_origin_line` and `_was_optimised = True` to every folded literal node; enables the compiler to tag constant-folded instructions as `[opt]` in the source map and disassembly
- All five `_make_literal()` call sites updated to pass `origin_line=node.line`

#### `vm.py` changes

- **`VMRuntimeError` imported from `source_map`** — VM no longer raises bare Python `NameError`/`RuntimeError`/`AttributeError`; all errors go through `_make_error()` which builds a full `VMRuntimeError` with source-mapped frames
- **`VM._current_line` and `VM._current_file`** — new state fields updated on every instruction fetch; always reflect the source location of the currently executing instruction
- **`VM._source_lines`** — dict mapping file path → list of source lines; populated via `vm.load_source(source, file_path)`; used by `_make_error()` to include source line text in traceback frames
- **`VM._make_error()`** — new method; walks the current call stack, looks up each frame's source location from its chunk's `SourceMap`, and constructs a `VMRuntimeError` with one `VMTraceFrame` per call frame
- **`VM._run()` updated** — updates `_current_line`/`_current_file` before each dispatch; wraps handler calls in `try/except` to catch all errors and re-raise as `VMRuntimeError` with source context
- **`VM.load_source()`** — new public method to cache source text for traceback display

---

## v1.4.0

### Phase 9: Serialization & Data Formats

#### `json_parser.py` (new file — 435 lines)

- **`JSONParseError`** — exception class with `message`, `line` (1-based), and `column` (1-based) attributes; `format()` method returns a boxed human-readable error display
- **`_JSONLexer`** — tokenises raw JSON text into `_Token` objects; tracks line and column throughout; token kinds: `LBRACE`, `RBRACE`, `LBRACKET`, `RBRACKET`, `COLON`, `COMMA`, `STRING`, `NUMBER`, `BOOL`, `NULL`, `EOF`
- **`_JSONParser`** — recursive descent parser over the token list; produces native Python/MYTH values; methods: `_parse_value()`, `_parse_object()`, `_parse_array()`
- **`parse_json(text)`** — public API; converts JSON text to MYTH runtime structures; raises `JSONParseError` with line/column on malformed input
- Full escape sequence support: `\"`, `\\`, `\/`, `\b`, `\f`, `\n`, `\r`, `\t`, `\uXXXX` unicode escapes
- Trailing comma detection with clear error messages
- Whole-number floats (e.g. `3.0`) coerced to `int` for MYTH compatibility
- Empty string and non-string input rejected with descriptive errors

**JSON → MYTH type mappings:**

| JSON | MYTH |
|:---|:---|
| object `{}` | `dict` |
| array `[]` | `list` |
| string | `str` |
| integer | `int` |
| float (whole) | `int` |
| float (fractional) | `float` |
| `true` | `True` |
| `false` | `False` |
| `null` | `None` |

#### `json_serializer.py` (new file — 254 lines)

- **`SerializationError`** — exception class with `message` attribute; `format()` returns a boxed error display
- **`_Serializer`** — internal serializer class; tracks seen object `id()`s for circular reference detection; supports `pretty=True` with 2-space indentation
- **`to_json(value, pretty=False)`** — public API; converts MYTH runtime value to JSON string
- Supports: `dict`, `list`, `str`, `int`, `float`, `bool`, `None`, `MyLangObject` (serialized as `{"__class__": "ClassName", ...properties}`)
- **Circular reference detection** — tracks all `dict`, `list`, and `MyLangObject` ids; raises `SerializationError` with "Circular reference detected" on cycles
- **String escaping** — handles `"`, `\`, and all control characters including `\uXXXX` for Unicode below 0x20
- **`MyLangNamespace` rejection** — raises `SerializationError` with a descriptive message
- **Non-string key detection** — raises `SerializationError` for dicts with non-string keys
- **Pretty format** — 2-space indentation, one entry per line, matching standard JSON formatting tools

#### `ast_interpreter.py` — 4 new built-in functions

- **`parse_json(text)`** — calls `json_parser.parse_json()`; wraps `JSONParseError` as `MyLangRuntimeError` with line/column context; validates input is STRING
- **`to_json(value)`** / **`to_json(value, pretty)`** — variadic (1–2 args); calls `json_serializer.to_json()`; wraps `SerializationError` as `MyLangRuntimeError`
- **`save_json(path, value)`** — serializes value to pretty JSON and writes to path; uses the existing `_resolve_file_path()` sandbox; creates intermediate directories automatically
- **`load_json(path)`** — reads a file using the existing sandbox, then parses with `json_parser.parse_json()`; raises `MyLangRuntimeError` with filename and line number on parse failure

#### New example file: `examples/json_test.my`

Covers: `to_json` (compact and pretty), `parse_json` round-trip, nested data structures, `save_json`/`load_json` with file persistence, nested `save_json`/`load_json` round-trip.
