from lexer import Lexer
from parser import Parser
from ast_interpreter import ASTInterpreter
from optimizer import ASTOptimiser

from runtime_error import (
    MyLangRuntimeError
)

from parser_error import (
    MyLangSyntaxError
)

import os
import sys

VERSION = "0.9.0"

MAIN_DIR = os.path.abspath(
    os.path.dirname(__file__)
)

# -------------------------
# FLAGS
# -------------------------

flags      = [a for a in sys.argv[1:] if a.startswith("--")]
args       = [a for a in sys.argv[1:] if not a.startswith("--")]

SHOW_BYTECODE = "--bytecode" in flags
NO_OPTIMISE   = "--no-opt"   in flags

# -------------------------
# ARGUMENT HANDLING
# -------------------------

if args:
    arg = args[0]
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
        "regression_test.my"
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

print(f"MyLang v{VERSION}")

try:

    # -------------------------
    # LEXER
    # -------------------------

    lexer  = Lexer(code)
    tokens = lexer.tokenize()

    # -------------------------
    # PARSER
    # -------------------------

    parser    = Parser(tokens)
    ast_nodes = parser.parse()

    # -------------------------
    # OPTIMISER  (Phase 7)
    # -------------------------

    if not NO_OPTIMISE:
        opt       = ASTOptimiser()
        ast_nodes = opt.optimise(ast_nodes)

    # -------------------------
    # BYTECODE EXPLORATION
    # -------------------------

    if SHOW_BYTECODE:
        from compiler import Compiler
        chunk = Compiler().compile(ast_nodes)
        print("\n" + chunk.disassemble())
        print()

    # -------------------------
    # INTERPRETER
    # -------------------------

    print("\nOUTPUT:")

    interpreter = ASTInterpreter(
        module_search_paths=[script_dir],
        file_root=script_dir
    )

    interpreter.set_source(code, file_path=SCRIPT)

    interpreter.run(ast_nodes)

except MyLangSyntaxError as e:

    print(
        e.format_traceback(source_lines)
    )

except MyLangRuntimeError as e:

    if not e.traceback and 'interpreter' in dir():
        interpreter._enrich_error(e)

    print(
        e.format_traceback(source_lines)
    )

except Exception as e:

    print(
        f"\nINTERNAL ERROR:\n{e}"
    )
