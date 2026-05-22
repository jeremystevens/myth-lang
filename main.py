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


# -------------------------
# ARGUMENT HANDLING
# -------------------------
#
# Usage:
#   python main.py                        — runs the default script
#   python main.py examples/hello.my     — runs a specific script
#   python main.py path/to/any/file.my   — runs any .my file

if len(sys.argv) >= 2:
    SCRIPT = sys.argv[1]
else:
    SCRIPT = "examples/file_read_write_test.my"

if not os.path.isfile(SCRIPT):
    print(f"Error: cannot find script '{SCRIPT}'")
    sys.exit(1)

with open(SCRIPT, "r") as file:
    code = file.read()

# The directory that holds the script being run
# is always the first place searched for imports
# and file IO operations.
script_dir = os.path.abspath(
    os.path.dirname(SCRIPT)
)

print(
    f"MyLang AST v{VERSION}"
)

try:

    # -------------------------
    # LEXER
    # -------------------------

    print("\nTOKENS:")

    lexer = Lexer(code)

    tokens = lexer.tokenize()

    print(tokens)

    # -------------------------
    # PARSER
    # -------------------------

    print("\nAST:")

    parser = Parser(tokens)

    ast = parser.parse()

    print(ast)

    # -------------------------
    # INTERPRETER
    # -------------------------

    print("\nOUTPUT:")

    interpreter = ASTInterpreter(
        module_search_paths=[script_dir],
        file_root=script_dir
    )

    interpreter.run(ast)

# -------------------------
# SYNTAX ERRORS
# -------------------------

except MyLangSyntaxError as e:

    print(
        f"\nSYNTAX ERROR:\n{e}"
    )

# -------------------------
# RUNTIME ERRORS
# -------------------------

except MyLangRuntimeError as e:

    print(
        f"\nRUNTIME ERROR:\n{e}"
    )

# -------------------------
# INTERNAL ERRORS
# -------------------------

except Exception as e:

    print(
        f"\nINTERNAL ERROR:\n{e}"
    )