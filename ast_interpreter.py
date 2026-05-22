from ast_nodes import *

from runtime_error import (
    MyLangRuntimeError
)

import random
import os


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
            self.functions = {}
            self._import_cache = set()
        else:
            # Child (module) interpreter — shares
            # the parent's dicts by reference
            self.functions = _globals
            self._import_cache = _import_cache

        self.variables = {}
        self.return_value = None

        # -------------------------
        # DEBUG HOOKS
        # -------------------------
        # Set by the IDE debug runner via
        # set_debug_controller().  None means
        # no debugging — zero overhead on normal
        # runs.

        self._debug_controller = None
        self._call_stack       = []   # list of frame dicts

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
        line=None
    ):

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

            with open(abs_path, "r") as f:
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

        child.run(ast)

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

        return type(value).__name__

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

        for i in range(
            len(function.params)
        ):

            param_name = function.params[i]

            param_value = self.evaluate(
                args[i]
            )

            self.variables[
                param_name
            ] = param_value

        self.return_value = None

        # Push call stack frame
        frame = {
            "name": name,
            "line": line or 0,
            "params": {
                function.params[i]: self.evaluate(args[i])
                if i < len(args) else None
                for i in range(len(function.params))
            }
        }
        if self._debug_controller is not None:
            self._call_stack.append(frame)

        self.run(function.body)

        # Pop call stack frame
        if self._debug_controller is not None:
            if self._call_stack:
                self._call_stack.pop()

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

            # WHILE
            elif isinstance(node, WhileNode):

                while self.evaluate(
                    node.condition
                ):

                    self.run(
                        node.body
                    )

            # IMPORT
            elif isinstance(node, ImportNode):

                self.load_module(
                    node.path,
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