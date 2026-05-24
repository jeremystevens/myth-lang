# ruff: noqa: F403, F405
from ast_nodes import *

from runtime_error import (
    MyLangRuntimeError,
    TraceFrame,
)

import random
import os


# ===========================================================================
# PHASE 5 — MYLANG OBJECT RUNTIME
# ===========================================================================

class MyLangObject:
    """
    A runtime instance of a MyLang class.

    Attributes
    ----------
    class_def   : ClassNode  — the class this was instantiated from
    properties  : dict       — instance property bag  (this.x, this.hp …)
    """

    def __init__(self, class_def):
        self.class_def  = class_def
        self.properties = {}

    def __repr__(self):
        return (
            f"<{self.class_def.name} "
            f"{self.properties}>"
        )


# ===========================================================================
# PHASE 6 — NAMESPACE RUNTIME
# ===========================================================================

class MyLangNamespace:
    """
    Holds the public API of an imported module.

    When you write:

        import utils

    the interpreter executes utils.my in isolation, then wraps
    the exported functions/classes in a MyLangNamespace stored
    under the alias 'utils'.  You then call them as:

        utils.double(x)
        utils.Player("Jeremy", 100)

    Attributes
    ----------
    name     : str   — the module alias (stem of the file path)
    exports  : dict  — name → FunctionNode | ClassNode
    """

    def __init__(self, name: str, exports: dict):
        self.name    = name
        self.exports = exports

    def get(self, attr_name: str):
        if attr_name in self.exports:
            return self.exports[attr_name]
        raise KeyError(attr_name)

    def __repr__(self):
        return (
            f"<module '{self.name}' — "
            f"exports: {list(self.exports.keys())}>"
        )


class ASTInterpreter:

    def __init__(
        self,
        module_search_paths=None,
        file_root=None,
        _globals=None,
        _import_cache=None
    ):

        # -------------------------
        # SHARED GLOBAL RUNTIME STATE
        # -------------------------
        #
        # _globals and _import_cache are passed
        # down from a parent interpreter when a
        # module is loaded.  This gives all modules
        # access to the same function registry and
        # import cache so that:
        #   - Functions defined in a module are
        #     visible to the importer's scope.
        #   - The same file is never executed twice
        #     regardless of how many times it is
        #     imported (import caching).\
        #
        # When _globals is None this is the root
        # interpreter; it creates the shared dicts
        # that every child will reference.

        if _globals is None:
            # Root interpreter — owns the dicts
            self.functions    = {}
            self._import_cache= set()
        else:
            # Child (module) interpreter — shares
            # the parent's dicts by reference
            self.functions    = _globals
            self._import_cache= _import_cache or set()

        # Allow _import_cache to be shared even
        # when _globals is not (Phase 6 namespace mode)
        if _globals is None and _import_cache is not None:
            self._import_cache = _import_cache

        self.variables = {}
        self.return_value = None

        # -------------------------
        # PHASE 6 — NAMESPACES
        # -------------------------
        #
        # _namespaces maps module alias → MyLangNamespace.
        # Populated when `import utils` is executed in
        # namespace mode (Phase 6).  Shared with child
        # interpreters so nested imports see the same map.

        self._namespaces = {}

        # -------------------------
        # PHASE 4 — ERROR SYSTEM
        # -------------------------
        #
        # _call_stack is maintained on EVERY run,
        # not just during debug sessions.  This
        # gives us a full traceback on any runtime
        # error without needing the debugger.
        #
        # _source_lines caches the raw text lines
        # of the current script so TraceFrames can
        # show the actual source code.
        #
        # _import_stack tracks the chain of import
        # statements that led to the current module
        # being executed, so nested import errors
        # show the full chain.
        #
        # _current_file tracks which .my file is
        # executing in this interpreter instance.

        self._call_stack   = []   # list[TraceFrame]
        self._source_lines = []   # list[str] — raw lines of current src
        self._import_stack = []   # list[dict] — {path, line}
        self._current_file = None # str | None
        self._export_names = []   # list[str] — names declared with export

        # -------------------------
        # DEBUG HOOKS
        # -------------------------
        # Set by the IDE debug runner via
        # set_debug_controller().  None means
        # no debugging — zero overhead on normal
        # runs.

        self._debug_controller = None

        # Directories searched when resolving an
        # import path.  The caller may pass extra
        # paths; the current working directory is
        # always appended as the final fallback.
        self.module_search_paths = list(
            module_search_paths or []
        )

        if os.getcwd() not in self.module_search_paths:
            self.module_search_paths.append(
                os.getcwd()
            )

        # -------------------------
        # FILE IO ROOT
        # -------------------------
        #
        # All file IO operations are sandboxed to
        # this directory.  Any path that would
        # escape it (e.g. ../../etc/passwd) is
        # rejected at runtime before touching disk.
        #
        # Defaults to cwd so scripts work out of
        # the box.  main.py sets it to script_dir
        # so relative paths resolve next to the
        # running script.  Child interpreters
        # inherit the same root so modules share
        # the sandbox.

        self.file_root = os.path.abspath(
            file_root or os.getcwd()
        )

        self.builtins = {

            # -------------------------
            # STRING
            # -------------------------

            "upper": (
                self.builtin_upper,
                1
            ),

            "lower": (
                self.builtin_lower,
                1
            ),

            "length": (
                self.builtin_length,
                1
            ),

            "trim": (
                self.builtin_trim,
                1
            ),

            "replace": (
                self.builtin_replace,
                3
            ),

            "split": (
                self.builtin_split,
                2
            ),

            "contains": (
                self.builtin_contains,
                2
            ),

            "starts_with": (
                self.builtin_starts_with,
                2
            ),

            "ends_with": (
                self.builtin_ends_with,
                2
            ),

            "repeat_str": (
                self.builtin_repeat_str,
                2
            ),

            "reverse": (
                self.builtin_reverse,
                1
            ),

            # -------------------------
            # MATH
            # -------------------------

            "abs": (
                self.builtin_abs,
                1
            ),

            "max": (
                self.builtin_max,
                2
            ),

            "min": (
                self.builtin_min,
                2
            ),

            "pow": (
                self.builtin_pow,
                2
            ),

            "floor": (
                self.builtin_floor,
                1
            ),

            "ceil": (
                self.builtin_ceil,
                1
            ),

            "sqrt": (
                self.builtin_sqrt,
                1
            ),

            "clamp": (
                self.builtin_clamp,
                3
            ),

            "random": (
                self.builtin_random,
                2
            ),

            # -------------------------
            # LIST
            # -------------------------

            "append": (
                self.builtin_append,
                2
            ),

            "remove": (
                self.builtin_remove,
                2
            ),

            "first": (
                self.builtin_first,
                1
            ),

            "last": (
                self.builtin_last,
                1
            ),

            "reverse_list": (
                self.builtin_reverse_list,
                1
            ),

            "slice": (
                self.builtin_slice,
                3
            ),

            "contains_item": (
                self.builtin_contains_item,
                2
            ),

            "sort": (
                self.builtin_sort,
                1
            ),

            "index_of": (
                self.builtin_index_of,
                2
            ),

            "flatten": (
                self.builtin_flatten,
                1
            ),

            # -------------------------
            # DICTIONARY
            # -------------------------

            "keys": (
                self.builtin_keys,
                1
            ),

            "values": (
                self.builtin_values,
                1
            ),

            "exists": (
                self.builtin_exists,
                2
            ),

            "delete": (
                self.builtin_delete,
                2
            ),

            "merge": (
                self.builtin_merge,
                2
            ),

            "get": (
                self.builtin_get,
                3
            ),

            # -------------------------
            # TYPE CONVERSION
            # -------------------------

            "to_int": (
                self.builtin_to_int,
                1
            ),

            "to_str": (
                self.builtin_to_str,
                1
            ),

            "to_bool": (
                self.builtin_to_bool,
                1
            ),

            "type_of": (
                self.builtin_type_of,
                1
            ),

            # -------------------------
            # INPUT / OUTPUT
            # -------------------------

            # input() accepts 0 or 1 arguments.
            # With 0 args: reads a line silently.
            # With 1 arg:  prints the prompt first,
            #              then reads a line.
            "input": (
                self.builtin_input,
                0,
                1
            ),

            # -------------------------
            # FILE IO
            # -------------------------

            # read_file(path)
            #   Reads the entire file at path and
            #   returns its contents as a STRING.

            "read_file": (
                self.builtin_read_file,
                1
            ),

            # write_file(path, content)
            #   Writes content to path, creating
            #   the file if it does not exist and
            #   overwriting it if it does.
            #   Returns the number of bytes written.

            "write_file": (
                self.builtin_write_file,
                2
            ),

            # append_file(path, content)
            #   Appends content to path, creating
            #   the file if it does not exist.
            #   Returns the number of bytes written.

            "append_file": (
                self.builtin_append_file,
                2
            ),

            # file_exists(path)
            #   Returns true if the file exists and
            #   is a regular file, false otherwise.
            #   Never raises — safe to call on any
            #   path.

            "file_exists": (
                self.builtin_file_exists,
                1
            ),

            # delete_file(path)
            #   Deletes the file at path.
            #   Raises a runtime error if the file
            #   does not exist or cannot be removed.

            "delete_file": (
                self.builtin_delete_file,
                1
            ),

            # -------------------------
            # JSON  (Phase 9)
            # -------------------------

            # parse_json(text)
            #   Parse a JSON string into a MYTH
            #   dict, list, string, integer,
            #   boolean, or null.

            "parse_json": (
                self.builtin_parse_json,
                1
            ),

            # to_json(value)
            # to_json(value, pretty)
            #   Serialize a MYTH value to a JSON
            #   string.  Optional second argument
            #   enables pretty-printing.

            "to_json": (
                self.builtin_to_json,
                1,
                2
            ),

            # save_json(path, value)
            #   Serialize value to JSON and write
            #   it to path (sandbox rules apply).

            "save_json": (
                self.builtin_save_json,
                2
            ),

            # load_json(path)
            #   Read a JSON file and return the
            #   parsed MYTH value.

            "load_json": (
                self.builtin_load_json,
                1
            ),

        }

    # -------------------------
    # DEBUG CONTROLLER
    # -------------------------

    def set_debug_controller(self, controller):
        """
        Attach a DebugController from the IDE.
        Once set, run() will call controller.on_line()
        before executing every statement, allowing
        breakpoints and single-stepping.
        """
        self._debug_controller = controller

    # -------------------------
    # PHASE 4 — ERROR HELPERS
    # -------------------------

    def set_source(self, source: str, file_path: str = None):
        """
        Store the raw source text so TraceFrames
        can show the actual code lines when an
        error occurs.  Called by the top-level
        runner before interpreter.run().
        """
        self._source_lines = source.splitlines()
        self._current_file = file_path

    def _snapshot_locals(self) -> dict:
        """
        Return a shallow copy of the current
        variable scope for inclusion in a
        TraceFrame.  Truncates large values so
        the snapshot stays readable.
        """
        snap = {}
        for k, v in self.variables.items():
            snap[k] = v
        return snap

    def _source_line(self, line_num) -> str:
        """
        Return the raw text of a 1-based line
        number from the cached source, or None.
        """
        if (
            self._source_lines
            and line_num
            and 0 < line_num <= len(self._source_lines)
        ):
            return self._source_lines[line_num - 1]
        return None

    def _enrich_error(self, error: MyLangRuntimeError):
        """
        Attach the current call stack and import
        chain to a MyLangRuntimeError before it
        propagates to the caller.

        The call stack is reversed so the most
        recent frame comes first in the list
        (matching Python traceback conventions:
        outermost → innermost → error site).
        """
        if not error.traceback:
            # Build TraceFrames from _call_stack
            frames = []
            for frame_dict in self._call_stack:
                ln  = frame_dict.get("line", 0)
                src = self._source_line(ln)
                frames.append(TraceFrame(
                    kind            = "function",
                    name            = frame_dict.get("name", "?"),
                    line            = ln,
                    source_line     = src,
                    file_path       = self._current_file,
                    locals_snapshot = frame_dict.get("locals", {}),
                ))
            error.traceback    = frames
            error.import_chain = list(self._import_stack)

        return error

    # -------------------------
    # MODULE RESOLUTION
    # -------------------------

    def resolve_module_path(
        self,
        raw_path,
        line=None
    ):

        # Strip optional quotes so both
        #   import utils
        #   import "utils"
        # work identically.
        path = raw_path.strip().strip('"')

        # Append .my if the caller omitted it
        if not path.endswith(".my"):
            path = path + ".my"

        # Walk the search path list and return
        # the first file that actually exists.
        for directory in self.module_search_paths:

            candidate = os.path.join(
                directory,
                path
            )

            if os.path.isfile(candidate):
                return os.path.abspath(candidate)

        raise MyLangRuntimeError(
            f"Cannot find module: '{raw_path}' "
            f"(searched: "
            f"{self.module_search_paths})",
            line
        )

    def load_module(
        self,
        raw_path,
        line=None,
        namespace_mode=True,
        selective_names=None,
    ):
        """
        Load and execute a MyLang module file.

        Parameters
        ----------
        raw_path        : str   — the path as written by the programmer
        line            : int   — source line of the import statement
        namespace_mode  : bool  — True  → store result as MyLangNamespace
                                  False → merge into global function dict
                                  (legacy behaviour, kept for compatibility)
        selective_names : list  — if given, only import these names directly
                                  into the caller's scope (from X import Y)
        """

        abs_path = self.resolve_module_path(raw_path, line)

        # ── Derive the module alias from the file stem ──────────────
        alias = os.path.splitext(
            os.path.basename(abs_path)
        )[0]

        # ── Circular import / cache guard ────────────────────────────
        # If already cached, return the existing namespace (if any).
        if abs_path in self._import_cache:

            if namespace_mode and alias in self._namespaces:
                # Already a namespace — nothing to do
                return

            if selective_names is not None:
                # Bring names from already-loaded namespace into scope
                if alias in self._namespaces:
                    ns = self._namespaces[alias]
                    self._apply_selective(
                        ns, selective_names, raw_path, line
                    )
                return

            return  # legacy mode — already merged

        # Mark as loaded before executing (prevents circular loops)
        self._import_cache.add(abs_path)

        # ── Read source ──────────────────────────────────────────────
        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                source = f.read()
        except OSError as e:
            raise MyLangRuntimeError(
                f"Cannot read module '{abs_path}': {e}", line
            )

        # ── Lex + parse ──────────────────────────────────────────────
        from lexer import Lexer
        from parser import Parser

        try:
            tokens = Lexer(source).tokenize()
            ast    = Parser(tokens).parse()
        except Exception as e:
            raise MyLangRuntimeError(
                f"Error loading module '{raw_path}': {e}", line
            )

        # ── Execute in an isolated child interpreter ─────────────────
        #
        # Phase 6 isolation:
        #   - child has its OWN function dict (not shared with parent)
        #   - child shares _import_cache and _namespaces so nested
        #     imports and circular guards work correctly
        #   - after execution we inspect what the child defined and
        #     what it explicitly exported

        child = ASTInterpreter(
            module_search_paths=self.module_search_paths,
            file_root=self.file_root,
            _import_cache=self._import_cache,
        )

        # Share the namespace registry so nested imports register too
        child._namespaces = self._namespaces

        # Phase 4 tracing
        child.set_source(source, file_path=abs_path)
        child._import_stack = list(self._import_stack) + [
            {"path": raw_path, "line": line or 0}
        ]

        try:
            child.run(ast)
        except MyLangRuntimeError as e:
            child._enrich_error(e)
            raise

        # ── Build the namespace from the child's definitions ─────────
        #
        # If the module used `export name` statements, only those names
        # are public.  If no exports were declared, everything is
        # public (backwards-compatible with Phase 1–5 modules).

        all_defined = dict(child.functions)

        if child._export_names:
            # Explicit exports only
            public = {}
            for name in child._export_names:
                if name in all_defined:
                    public[name] = all_defined[name]
                else:
                    raise MyLangRuntimeError(
                        f"Module '{raw_path}' exports "
                        f"'{name}' but it is not defined",
                        line
                    )
        else:
            # No exports declared — everything is public
            public = all_defined

        ns = MyLangNamespace(alias, public)
        self._namespaces[alias] = ns

        if namespace_mode and selective_names is None:
            # `import utils` → store namespace in caller's variables
            self.variables[alias] = ns

        elif selective_names is not None:
            # `from utils import double, triple`
            self._apply_selective(ns, selective_names, raw_path, line)

        else:
            # Legacy mode (should not normally be reached in Phase 6
            # but kept for internal use / backwards compat)
            self.functions.update(public)

    # ─────────────────────────────────────────────────────────────────

    def _apply_selective(
        self,
        ns: "MyLangNamespace",
        names: list,
        raw_path: str,
        line=None
    ):
        """
        Import specific names from a namespace into the current scope.
        Used by `from utils import double, triple`.
        """
        for name in names:
            try:
                defn = ns.get(name)
            except KeyError:
                raise MyLangRuntimeError(
                    f"Module '{raw_path}' has no export "
                    f"named '{name}'",
                    line
                )
            # Functions and classes go into self.functions
            # so call_function() can find them
            self.functions[name] = defn

        # Resolve to an absolute path so the cache
        # key is canonical regardless of how the
        # import was written.
        abs_path = self.resolve_module_path(
            raw_path,
            line
        )

        # -------------------------
        # IMPORT CACHE CHECK
        # -------------------------
        # If this file has already been executed
        # during this run, skip it entirely.  Any
        # functions it defined are already in the
        # shared functions dict.

        if abs_path in self._import_cache:
            return

        # Mark as loaded *before* executing so
        # that circular imports don't cause
        # infinite recursion.
        self._import_cache.add(abs_path)

        # -------------------------
        # READ SOURCE
        # -------------------------

        try:

            with open(abs_path, "r", encoding="utf-8") as f:
                source = f.read()

        except OSError as e:

            raise MyLangRuntimeError(
                f"Cannot read module "
                f"'{abs_path}': {e}",
                line
            )

        # -------------------------
        # LEXER  →  PARSER
        # -------------------------

        # Import here to avoid circular imports
        # at module level.
        from lexer import Lexer
        from parser import Parser

        try:

            lexer = Lexer(source)
            tokens = lexer.tokenize()

            parser = Parser(tokens)
            ast = parser.parse()

        except Exception as e:

            raise MyLangRuntimeError(
                f"Error loading module "
                f"'{raw_path}': {e}",
                line
            )

        # -------------------------
        # EXECUTE IN CHILD INTERPRETER
        # -------------------------
        #
        # The child interpreter receives:
        #   _globals       — shared functions dict
        #   _import_cache  — shared cache set
        #   module_search_paths — so nested imports
        #                         keep the same
        #                         search roots
        #
        # The child gets its OWN variables dict so
        # that top-level assignments in a module
        # don't pollute the importer's scope.
        # Functions, however, flow into the shared
        # functions dict and become globally
        # available immediately.

        child = ASTInterpreter(
            module_search_paths=(
                self.module_search_paths
            ),
            file_root=self.file_root,
            _globals=self.functions,
            _import_cache=self._import_cache
        )

        # Phase 4: give child its source + import chain
        child.set_source(source, file_path=abs_path)
        child._import_stack = list(self._import_stack) + [
            {"path": raw_path, "line": line or 0}
        ]

        try:
            child.run(ast)
        except MyLangRuntimeError as e:
            # Enrich with child traceback, then re-raise
            child._enrich_error(e)
            raise

    # -------------------------
    # TYPE HELPERS
    # -------------------------

    def type_name(self, value):

        if isinstance(value, int):
            return "INTEGER"

        if isinstance(value, str):
            return "STRING"

        if isinstance(value, list):
            return "LIST"

        if isinstance(value, dict):
            return "DICTIONARY"

        if isinstance(value, bool):
            return "BOOLEAN"

        if isinstance(value, MyLangObject):
            return value.class_def.name

        if isinstance(value, MyLangNamespace):
            return f"module:{value.name}"

        return type(value).__name__

    # -------------------------
    # PHASE 5 — METHOD DISPATCH
    # -------------------------

    def _call_method(
        self,
        obj_expr,
        method_name,
        args,
        line=None
    ):
        """
        Evaluate obj_expr to a MyLangObject, look up
        method_name in its class definition, then execute
        the method body with 'this' bound to the instance
        and the method's parameters in scope.
        """

        obj = self.evaluate(obj_expr)

        if not isinstance(obj, MyLangObject):

            raise MyLangRuntimeError(
                f"Cannot call method '{method_name}' on "
                f"{self.type_name(obj)} — expected an object",
                line
            )

        class_def = obj.class_def

        if method_name not in class_def.methods:

            raise MyLangRuntimeError(
                f"Class '{class_def.name}' has no method "
                f"'{method_name}'",
                line
            )

        method = class_def.methods[method_name]

        # Evaluate arguments
        evaluated_args = [
            self.evaluate(a) for a in args
        ]

        if len(evaluated_args) != len(method.params):

            raise MyLangRuntimeError(
                f"{class_def.name}.{method_name}() expected "
                f"{len(method.params)} argument(s) "
                f"but got {len(evaluated_args)}",
                line
            )

        # Execute method body with 'this' + params in scope.
        # Restore variables after the call.
        old_vars = self.variables.copy()
        old_return = self.return_value

        self.variables["this"] = obj

        for i, pname in enumerate(method.params):
            self.variables[pname] = evaluated_args[i]

        self.return_value = None

        # Push call stack frame for Phase 4 tracing
        frame_dict = {
            "name":   f"{class_def.name}.{method_name}",
            "line":   line or 0,
            "locals": {"this": repr(obj)},
            "params": {"this": repr(obj)},
        }
        self._call_stack.append(frame_dict)

        try:
            self.run(method.body)
        except MyLangRuntimeError as e:
            self._enrich_error(e)
            raise
        finally:
            if self._call_stack:
                self._call_stack.pop()

        result = self.return_value

        # Restore caller scope but keep any mutations
        # to the object's properties (they live on the
        # MyLangObject, not in self.variables).
        self.variables  = old_vars
        self.return_value = old_return

        return result

    # -------------------------
    # BUILTINS
    # -------------------------

    def builtin_upper(self, args):

        return str(args[0]).upper()

    def builtin_lower(self, args):

        return str(args[0]).lower()

    def builtin_length(self, args):

        return len(args[0])

    def builtin_append(self, args):

        args[0].append(args[1])

        return args[0]

    def builtin_remove(self, args):

        args[0].remove(args[1])

        return args[0]

    def builtin_random(self, args):

        return random.randint(
            args[0],
            args[1]
        )

    def builtin_keys(self, args):

        dictionary = args[0]

        if not isinstance(dictionary, dict):

            raise MyLangRuntimeError(
                "keys() requires DICTIONARY"
            )

        return list(dictionary.keys())

    def builtin_values(self, args):

        dictionary = args[0]

        if not isinstance(dictionary, dict):

            raise MyLangRuntimeError(
                "values() requires DICTIONARY"
            )

        return list(dictionary.values())

    def builtin_exists(self, args):

        dictionary = args[0]
        key = args[1]

        if not isinstance(dictionary, dict):

            raise MyLangRuntimeError(
                "exists() requires DICTIONARY"
            )

        return key in dictionary

    # -------------------------
    # STRING BUILTINS
    # -------------------------

    def builtin_trim(self, args):

        value = args[0]

        if not isinstance(value, str):

            raise MyLangRuntimeError(
                "trim() requires STRING"
            )

        return value.strip()

    def builtin_replace(self, args):

        text = args[0]
        old = args[1]
        new = args[2]

        if not isinstance(text, str):

            raise MyLangRuntimeError(
                "replace() requires STRING "
                "as first argument"
            )

        return str(text).replace(
            str(old),
            str(new)
        )

    def builtin_split(self, args):

        text = args[0]
        delimiter = args[1]

        if not isinstance(text, str):

            raise MyLangRuntimeError(
                "split() requires STRING "
                "as first argument"
            )

        if not isinstance(delimiter, str):

            raise MyLangRuntimeError(
                "split() requires STRING "
                "as second argument"
            )

        return text.split(delimiter)

    def builtin_contains(self, args):

        text = args[0]
        substring = args[1]

        if not isinstance(text, str):

            raise MyLangRuntimeError(
                "contains() requires STRING "
                "as first argument"
            )

        return str(substring) in text

    def builtin_starts_with(self, args):

        text = args[0]
        prefix = args[1]

        if not isinstance(text, str):

            raise MyLangRuntimeError(
                "starts_with() requires STRING "
                "as first argument"
            )

        return text.startswith(str(prefix))

    def builtin_ends_with(self, args):

        text = args[0]
        suffix = args[1]

        if not isinstance(text, str):

            raise MyLangRuntimeError(
                "ends_with() requires STRING "
                "as first argument"
            )

        return text.endswith(str(suffix))

    def builtin_repeat_str(self, args):

        text = args[0]
        times = args[1]

        if not isinstance(text, str):

            raise MyLangRuntimeError(
                "repeat_str() requires STRING "
                "as first argument"
            )

        if not isinstance(times, int):

            raise MyLangRuntimeError(
                "repeat_str() requires INTEGER "
                "as second argument"
            )

        if times < 0:

            raise MyLangRuntimeError(
                "repeat_str() count "
                "must be >= 0"
            )

        return text * times

    def builtin_reverse(self, args):

        value = args[0]

        if not isinstance(value, str):

            raise MyLangRuntimeError(
                "reverse() requires STRING — "
                "use reverse_list() for lists"
            )

        return value[::-1]

    # -------------------------
    # MATH BUILTINS
    # -------------------------

    def builtin_abs(self, args):

        value = args[0]

        if not isinstance(value, (int, float)):

            raise MyLangRuntimeError(
                f"abs() requires INTEGER, "
                f"got {self.type_name(value)}"
            )

        return abs(value)

    def builtin_max(self, args):

        a = args[0]
        b = args[1]

        if (
            not isinstance(a, (int, float))
            or
            not isinstance(b, (int, float))
        ):

            raise MyLangRuntimeError(
                "max() requires two INTEGERs"
            )

        return a if a > b else b

    def builtin_min(self, args):

        a = args[0]
        b = args[1]

        if (
            not isinstance(a, (int, float))
            or
            not isinstance(b, (int, float))
        ):

            raise MyLangRuntimeError(
                "min() requires two INTEGERs"
            )

        return a if a < b else b

    def builtin_pow(self, args):

        base = args[0]
        exp = args[1]

        if (
            not isinstance(base, (int, float))
            or
            not isinstance(exp, (int, float))
        ):

            raise MyLangRuntimeError(
                "pow() requires two INTEGERs"
            )

        return int(base ** exp)

    def builtin_floor(self, args):

        import math

        value = args[0]

        if not isinstance(value, (int, float)):

            raise MyLangRuntimeError(
                "floor() requires INTEGER"
            )

        return int(math.floor(value))

    def builtin_ceil(self, args):

        import math

        value = args[0]

        if not isinstance(value, (int, float)):

            raise MyLangRuntimeError(
                "ceil() requires INTEGER"
            )

        return int(math.ceil(value))

    def builtin_sqrt(self, args):

        import math

        value = args[0]

        if not isinstance(value, (int, float)):

            raise MyLangRuntimeError(
                "sqrt() requires INTEGER"
            )

        if value < 0:

            raise MyLangRuntimeError(
                "sqrt() argument must be >= 0"
            )

        return int(math.isqrt(int(value)))

    def builtin_clamp(self, args):

        value = args[0]
        lo = args[1]
        hi = args[2]

        if (
            not isinstance(value, (int, float))
            or
            not isinstance(lo, (int, float))
            or
            not isinstance(hi, (int, float))
        ):

            raise MyLangRuntimeError(
                "clamp() requires three INTEGERs"
            )

        if lo > hi:

            raise MyLangRuntimeError(
                "clamp() lo must be <= hi"
            )

        if value < lo:
            return lo

        if value > hi:
            return hi

        return value

    # -------------------------
    # LIST BUILTINS
    # -------------------------

    def builtin_first(self, args):

        lst = args[0]

        if not isinstance(lst, list):

            raise MyLangRuntimeError(
                "first() requires LIST"
            )

        if len(lst) == 0:

            raise MyLangRuntimeError(
                "first() called on empty LIST"
            )

        return lst[0]

    def builtin_last(self, args):

        lst = args[0]

        if not isinstance(lst, list):

            raise MyLangRuntimeError(
                "last() requires LIST"
            )

        if len(lst) == 0:

            raise MyLangRuntimeError(
                "last() called on empty LIST"
            )

        return lst[-1]

    def builtin_reverse_list(self, args):

        lst = args[0]

        if not isinstance(lst, list):

            raise MyLangRuntimeError(
                "reverse_list() requires LIST — "
                "use reverse() for strings"
            )

        return list(reversed(lst))

    def builtin_slice(self, args):

        lst = args[0]
        start = args[1]
        end = args[2]

        if not isinstance(lst, list):

            raise MyLangRuntimeError(
                "slice() requires LIST "
                "as first argument"
            )

        if (
            not isinstance(start, int)
            or
            not isinstance(end, int)
        ):

            raise MyLangRuntimeError(
                "slice() start and end "
                "must be INTEGER"
            )

        return lst[start:end]

    def builtin_contains_item(self, args):

        lst = args[0]
        item = args[1]

        if not isinstance(lst, list):

            raise MyLangRuntimeError(
                "contains_item() requires LIST "
                "as first argument"
            )

        return item in lst

    def builtin_sort(self, args):

        lst = args[0]

        if not isinstance(lst, list):

            raise MyLangRuntimeError(
                "sort() requires LIST"
            )

        try:

            return sorted(lst)

        except TypeError:

            raise MyLangRuntimeError(
                "sort() list elements "
                "must all be the same type"
            )

    def builtin_index_of(self, args):

        lst = args[0]
        item = args[1]

        if not isinstance(lst, list):

            raise MyLangRuntimeError(
                "index_of() requires LIST "
                "as first argument"
            )

        # Returns -1 when not found —
        # consistent with most languages
        # beginners already know.
        try:
            return lst.index(item)
        except ValueError:
            return -1

    def builtin_flatten(self, args):

        lst = args[0]

        if not isinstance(lst, list):

            raise MyLangRuntimeError(
                "flatten() requires LIST"
            )

        result = []

        for item in lst:

            if isinstance(item, list):
                result.extend(item)
            else:
                result.append(item)

        return result

    # -------------------------
    # DICTIONARY BUILTINS
    # -------------------------

    def builtin_delete(self, args):

        dictionary = args[0]
        key = args[1]

        if not isinstance(dictionary, dict):

            raise MyLangRuntimeError(
                "delete() requires DICTIONARY "
                "as first argument"
            )

        if key not in dictionary:

            raise MyLangRuntimeError(
                f"delete() key not found: "
                f"'{key}'"
            )

        del dictionary[key]

        return dictionary

    def builtin_merge(self, args):

        a = args[0]
        b = args[1]

        if (
            not isinstance(a, dict)
            or
            not isinstance(b, dict)
        ):

            raise MyLangRuntimeError(
                "merge() requires two DICTIONARYs"
            )

        # Second dict wins on key conflicts —
        # same behaviour as Python dict unpacking.
        result = {}
        result.update(a)
        result.update(b)

        return result

    def builtin_get(self, args):

        dictionary = args[0]
        key = args[1]
        default = args[2]

        if not isinstance(dictionary, dict):

            raise MyLangRuntimeError(
                "get() requires DICTIONARY "
                "as first argument"
            )

        return dictionary.get(key, default)

    # -------------------------
    # TYPE CONVERSION BUILTINS
    # -------------------------

    def builtin_to_int(self, args):

        value = args[0]

        if isinstance(value, int):
            return value

        if isinstance(value, bool):
            return int(value)

        if isinstance(value, str):

            try:
                return int(value)
            except ValueError:
                raise MyLangRuntimeError(
                    f"to_int() cannot convert "
                    f'"{value}" to INTEGER'
                )

        raise MyLangRuntimeError(
            f"to_int() cannot convert "
            f"{self.type_name(value)}"
        )

    def builtin_to_str(self, args):

        value = args[0]

        if isinstance(value, bool):
            return "true" if value else "false"

        return str(value)

    def builtin_to_bool(self, args):

        value = args[0]

        if isinstance(value, bool):
            return value

        if isinstance(value, int):
            return value != 0

        if isinstance(value, str):

            low = value.strip().lower()

            if low in ("true", "1", "yes"):
                return True

            if low in ("false", "0", "no", ""):
                return False

            raise MyLangRuntimeError(
                f"to_bool() cannot convert "
                f'"{value}" to BOOLEAN'
            )

        raise MyLangRuntimeError(
            f"to_bool() cannot convert "
            f"{self.type_name(value)}"
        )

    def builtin_type_of(self, args):

        return self.type_name(args[0])

    # -------------------------
    # INPUT / OUTPUT BUILTINS
    # -------------------------

    def builtin_input(self, args):

        # 0 args — read silently
        if len(args) == 0:

            return input()

        # 1 arg — print prompt, then read
        prompt = args[0]

        return input(str(prompt))

    # -------------------------
    # FILE IO BUILTINS
    # -------------------------

    def _resolve_file_path(
        self,
        raw_path,
        line=None
    ):

        # -------------------------
        # TYPE CHECK
        # -------------------------

        if not isinstance(raw_path, str):

            raise MyLangRuntimeError(
                f"File path must be STRING, "
                f"got {self.type_name(raw_path)}",
                line
            )

        path = raw_path.strip()

        if not path:

            raise MyLangRuntimeError(
                "File path cannot be empty",
                line
            )

        # -------------------------
        # PATH TRAVERSAL GUARD
        # -------------------------
        #
        # Join the path to file_root and then
        # resolve it to an absolute canonical path.
        # If the result does not start with
        # file_root the script is trying to escape
        # the sandbox — reject it immediately.
        #
        # This blocks attacks like:
        #   read_file("../../etc/passwd")
        #   write_file("../sensitive.txt", "x")

        abs_path = os.path.abspath(
            os.path.join(self.file_root, path)
        )

        root = self.file_root

        # Ensure the resolved path is inside the
        # sandbox.  We compare with a trailing
        # separator so that a root of /foo does not
        # accidentally allow /foobar.
        if not (
            abs_path == root
            or
            abs_path.startswith(
                root + os.sep
            )
        ):

            raise MyLangRuntimeError(
                f"File path escapes sandbox: "
                f"'{raw_path}' resolves outside "
                f"the allowed directory",
                line
            )

        return abs_path

    def builtin_read_file(self, args):

        path = self._resolve_file_path(args[0])

        # -------------------------
        # EXISTENCE CHECK
        # -------------------------

        if not os.path.isfile(path):

            raise MyLangRuntimeError(
                f"read_file(): file not found: "
                f"'{args[0]}'"
            )

        # -------------------------
        # READ
        # -------------------------

        try:

            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        except OSError as e:

            raise MyLangRuntimeError(
                f"read_file(): cannot read "
                f"'{args[0]}': {e}"
            )

    def builtin_write_file(self, args):

        path = self._resolve_file_path(args[0])
        content = args[1]

        # -------------------------
        # CONTENT TYPE CHECK
        # -------------------------

        if not isinstance(content, str):

            raise MyLangRuntimeError(
                f"write_file() content must be "
                f"STRING, got "
                f"{self.type_name(content)}"
            )

        # -------------------------
        # WRITE (create or overwrite)
        # -------------------------

        try:

            # Create any intermediate directories
            # so write_file("logs/out.txt", x)
            # works even if logs/ doesn't exist.
            parent = os.path.dirname(path)

            if parent:
                os.makedirs(parent, exist_ok=True)

            with open(
                path, "w", encoding="utf-8"
            ) as f:

                bytes_written = f.write(content)

            return bytes_written

        except OSError as e:

            raise MyLangRuntimeError(
                f"write_file(): cannot write "
                f"'{args[0]}': {e}"
            )

    def builtin_append_file(self, args):

        path = self._resolve_file_path(args[0])
        content = args[1]

        # -------------------------
        # CONTENT TYPE CHECK
        # -------------------------

        if not isinstance(content, str):

            raise MyLangRuntimeError(
                f"append_file() content must be "
                f"STRING, got "
                f"{self.type_name(content)}"
            )

        # -------------------------
        # APPEND (create if missing)
        # -------------------------

        try:

            parent = os.path.dirname(path)

            if parent:
                os.makedirs(parent, exist_ok=True)

            with open(
                path, "a", encoding="utf-8"
            ) as f:

                bytes_written = f.write(content)

            return bytes_written

        except OSError as e:

            raise MyLangRuntimeError(
                f"append_file(): cannot append to "
                f"'{args[0]}': {e}"
            )

    def builtin_file_exists(self, args):

        # Type-check but never raise on bad paths —
        # file_exists() is meant to be safe to call
        # on any string without crashing.

        if not isinstance(args[0], str):

            return False

        try:

            path = self._resolve_file_path(args[0])
            return os.path.isfile(path)

        except MyLangRuntimeError:

            # Path escaped the sandbox — treat as
            # non-existent rather than crashing.
            return False

    def builtin_delete_file(self, args):

        path = self._resolve_file_path(args[0])

        # -------------------------
        # EXISTENCE CHECK
        # -------------------------

        if not os.path.isfile(path):

            raise MyLangRuntimeError(
                f"delete_file(): file not found: "
                f"'{args[0]}'"
            )

        # -------------------------
        # DELETE
        # -------------------------

        try:

            os.remove(path)
            return True

        except OSError as e:

            raise MyLangRuntimeError(
                f"delete_file(): cannot delete "
                f"'{args[0]}': {e}"
            )

    # -------------------------
    # JSON BUILTINS  (Phase 9)
    # -------------------------

    def builtin_parse_json(self, args):
        """
        parse_json(text)
        Parse a JSON string into a native MYTH value.
        """

        from json_parser import parse_json, JSONParseError

        if not isinstance(args[0], str):
            raise MyLangRuntimeError(
                f"parse_json() expects STRING, "
                f"got {self.type_name(args[0])}"
            )

        try:
            return parse_json(args[0])

        except JSONParseError as e:
            raise MyLangRuntimeError(
                f"parse_json(): {e.message} "
                f"(line {e.line}, col {e.column})"
            )

        except Exception as e:
            raise MyLangRuntimeError(
                f"parse_json(): {e}"
            )

    def builtin_to_json(self, args):
        """
        to_json(value)
        to_json(value, pretty)
        Serialize a MYTH value to a JSON string.
        """

        from json_serializer import to_json, SerializationError

        value  = args[0]
        pretty = bool(args[1]) if len(args) > 1 else False

        try:
            return to_json(value, pretty=pretty)

        except SerializationError as e:
            raise MyLangRuntimeError(
                f"to_json(): {e.message}"
            )

        except Exception as e:
            raise MyLangRuntimeError(
                f"to_json(): {e}"
            )

    def builtin_save_json(self, args):
        """
        save_json(path, value)
        Serialize value to JSON and write to path.
        Sandbox rules apply (same as write_file).
        """

        from json_serializer import to_json, SerializationError

        raw_path = args[0]
        value    = args[1]
        path     = self._resolve_file_path(raw_path)

        try:
            json_text = to_json(value, pretty=True)

        except SerializationError as e:
            raise MyLangRuntimeError(
                f"save_json(): {e.message}"
            )

        try:
            parent = os.path.dirname(path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(json_text)
            return True

        except OSError as e:
            raise MyLangRuntimeError(
                f"save_json(): cannot write "
                f"'{raw_path}': {e}"
            )

    def builtin_load_json(self, args):
        """
        load_json(path)
        Read a JSON file and return the parsed MYTH value.
        Sandbox rules apply (same as read_file).
        """

        from json_parser import parse_json, JSONParseError

        raw_path = args[0]
        path     = self._resolve_file_path(raw_path)

        if not os.path.isfile(path):
            raise MyLangRuntimeError(
                f"load_json(): file not found: "
                f"'{raw_path}'"
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()

        except OSError as e:
            raise MyLangRuntimeError(
                f"load_json(): cannot read "
                f"'{raw_path}': {e}"
            )

        try:
            return parse_json(text)

        except JSONParseError as e:
            raise MyLangRuntimeError(
                f"load_json(): JSON error in '{raw_path}': "
                f"{e.message} (line {e.line})"
            )

    def resolve_collection_reference(
        self,
        node
    ):

        # VARIABLE
        if isinstance(node, VariableNode):

            if node.name not in self.variables:

                raise MyLangRuntimeError(
                    f"Undefined variable: "
                    f"{node.name}",
                    node.line
                )

            return self.variables[node.name]

        # INDEX NODE
        if isinstance(node, IndexNode):

            parent = (
                self.resolve_collection_reference(
                    node.collection
                )
            )

            index = self.evaluate(
                node.index
            )

            try:

                return parent[index]

            except Exception:

                raise MyLangRuntimeError(
                    f"Invalid index/key: "
                    f"{index}",
                    node.line
                )

        raise MyLangRuntimeError(
            "Invalid assignment target",
            getattr(node, "line", None)
        )

    # -------------------------
    # EVALUATE
    # -------------------------

    def evaluate(self, node):

        # ── Phase 7: fast-path dispatch table ────────────────────────
        # Resolve the most common leaf nodes by type lookup instead of
        # cascading isinstance() calls.  Profiling showed isinstance()
        # accounted for ~41% of interpreter CPU time.  This table
        # covers the nodes that appear in tight inner loops.

        _type = type(node)

        if _type is NumberNode:
            return node.value

        if _type is StringNode:
            return node.value

        if _type is VariableNode:
            if node.name in self.variables:
                return self.variables[node.name]
            if node.name in self.functions:
                return self.functions[node.name]
            raise MyLangRuntimeError(
                f"Undefined variable: {node.name}",
                node.line
            )

        if _type is BinaryOperationNode:
            left  = self.evaluate(node.left)
            right = self.evaluate(node.right)
            op    = node.operator
            try:
                if op == "+":
                    if isinstance(left, str) or isinstance(right, str):
                        return str(left) + str(right)
                    return left + right
                if op == "-": return left - right
                if op == "*": return left * right
                if op == "/":
                    if right == 0:
                        raise MyLangRuntimeError("Division by zero", node.line)
                    return left // right
                if op == "%":
                    if right == 0:
                        raise MyLangRuntimeError("Modulo by zero", node.line)
                    return left % right
            except TypeError:
                raise MyLangRuntimeError(
                    f"Cannot apply '{op}' to "
                    f"{self.type_name(left)} and {self.type_name(right)}",
                    node.line
                )

        if _type is CompareNode:
            left  = self.evaluate(node.left)
            right = self.evaluate(node.right)
            op    = node.operator
            if op == "==": return left == right
            if op == ">":  return left > right
            if op == "<":  return left < right

        # ── Remaining nodes use the original isinstance path ──────────

        # NUMBER
        if isinstance(node, NumberNode):

            return node.value

        # STRING
        if isinstance(node, StringNode):

            return node.value

        # LIST
        if isinstance(node, ListNode):

            result = []

            for element in node.elements:

                result.append(
                    self.evaluate(element)
                )

            return result

        # DICTIONARY
        if isinstance(node, DictionaryNode):

            result = {}

            for key_node, value_node in node.pairs:

                key = self.evaluate(
                    key_node
                )

                value = self.evaluate(
                    value_node
                )

                result[key] = value

            return result

        # INDEX
        if isinstance(node, IndexNode):

            collection = self.evaluate(
                node.collection
            )

            index = self.evaluate(
                node.index
            )

            if not isinstance(
                collection,
                (list, dict)
            ):

                raise MyLangRuntimeError(
                    f"Cannot index "
                    f"{self.type_name(collection)}",
                    node.line
                )

            try:

                return collection[index]

            except Exception:

                raise MyLangRuntimeError(
                    f"Invalid index/key: "
                    f"{index}",
                    node.line
                )

        # VARIABLE
        if isinstance(node, VariableNode):

            if node.name not in self.variables:

                raise MyLangRuntimeError(
                    f"Undefined variable: "
                    f"{node.name}",
                    node.line
                )

            return self.variables[
                node.name
            ]

        # UNARY
        if isinstance(node, UnaryOperationNode):

            operand = self.evaluate(
                node.operand
            )

            if node.operator == "not":

                return not operand

        # LOGICAL
        if isinstance(node, LogicalOperationNode):

            left = self.evaluate(
                node.left
            )

            right = self.evaluate(
                node.right
            )

            if node.operator == "and":

                return left and right

            if node.operator == "or":

                return left or right

        # FUNCTION CALL
        if isinstance(node, CallNode):

            return self.call_function(
                node.name,
                node.args,
                node.line
            )

        # COMPARISON
        if isinstance(node, CompareNode):

            left = self.evaluate(
                node.left
            )

            right = self.evaluate(
                node.right
            )

            try:

                if node.operator == "==":
                    return left == right

                if node.operator == ">":
                    return left > right

                if node.operator == "<":
                    return left < right

            except Exception:

                raise MyLangRuntimeError(
                    f"Invalid comparison between "
                    f"{self.type_name(left)} and "
                    f"{self.type_name(right)}",
                    node.line
                )

        # BINARY
        if isinstance(
            node,
            BinaryOperationNode
        ):

            left = self.evaluate(
                node.left
            )

            right = self.evaluate(
                node.right
            )

            # ADD
            if node.operator == "+":

                if (
                    isinstance(left, int)
                    and
                    isinstance(right, int)
                ):

                    return left + right

                if (
                    isinstance(left, str)
                    or
                    isinstance(right, str)
                ):

                    return str(left) + str(right)

                raise MyLangRuntimeError(
                    f"Cannot add "
                    f"{self.type_name(left)} and "
                    f"{self.type_name(right)}",
                    node.line
                )

            # SUBTRACT
            if node.operator == "-":

                if (
                    isinstance(left, int)
                    and
                    isinstance(right, int)
                ):

                    return left - right

                raise MyLangRuntimeError(
                    f"Cannot subtract "
                    f"{self.type_name(left)} and "
                    f"{self.type_name(right)}",
                    node.line
                )

            # MULTIPLY
            if node.operator == "*":

                if (
                    isinstance(left, int)
                    and
                    isinstance(right, int)
                ):

                    return left * right

                raise MyLangRuntimeError(
                    f"Cannot multiply "
                    f"{self.type_name(left)} and "
                    f"{self.type_name(right)}",
                    node.line
                )

            # DIVIDE
            if node.operator == "/":

                if (
                    isinstance(left, int)
                    and
                    isinstance(right, int)
                ):

                    if right == 0:

                        raise MyLangRuntimeError(
                            "Division by zero",
                            node.line
                        )

                    return left / right

                raise MyLangRuntimeError(
                    f"Cannot divide "
                    f"{self.type_name(left)} and "
                    f"{self.type_name(right)}",
                    node.line
                )

            # MODULO
            if node.operator == "%":

                if (
                    isinstance(left, int)
                    and
                    isinstance(right, int)
                ):

                    return left % right

                raise MyLangRuntimeError(
                    f"Cannot modulo "
                    f"{self.type_name(left)} and "
                    f"{self.type_name(right)}",
                    node.line
                )

        # ── PHASE 5 / 6 — OBJECT & NAMESPACE ACCESS ──────────────────

        # PROPERTY ACCESS   obj.property  /  module.name
        if isinstance(node, PropertyAccessNode):

            obj = self.evaluate(node.obj_expr)

            # ── Phase 6: namespace attribute access ──────────────────
            if isinstance(obj, MyLangNamespace):

                try:
                    return obj.get(node.property_name)
                except KeyError:
                    raise MyLangRuntimeError(
                        f"Module '{obj.name}' has no "
                        f"export '{node.property_name}'",
                        node.line
                    )

            # ── Phase 5: object property access ──────────────────────
            if not isinstance(obj, MyLangObject):

                raise MyLangRuntimeError(
                    f"Cannot access property on "
                    f"{self.type_name(obj)} — "
                    f"expected an object or module",
                    node.line
                )

            prop = node.property_name

            if prop not in obj.properties:

                raise MyLangRuntimeError(
                    f"Object of class "
                    f"'{obj.class_def.name}' has "
                    f"no property '{prop}'",
                    node.line
                )

            return obj.properties[prop]

        # METHOD CALL   obj.method(args)  /  module.function(args)
        if isinstance(node, MethodCallNode):

            obj = self.evaluate(node.obj_expr)

            # ── Phase 6: namespace function call ─────────────────────
            if isinstance(obj, MyLangNamespace):

                try:
                    defn = obj.get(node.method_name)
                except KeyError:
                    raise MyLangRuntimeError(
                        f"Module '{obj.name}' has no "
                        f"export '{node.method_name}'",
                        node.line
                    )

                # Temporarily register the function so
                # call_function() can dispatch it normally
                tmp_name = f"__ns_{obj.name}_{node.method_name}"
                self.functions[tmp_name] = defn

                try:
                    result = self.call_function(
                        tmp_name,
                        node.args,
                        node.line
                    )
                finally:
                    self.functions.pop(tmp_name, None)

                return result

            # ── Phase 5: object method call ───────────────────────────
            return self._call_method(
                node.obj_expr,
                node.method_name,
                node.args,
                node.line
            )

        # UNKNOWN EXPRESSION
        raise MyLangRuntimeError(
            f"Unknown expression node: "
            f"{type(node).__name__}",
            getattr(
                node,
                "line",
                None
            )
        )

    # -------------------------
    # FUNCTION CALLS
    # -------------------------

    def call_function(
        self,
        name,
        args,
        line=None
    ):

        # BUILTINS
        if name in self.builtins:

            entry = self.builtins[name]

            # Tuples are (fn, min_args, max_args).
            # max_args=None means any number ≥ min.
            # Legacy 2-tuples (fn, n) still work —
            # treated as exact (min == max == n).

            if len(entry) == 2:

                builtin_function = entry[0]
                min_args = entry[1]
                max_args = entry[1]

            else:

                builtin_function = entry[0]
                min_args = entry[1]
                max_args = entry[2]

            n = len(args)

            too_few = n < min_args

            too_many = (
                max_args is not None
                and
                n > max_args
            )

            if too_few or too_many:

                if min_args == max_args:
                    expected_str = (
                        str(min_args)
                    )
                elif max_args is None:
                    expected_str = (
                        f"at least {min_args}"
                    )
                else:
                    expected_str = (
                        f"{min_args}-{max_args}"
                    )

                raise MyLangRuntimeError(
                    f"{name}() expected "
                    f"{expected_str} argument(s) "
                    f"but got {n}",
                    line
                )

            evaluated_args = []

            for arg in args:

                evaluated_args.append(
                    self.evaluate(arg)
                )

            return builtin_function(
                evaluated_args
            )

        # ── PHASE 5: CLASS INSTANTIATION ─────────────────────────────
        # When a name refers to a ClassNode, calling it creates a new
        # MyLangObject instance and runs the constructor (init body)
        # with 'this' bound to the fresh instance.

        if name in self.functions and isinstance(
            self.functions[name], ClassNode
        ):

            class_def = self.functions[name]
            instance  = MyLangObject(class_def)

            # Evaluate constructor arguments
            evaluated_args = [
                self.evaluate(a) for a in args
            ]

            if len(evaluated_args) != len(class_def.params):

                raise MyLangRuntimeError(
                    f"{name}() constructor expected "
                    f"{len(class_def.params)} argument(s) "
                    f"but got {len(evaluated_args)}",
                    line
                )

            # Run the init body with 'this' bound
            # and constructor params in scope.
            old_vars = self.variables.copy()
            self.variables["this"] = instance

            for i, pname in enumerate(class_def.params):
                self.variables[pname] = evaluated_args[i]

            self.run(class_def.init_body)

            self.variables = old_vars

            return instance

        # USER FUNCTION CHECK
        if name not in self.functions:

            raise MyLangRuntimeError(
                f"Undefined function: "
                f"{name}",
                line
            )

        function = self.functions[name]

        if len(args) != len(function.params):

            raise MyLangRuntimeError(
                f"Function '{name}' expected "
                f"{len(function.params)} arguments "
                f"but got {len(args)}",
                line
            )

        old_variables = self.variables.copy()

        self.return_value = None

        # ── Phase 4: push frame unconditionally ───────────────────────
        # Record parameter values as the locals snapshot for this frame.
        param_locals = {}
        for i in range(len(function.params)):
            if i < len(args):
                try:
                    param_locals[function.params[i]] = (
                        self.evaluate(args[i])
                    )
                except Exception:
                    param_locals[function.params[i]] = "?"

        frame_dict = {
            "name":   name,
            "line":   line or 0,
            "locals": param_locals,
            "params": param_locals,  # alias for IDE debug panel
        }
        self._call_stack.append(frame_dict)

        # Set parameters in the current variables scope
        for pname, pval in param_locals.items():
            self.variables[pname] = pval

        try:
            self.run(function.body)
        except MyLangRuntimeError as e:
            # Enrich before propagating
            self._enrich_error(e)
            raise
        finally:
            # Always pop the frame, even on error
            if self._call_stack:
                self._call_stack.pop()

        # ── Phase 4: debug controller ─────────────────────────────────
        if self._debug_controller is not None:
            pass   # already handled in run() per-node hook

        result = self.return_value

        self.variables = old_variables

        return result

    # -------------------------
    # MAIN RUNTIME
    # -------------------------

    def run(self, nodes):

        for node in nodes:

            # -------------------------
            # DEBUG HOOK
            # -------------------------
            # If a debug controller is attached,
            # notify it before every statement.
            # on_line() blocks when paused at a
            # breakpoint or in step mode.

            if self._debug_controller is not None:
                line = getattr(node, "line", None)
                if line is not None:
                    self._debug_controller.on_line(
                        line,
                        self.variables,
                        list(self._call_stack)
                    )

            # PRINT
            if isinstance(node, PrintNode):

                value = self.evaluate(
                    node.value
                )

                print(value)

            # FOREACH
            elif isinstance(
                node,
                ForEachNode
            ):

                iterable = self.evaluate(
                    node.iterable
                )

                if not isinstance(iterable, list):

                    raise MyLangRuntimeError(
                        "FOREACH requires LIST",
                        node.line
                    )

                for item in iterable:

                    self.variables[
                        node.variable
                    ] = item

                    self.run(
                        node.body
                    )

                    if self.return_value is not None:
                        return

            # FOR
            elif isinstance(node, ForNode):

                start = self.evaluate(
                    node.start
                )

                end = self.evaluate(
                    node.end
                )

                if (
                    not isinstance(start, int)
                    or
                    not isinstance(end, int)
                ):

                    raise MyLangRuntimeError(
                        "FOR loop bounds must be INTEGER",
                        node.line
                    )

                for i in range(
                    start,
                    end + 1
                ):

                    self.variables[
                        node.variable
                    ] = i

                    self.run(
                        node.body
                    )

                    if self.return_value is not None:
                        return

            # INDEX ASSIGN
            elif isinstance(
                node,
                IndexAssignNode
            ):

                collection = (
                    self.resolve_collection_reference(
                        node.collection
                    )
                )

                index = self.evaluate(
                    node.index
                )

                value = self.evaluate(
                    node.value
                )

                if not isinstance(
                    collection,
                    (list, dict)
                ):

                    raise MyLangRuntimeError(
                        "Cannot index assign non-collection",
                        node.line
                    )

                try:

                    collection[index] = value

                except Exception:

                    raise MyLangRuntimeError(
                        "Index Assignment Error",
                        node.line
                    )

            # ASSIGN
            elif isinstance(
                node,
                AssignNode
            ):

                self.variables[
                    node.name
                ] = self.evaluate(
                    node.value
                )

            # FUNCTION
            elif isinstance(
                node,
                FunctionNode
            ):

                self.functions[
                    node.name
                ] = node

            # RETURN
            elif isinstance(
                node,
                ReturnNode
            ):

                self.return_value = (
                    self.evaluate(
                        node.value
                    )
                )

                return

            # CALL
            elif isinstance(
                node,
                CallNode
            ):

                self.call_function(
                    node.name,
                    node.args,
                    node.line
                )

            # IF
            elif isinstance(node, IfNode):

                condition = self.evaluate(
                    node.condition
                )

                if condition:

                    self.run(
                        node.true_body
                    )

                else:

                    self.run(
                        node.false_body
                    )

                # Propagate return if the branch returned
                if self.return_value is not None:
                    return

            # WHILE
            elif isinstance(node, WhileNode):

                while self.evaluate(
                    node.condition
                ):

                    self.run(
                        node.body
                    )

                    # Propagate return from inside while
                    if self.return_value is not None:
                        return

            # IMPORT  →  namespace mode
            elif isinstance(node, ImportNode):

                self.load_module(
                    node.path,
                    node.line,
                    namespace_mode=True,
                )

            # FROM ... IMPORT  →  selective import
            elif isinstance(node, FromImportNode):

                self.load_module(
                    node.path,
                    node.line,
                    namespace_mode=False,
                    selective_names=node.names,
                )

            # EXPORT  →  mark a name as public
            elif isinstance(node, ExportNode):

                if node.name not in self._export_names:
                    self._export_names.append(node.name)

            # ── PHASE 5 — OBJECT SYSTEM ──────────────────────────────

            # CLASS DEFINITION
            # Register the class so it can be
            # instantiated by name like a function.
            elif isinstance(node, ClassNode):

                self.functions[node.name] = node

            # PROPERTY ASSIGNMENT   obj.prop = value
            elif isinstance(node, PropertyAssignNode):

                obj = self.evaluate(node.obj_expr)

                if not isinstance(obj, MyLangObject):

                    raise MyLangRuntimeError(
                        f"Cannot set property on "
                        f"{self.type_name(obj)} — "
                        f"expected an object",
                        node.line
                    )

                value = self.evaluate(node.value)
                obj.properties[node.property_name] = value

            # STANDALONE METHOD CALL / NAMESPACE CALL
            elif isinstance(node, MethodCallNode):

                obj = self.evaluate(node.obj_expr)

                if isinstance(obj, MyLangNamespace):

                    # Delegate to evaluate() which handles namespaces
                    self.evaluate(node)

                else:

                    self._call_method(
                        node.obj_expr,
                        node.method_name,
                        node.args,
                        node.line
                    )

            # UNKNOWN NODE
            else:

                raise MyLangRuntimeError(
                    f"Unknown AST node: "
                    f"{type(node).__name__}",
                    getattr(
                        node,
                        "line",
                        None
                    )
                )