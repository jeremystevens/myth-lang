# MyLang Roadmap

Current version: **0.8.0**

This roadmap tracks what has been completed and what is planned. Items are grouped by category and marked with their current status.

---

## Language Runtime

### ✅ Complete

| Feature | Added in |
|:---|:---|
| Variables (integer, string, boolean) | v0.1.0 |
| Arithmetic operators `+ - * / %` | v0.1.0 |
| Comparison operators `== > <` | v0.1.0 |
| Logical operators `and or not` | v0.1.0 |
| `print` statement | v0.1.0 |
| `if / else / end` blocks | v0.1.0 |
| `while` loops | v0.1.0 |
| `for i = N to M` loops | v0.1.0 |
| `foreach item in list` loops | v0.1.0 |
| User-defined functions with parameters and return values | v0.1.0 |
| Lists with index access and index assignment | v0.1.0 |
| Dictionaries with key access and key assignment | v0.1.0 |
| Core built-in functions (upper, lower, length, append, remove, random, keys, values, exists) | v0.1.0 |
| AST-based interpreter (lexer → parser → AST → execution pipeline) | v0.1.0 |
| String built-ins: trim, replace, split, contains, starts_with, ends_with, repeat_str, reverse | v0.6.0 |
| Math built-ins: abs, max, min, pow, floor, ceil, sqrt, clamp | v0.6.0 |
| List built-ins: first, last, reverse_list, slice, contains_item, sort, index_of, flatten | v0.6.0 |
| Dictionary built-ins: delete, merge, get | v0.6.0 |
| Type conversion: to_int, to_str, to_bool, type_of | v0.6.0 |
| `input()` with optional prompt | v0.6.0 |
| Negative number literals (`-42`) | v0.6.0 |
| `\n`, `\t`, `\\` escape sequences in strings | v0.7.0 |
| Module import system (`import filename`) | v0.5.0 |
| Import caching (each file executed once per run) | v0.5.0 |
| Circular import protection | v0.5.0 |
| File I/O: read_file, write_file, append_file, file_exists, delete_file | v0.7.0 |
| File I/O path sandbox safety | v0.7.0 |
| Structured runtime tracebacks with call stack | v0.8.0 |
| Source line display in error frames | v0.8.0 |
| Local variable snapshots in error frames | v0.8.0 |
| Module import chain tracing | v0.8.0 |
| Syntax error caret display | v0.8.0 |
| Debug hooks for IDE integration (`set_debug_controller`) | v0.2.0 |

### 🔲 Planned — Language

| Feature | Priority | Notes |
|:---|:---:|:---|
| `>=` and `<=` comparison operators | High | Missing from the parser's operator list |
| `elif` chains | High | Currently requires nested `if / else / end` |
| `break` and `continue` in loops | Medium | No early-exit mechanism yet |
| Float / decimal number support | Medium | Division currently always produces an integer result |
| String indexing (`s[0]`) | Medium | Only lists and dicts support index access |
| Error handling — `try / catch / end` | Medium | No way to recover from runtime errors in user code |
| `not=` or `!=` inequality operator | Low | Currently must use `not (a == b)` |
| Multi-line expressions | Low | All statements must fit on one line |
| Lambda / anonymous functions | Low | Functions require a name |
| String interpolation | Low | Currently use `+` concatenation with `to_str()` |

---

## Standard Library

### ✅ Complete

| Category | Functions |
|:---|:---|
| String | upper, lower, length, trim, replace, split, contains, starts_with, ends_with, repeat_str, reverse |
| Math | abs, max, min, pow, floor, ceil, sqrt, clamp, random |
| List | append, remove, first, last, reverse_list, slice, contains_item, sort, index_of, flatten |
| Dictionary | keys, values, exists, get, delete, merge |
| Type Conversion | to_int, to_str, to_bool, type_of |
| I/O | input |
| File I/O | read_file, write_file, append_file, file_exists, delete_file |

### 🔲 Planned — Standard Library

| Function | Category | Description |
|:---|:---|:---|
| `join(list, delim)` | String | Join list elements into a string |
| `pad_left(s, n)` / `pad_right(s, n)` | String | Pad string to length `n` |
| `count(list, item)` | List | Count occurrences of item |
| `zip(a, b)` | List | Pair elements from two lists |
| `range(start, end, step)` | List | Generate a list of numbers |
| `round(n)` | Math | Round to nearest integer (when floats are added) |
| `sum(list)` | Math | Sum all numbers in a list |
| `now()` | I/O | Return current timestamp string |
| `env(name)` | I/O | Read an environment variable |
| `json_parse(s)` | Data | Parse a JSON string into a dict/list |
| `json_format(v)` | Data | Format a dict/list as a JSON string |

---

## IDE

### ✅ Complete

| Phase | Features |
|:---|:---|
| **Phase 1** | Core editor · Three themes (Dark / Light / QBasic) · Run/Stop · Output console · File explorer dock · Status bar · Keyboard shortcuts |
| **Phase 2** | Syntax highlighting · Live lexer+parser analysis (400ms debounce) · Red squiggly error underlines · Token Viewer · AST Viewer · Error status indicator · Jump to Line (Ctrl+G) |
| **Phase 3** | Integrated debugger · Breakpoints (click gutter) · Step Over (F10) · Continue · Variable Inspector · Call Stack panel · Exception Viewer · Debug toolbar |
| **Phase 4** | Autocomplete popup · Function signature hints · Find References (Shift+F12) · Go to Definition (F12) · Code formatter (Shift+Alt+F) · Symbol panel · Right-click context menu |
| **Phase 5** | Package manager · Plugin system · Integrated terminal (tabbed with console) · Project templates · Export tools (Standalone / ZIP / Docs / JSON) |

### 🔲 Planned — IDE

| Feature | Description |
|:---|:---|
| AI-assisted suggestions | Context-aware completions beyond the symbol table |
| Multi-file project workspace | Tabbed editor for multiple open files simultaneously |
| Git integration | Show changed lines in the gutter; basic commit/diff UI |
| Cross-platform packaging | One-click installer for Windows/macOS/Linux |
| Search across files | Find/replace across all `.my` files in the project |
| `repeat` loop syntax | Restore the removed `repeat N ... end` convenience syntax |
| Settings panel | Persistent user preferences (font size, tab width, default theme) |
| REPL upgrade | Connect the REPL to the Phase 4 language services |

---

## Compiler / VM

### 🔲 Planned

| Feature | Description |
|:---|:---|
| Bytecode compiler | Compile AST to a compact instruction set |
| Stack-based VM | Execute bytecode rather than walking the AST |
| Bytecode serialisation | Save compiled `.myc` files to disk |
| Performance profiler | Measure time spent per function |
| Self-hosting | Rewrite the lexer and parser in MyLang itself |
| Native compiler | Compile to native code via LLVM or C intermediate |

---

## Ecosystem

### ✅ Complete

| Feature | Notes |
|:---|:---|
| Package manager | Local path and URL install; `~/.mylang/packages/` |
| Plugin system | Python plugins; `~/.mylang/plugins/` |
| Project templates | 6 built-in templates |
| Export tools | Standalone, ZIP, Markdown docs, JSON syntax report |
| Language specification | `docs/language-spec.md` |
| Beginner guide | `docs/beginner-guide.md` |
| Changelog | `docs/changelog.md` |

### 🔲 Planned — Ecosystem

| Feature | Description |
|:---|:---|
| Online package registry | Hosted index of community-published MyLang packages |
| `mylang install <name>` CLI | Command-line package installer |
| Language server protocol (LSP) | Enable any editor to use MyLang language services |
| Community plugin gallery | Curated list of IDE plugins |
| Interactive tutorial | Built-in walkthrough in the IDE for new users |

---

## Version History Summary

| Version | Focus |
|:---|:---|
| v0.1.0 | Core language — variables, control flow, functions, collections, AST interpreter |
| v0.5.0 | Module / import system |
| v0.6.0 | Standard library expansion (40+ built-ins) |
| v0.7.0 | File I/O, escape sequences |
| v0.8.0 | Error system expansion — structured tracebacks, call stack, import tracing |

