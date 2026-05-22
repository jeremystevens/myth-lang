# ruff: noqa: F403, F405
"""
repl.py — MYTH Lang Advanced REPL  (Phase 8a)
==============================================
A modern interactive development environment for rapid
experimentation, debugging, and runtime inspection.

Features
────────
  Persistent scope       — variables, functions, classes, objects,
                           and namespaces survive between evaluations
  Multiline input        — if / while / for / foreach / function /
                           class blocks collected automatically
  Command history        — arrow-key navigation; saved to
                           ~/.mylang/repl_history across sessions
  Autocomplete           — Tab-completion for builtins, variables,
                           functions, classes, and namespaces
  Live inspection        — :variables  :functions  :classes  :modules
  AST mode               — :ast  shows the parse tree before running
  Bytecode mode          — :bytecode  shows compiled instructions
  Optimiser mode         — :opt  shows before/after AST + fold stats
  VM mode                — :vm on/off  switches execution backend
  Error recovery         — parser/runtime errors never end the session
  Pretty printing        — formatted output for objects and namespaces

Commands
────────
  :help          Show this help
  :quit          Exit the REPL
  :reset         Clear all session state
  :clear         Clear the terminal screen
  :variables     List all session variables
  :functions     List all defined functions
  :classes       List all defined classes
  :modules       List all imported namespaces
  :ast           Toggle AST display mode
  :bytecode      Toggle bytecode display mode
  :opt           Toggle optimiser display mode
  :vm on/off     Switch between AST interpreter and VM executor
  :history       Show command history for this session
"""

import os
import sys
import pathlib

# ── readline for history + autocomplete ──────────────────────────────────────
try:
    import readline
    import rlcompleter
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

# ── MyLang runtime ───────────────────────────────────────────────────────────
IDE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, IDE_DIR)

from lexer import Lexer
from parser import Parser
from ast_interpreter import ASTInterpreter, MyLangObject, MyLangNamespace
from optimizer import ASTOptimiser
from compiler import Compiler
from vm import VM
from runtime_error import MyLangRuntimeError
from parser_error import MyLangSyntaxError

# ── Constants ────────────────────────────────────────────────────────────────

VERSION      = "1.1.0"
REPL_VERSION = "Phase 8a"
HISTORY_FILE = pathlib.Path.home() / ".mylang" / "repl_history"
SCRIPT_DIR   = IDE_DIR

BANNER = f"""
╔══════════════════════════════════════════════════════════╗
║           MYTH Lang  v{VERSION}  —  Interactive REPL          ║
║                      {REPL_VERSION}                         ║
╠══════════════════════════════════════════════════════════╣
║  Type MyLang code and press Enter to run it.             ║
║  Use :help for commands  ·  Tab for autocomplete         ║
║  Arrow keys for history  ·  :quit to exit                ║
╚══════════════════════════════════════════════════════════╝
"""

# Keywords that open a block (increase depth)
BLOCK_OPENERS = {
    "if", "else", "while", "for", "foreach", "function", "class"
}

# All built-in function names (for autocomplete + :help)
BUILTIN_NAMES = [
    "upper", "lower", "length", "trim", "replace", "split",
    "contains", "starts_with", "ends_with", "repeat_str", "reverse",
    "abs", "max", "min", "pow", "floor", "ceil", "sqrt", "clamp", "random",
    "append", "remove", "first", "last", "reverse_list", "slice",
    "contains_item", "sort", "index_of", "flatten",
    "keys", "values", "exists", "get", "delete", "merge",
    "to_int", "to_str", "to_bool", "type_of",
    "input", "read_file", "write_file", "append_file",
    "file_exists", "delete_file",
]


# ===========================================================================
# PRETTY PRINTER
# ===========================================================================

def pretty(value, indent: int = 0) -> str:
    """Format a MyLang runtime value for display."""
    pad = "  " * indent

    if isinstance(value, MyLangObject):
        lines = [f"<{value.class_def.name}>"]
        for k, v in value.properties.items():
            lines.append(f"{pad}  .{k} = {pretty(v, indent + 1)}")
        return "\n".join(lines)

    if isinstance(value, MyLangNamespace):
        exports = list(value.exports.keys())
        return f"<module '{value.name}' exports={exports}>"

    if isinstance(value, list):
        if not value:
            return "[]"
        if len(value) <= 6 and all(
            not isinstance(v, (list, dict, MyLangObject)) for v in value
        ):
            return "[" + ", ".join(repr(v) for v in value) + "]"
        lines = ["["]
        for item in value:
            lines.append(f"{pad}  {pretty(item, indent + 1)},")
        lines.append(f"{pad}]")
        return "\n".join(lines)

    if isinstance(value, dict):
        if not value:
            return "{}"
        lines = ["{"]
        for k, v in value.items():
            lines.append(f"{pad}  {k!r}: {pretty(v, indent + 1)},")
        closing = pad + "}"
        lines.append(closing)
        return "\n".join(lines)

    if isinstance(value, bool):
        return "true" if value else "false"

    return repr(value)


# ===========================================================================
# AUTOCOMPLETE
# ===========================================================================

class ReplCompleter:
    """
    Tab-completion for the REPL.
    Completes: built-ins, REPL commands, session variables,
    functions, class names, namespace names, and dot-notation
    for namespace members.
    """

    COMMANDS = [
        ":help", ":quit", ":reset", ":clear",
        ":variables", ":functions", ":classes", ":modules",
        ":ast", ":bytecode", ":opt",
        ":vm on", ":vm off", ":history",
    ]

    def __init__(self, session: "ReplSession"):
        self.session = session

    def complete(self, text: str, state: int):
        if state == 0:
            self._matches = self._build_matches(text)
        try:
            return self._matches[state]
        except IndexError:
            return None

    def _build_matches(self, text: str) -> list:
        matches = []

        # Dot-notation:  namespace.func  or  obj.prop
        if "." in text:
            prefix, attr = text.rsplit(".", 1)
            # Check if prefix is a known namespace
            ns = self.session.interp._namespaces.get(prefix)
            if ns:
                for name in ns.exports:
                    if name.startswith(attr):
                        matches.append(f"{prefix}.{name}")
            return matches

        # REPL commands
        for cmd in self.COMMANDS:
            if cmd.startswith(text):
                matches.append(cmd)

        # Built-ins
        for name in BUILTIN_NAMES:
            if name.startswith(text):
                matches.append(name)

        # Session variables
        for name in self.session.interp.variables:
            if name.startswith(text) and not name.startswith("__"):
                matches.append(name)

        # Functions
        for name in self.session.interp.functions:
            if name.startswith(text):
                matches.append(name)

        # Namespace names (for dot-notation prefix)
        for name in self.session.interp._namespaces:
            if name.startswith(text):
                matches.append(name + ".")

        return sorted(set(matches))


# ===========================================================================
# REPL SESSION  (persistent state)
# ===========================================================================

class ReplSession:
    """
    Holds all state for one REPL session:
      - a single persistent ASTInterpreter
      - mode flags (ast, bytecode, opt, vm)
      - command history for :history display
    """

    def __init__(self):
        self.interp    = ASTInterpreter(
            module_search_paths=[SCRIPT_DIR],
            file_root=SCRIPT_DIR,
        )
        self.optimiser = ASTOptimiser()
        self.compiler  = Compiler()

        # Mode flags
        self.mode_ast      = False
        self.mode_bytecode = False
        self.mode_opt      = False
        self.mode_vm       = False

        # Session history (list of (input_str, result_str) )
        self._history : list = []

    def reset(self):
        """Clear all session state."""
        self.interp = ASTInterpreter(
            module_search_paths=[SCRIPT_DIR],
            file_root=SCRIPT_DIR,
        )
        self.optimiser = ASTOptimiser()
        self._history  = []

    # ── Execute one block of MyLang code ──────────────────────────────────

    def evaluate(self, code: str) -> None:
        """
        Parse, optionally display diagnostics, then execute.
        All errors are caught and displayed without ending the session.
        """
        self._history.append(code)

        # Lex
        try:
            tokens = Lexer(code).tokenize()
        except MyLangSyntaxError as e:
            print(e.format_traceback(code.splitlines()))
            return

        # Parse
        try:
            ast = Parser(tokens).parse()
        except MyLangSyntaxError as e:
            print(e.format_traceback(code.splitlines()))
            return
        except Exception as e:
            _print_internal(e)
            return

        # ── Opt mode: show before/after ──────────────────────────────
        if self.mode_opt:
            self.optimiser = ASTOptimiser()
            print()
            _section("ORIGINAL AST")
            for node in ast:
                print(f"  {node}")
            opt_ast = self.optimiser.optimise(ast)
            _section("OPTIMISED AST")
            for node in opt_ast:
                print(f"  {node}")
            _section("STATS")
            print(f"  {self.optimiser.report().strip()}")
            print()
            ast = opt_ast

        elif self.mode_bytecode or self.mode_vm:
            # Always optimise before compiling
            ast = self.optimiser.optimise(ast)

        elif not self.mode_opt:
            # Default: always optimise silently
            ast = self.optimiser.optimise(ast)

        # ── AST mode ─────────────────────────────────────────────────
        if self.mode_ast:
            print()
            _section("AST")
            for node in ast:
                print(f"  {node}")
            print()

        # ── Bytecode mode ─────────────────────────────────────────────
        if self.mode_bytecode:
            try:
                chunk = self.compiler.compile(ast)
                print()
                _section("BYTECODE")
                print(chunk.disassemble())
                print()
            except Exception as e:
                print(f"  [compiler error: {e}]")

        # ── Execute ───────────────────────────────────────────────────
        if self.mode_vm:
            self._run_vm(ast, code)
        else:
            self._run_interp(ast, code)

    def _run_interp(self, ast, code: str):
        """Execute on the persistent AST interpreter."""
        self.interp.set_source(code)
        try:
            self.interp.run(ast)
        except MyLangRuntimeError as e:
            self.interp._enrich_error(e)
            print(e.format_traceback(code.splitlines()))
        except Exception as e:
            _print_internal(e)

    def _run_vm(self, ast, code: str):
        """Compile and execute on a fresh VM instance."""
        try:
            chunk = self.compiler.compile(ast)
            vm    = VM()
            # Seed VM with session variables and functions
            vm.globals.update(self.interp.variables)
            for fname, fnode in self.interp.functions.items():
                vm.functions[fname] = fnode
            vm.execute(chunk)
        except Exception as e:
            _print_internal(e)

    # ── Inspection commands ───────────────────────────────────────────────

    def show_variables(self):
        """Display all current session variables."""
        skip = {"__builtins__"}
        vars_ = {
            k: v for k, v in self.interp.variables.items()
            if k not in skip and not k.startswith("__")
        }
        if not vars_:
            print("  (no variables defined)")
            return
        print()
        _section("VARIABLES")
        for name, value in sorted(vars_.items()):
            print(f"  {name} = {pretty(value)}")
        print()

    def show_functions(self):
        """Display all user-defined functions."""
        from ast_nodes import FunctionNode
        fns = {
            k: v for k, v in self.interp.functions.items()
            if isinstance(v, FunctionNode)
        }
        if not fns:
            print("  (no functions defined)")
            return
        print()
        _section("FUNCTIONS")
        for name, node in sorted(fns.items()):
            params = ", ".join(node.params)
            print(f"  function {name}({params})  — line {node.line}")
        print()

    def show_classes(self):
        """Display all defined classes."""
        from ast_nodes import ClassNode
        classes = {
            k: v for k, v in self.interp.functions.items()
            if isinstance(v, ClassNode)
        }
        if not classes:
            print("  (no classes defined)")
            return
        print()
        _section("CLASSES")
        for name, node in sorted(classes.items()):
            params  = ", ".join(node.params)
            methods = ", ".join(node.methods.keys())
            print(f"  class {name}({params})")
            if methods:
                print(f"    methods: {methods}")
        print()

    def show_modules(self):
        """Display all imported namespaces."""
        ns = self.interp._namespaces
        if not ns:
            print("  (no modules imported)")
            return
        print()
        _section("MODULES")
        for alias, namespace in sorted(ns.items()):
            exports = list(namespace.exports.keys())
            print(f"  {alias}  →  {exports}")
        print()

    def show_history(self):
        """Display commands entered this session."""
        if not self._history:
            print("  (no history)")
            return
        print()
        _section("SESSION HISTORY")
        for i, entry in enumerate(self._history, 1):
            first_line = entry.splitlines()[0]
            print(f"  {i:3d}  {first_line}")
        print()


# ===========================================================================
# HELPERS
# ===========================================================================

def _section(title: str):
    print(f"  ── {title} {'─' * max(0, 44 - len(title))}")

def _print_internal(e: Exception):
    import traceback
    print(f"\n  INTERNAL ERROR: {e}")
    print(f"  {traceback.format_exc().splitlines()[-1]}\n")

def _clear_screen():
    os.system("cls" if sys.platform == "win32" else "clear")


# ===========================================================================
# INPUT COLLECTION  (multiline block support)
# ===========================================================================

BLOCK_OPENERS_STARTSWITH = tuple(BLOCK_OPENERS)

def _block_depth_change(line: str) -> int:
    """Return +1 if the line opens a block, -1 if it closes one, else 0."""
    stripped = line.strip().lower()
    first    = stripped.split()[0] if stripped.split() else ""

    if first in BLOCK_OPENERS:
        return +1
    if first == "end":
        return -1
    return 0

def collect_input(prompt_first: str = ">> ", prompt_cont: str = ".. ") -> str:
    """
    Collect one complete unit of input from the user.
    Handles multiline blocks by tracking depth.
    Returns the joined source string, or raises EOFError on Ctrl-D.
    """
    lines = []
    depth = 0

    first_line = input(prompt_first).strip()
    lines.append(first_line)
    depth += _block_depth_change(first_line)

    while depth > 0:
        line = input(prompt_cont).strip()
        lines.append(line)
        depth += _block_depth_change(line)
        depth  = max(0, depth)   # guard against stray 'end'

    return "\n".join(lines)


# ===========================================================================
# COMMAND DISPATCHER
# ===========================================================================

def handle_command(raw: str, session: ReplSession) -> bool:
    """
    Handle a REPL : command.
    Returns True if the command was handled (even if it was :quit).
    Returns False if the input is not a command.
    """
    cmd = raw.strip().lower()

    if not cmd.startswith(":"):
        return False

    # ── :quit / :exit ────────────────────────────────────────────────────
    if cmd in (":quit", ":exit", ":q"):
        print("\n  Goodbye!\n")
        sys.exit(0)

    # ── :help ─────────────────────────────────────────────────────────────
    if cmd == ":help":
        print(f"""
  ┌─────────────────────────────────────────────────────┐
  │             MYTH Lang REPL — Commands               │
  ├─────────────────────────────────────────────────────┤
  │  :help          Show this help                      │
  │  :quit          Exit the REPL                       │
  │  :reset         Clear all session state             │
  │  :clear         Clear the terminal screen           │
  ├─────────────────────────────────────────────────────┤
  │  :variables     List all session variables          │
  │  :functions     List all defined functions          │
  │  :classes       List all defined classes            │
  │  :modules       List all imported namespaces        │
  │  :history       Show command history                │
  ├─────────────────────────────────────────────────────┤
  │  :ast           Toggle AST display mode             │
  │  :bytecode      Toggle bytecode display mode        │
  │  :opt           Toggle optimiser display mode       │
  │  :vm on|off     Switch execution backend            │
  └─────────────────────────────────────────────────────┘
  Current modes:
    AST      = {"ON" if session.mode_ast else "off"}
    Bytecode = {"ON" if session.mode_bytecode else "off"}
    Opt      = {"ON" if session.mode_opt else "off"}
    VM       = {"ON" if session.mode_vm else "off"}
""")
        return True

    # ── :reset ────────────────────────────────────────────────────────────
    if cmd == ":reset":
        session.reset()
        print("  Session reset — all variables, functions, and classes cleared.")
        return True

    # ── :clear ────────────────────────────────────────────────────────────
    if cmd == ":clear":
        _clear_screen()
        return True

    # ── Inspection ────────────────────────────────────────────────────────
    if cmd == ":variables": session.show_variables(); return True
    if cmd == ":functions": session.show_functions(); return True
    if cmd == ":classes":   session.show_classes();   return True
    if cmd == ":modules":   session.show_modules();   return True
    if cmd == ":history":   session.show_history();   return True

    # ── Mode toggles ──────────────────────────────────────────────────────
    if cmd == ":ast":
        session.mode_ast = not session.mode_ast
        state = "ON" if session.mode_ast else "off"
        print(f"  AST mode: {state}")
        return True

    if cmd == ":bytecode":
        session.mode_bytecode = not session.mode_bytecode
        state = "ON" if session.mode_bytecode else "off"
        print(f"  Bytecode mode: {state}")
        return True

    if cmd == ":opt":
        session.mode_opt = not session.mode_opt
        state = "ON" if session.mode_opt else "off"
        print(f"  Optimiser mode: {state}")
        return True

    if cmd in (":vm on", ":vm"):
        session.mode_vm = True
        print("  VM mode: ON  (executing via bytecode VM)")
        return True

    if cmd == ":vm off":
        session.mode_vm = False
        print("  VM mode: off  (executing via AST interpreter)")
        return True

    # ── Unknown command ───────────────────────────────────────────────────
    print(f"  Unknown command: {raw.strip()}  (type :help for commands)")
    return True


# ===========================================================================
# READLINE SETUP
# ===========================================================================

def setup_readline(session: ReplSession):
    if not READLINE_AVAILABLE:
        return

    # History
    readline.set_history_length(500)

    history_path = HISTORY_FILE
    history_path.parent.mkdir(parents=True, exist_ok=True)

    if history_path.exists():
        try:
            readline.read_history_file(str(history_path))
        except OSError:
            pass

    import atexit
    atexit.register(
        lambda: readline.write_history_file(str(history_path))
    )

    # Autocomplete
    completer = ReplCompleter(session)
    readline.set_completer(completer.complete)
    readline.set_completer_delims(" \t\n;")

    if sys.platform == "darwin":
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")


# ===========================================================================
# MAIN LOOP
# ===========================================================================

def main():
    print(BANNER)

    session = ReplSession()
    setup_readline(session)

    while True:
        try:
            code = collect_input()
        except EOFError:
            # Ctrl-D
            print("\n\n  Goodbye!\n")
            break
        except KeyboardInterrupt:
            # Ctrl-C — cancel current input, start fresh
            print()
            continue

        if not code.strip():
            continue

        # REPL command?
        if code.strip().startswith(":"):
            handle_command(code.strip(), session)
            continue

        # Legacy exit/help
        if code.strip().lower() == "exit":
            print("\n  Goodbye!\n")
            break

        # Execute
        session.evaluate(code)


if __name__ == "__main__":
    main()
