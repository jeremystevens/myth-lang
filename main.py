from lexer import Lexer
from parser import Parser
from ast_interpreter import ASTInterpreter

from runtime_error import (
    MyLangRuntimeError
)

from parser_error import (
    MyLangSyntaxError
)

import os
import sys

VERSION = "0.8.0"


# Directory where main.py lives — used to
# resolve the default script path so the file
# can be run from any working directory.
MAIN_DIR = os.path.abspath(
    os.path.dirname(__file__)
)

# -------------------------
# ARGUMENT HANDLING
# -------------------------

if len(sys.argv) >= 2:
    arg = sys.argv[1]
    if os.path.isfile(arg):
        SCRIPT = os.path.abspath(arg)
    else:
        SCRIPT = os.path.abspath(
            os.path.join(MAIN_DIR, arg)
        )
else:
    SCRIPT = os.path.join(
        MAIN_DIR,
        "examples",
        "dictionary_builtin_test.my"
    )

if not os.path.isfile(SCRIPT):
    print(f"Error: cannot find script '{SCRIPT}'")
    sys.exit(1)

with open(SCRIPT, "r") as file:
    code = file.read()

source_lines = code.splitlines()

script_dir = os.path.abspath(
    os.path.dirname(SCRIPT)
)

print(f"MyLang AST v{VERSION}")

try:

    # -------------------------
    # LEXER
    # -------------------------

    print("\nTOKENS:")
    lexer  = Lexer(code)
    tokens = lexer.tokenize()
    print(tokens)

    # -------------------------
    # PARSER
    # -------------------------

    print("\nAST:")
    parser = Parser(tokens)
    ast    = parser.parse()
    print(ast)

    # -------------------------
    # INTERPRETER
    # -------------------------

    print("\nOUTPUT:")

    interpreter = ASTInterpreter(
        module_search_paths=[script_dir],
        file_root=script_dir
    )

    # Phase 4: give interpreter the source so
    # tracebacks can show the actual code lines.
    interpreter.set_source(code, file_path=SCRIPT)

    interpreter.run(ast)

# -------------------------
# SYNTAX ERRORS
# -------------------------

except MyLangSyntaxError as e:

    print(
        e.format_traceback(source_lines)
    )

# -------------------------
# RUNTIME ERRORS
# -------------------------

except MyLangRuntimeError as e:

    # Enrich with traceback if not already set
    if not e.traceback and 'interpreter' in dir():
        interpreter._enrich_error(e)

    print(
        e.format_traceback(source_lines)
    )

# -------------------------
# INTERNAL ERRORS
# -------------------------

except Exception as e:

    print(
        f"\nINTERNAL ERROR:\n{e}"
    )
