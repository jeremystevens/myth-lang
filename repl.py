from lexer import Lexer
from interpreter import Interpreter

VERSION = "MyLang REPL v0.2.0"

print(VERSION)
print("Type 'exit' to quit")
print("Type 'help' for commands")
print()

interpreter = Interpreter()

debug_tokens = False

while True:

    try:

        lines = []
        block_depth = 0

        # FIRST LINE
        first_line = input(">> ").strip()

        # EXIT
        if first_line.lower() == "exit":
            break

        # HELP
        if first_line.lower() == "help":

            print()
            print("Commands:")
            print("  exit         Quit REPL")
            print("  help         Show help")
            print("  tokens       Toggle token debug")
            print()

            continue

        # TOKEN DEBUG
        if first_line.lower() == "tokens":

            debug_tokens = not debug_tokens

            print(
                f"Token Debug = {debug_tokens}"
            )

            continue

        lines.append(first_line)

        # BLOCK STARTERS
        if (
            first_line.startswith("if")
            or
            first_line.startswith("while")
            or
            first_line.startswith("repeat")
            or
            first_line.startswith("function")
        ):
            block_depth += 1

        # MULTI-LINE MODE
        while block_depth > 0:

            line = input(".. ").strip()

            lines.append(line)

            if (
                line.startswith("if")
                or
                line.startswith("while")
                or
                line.startswith("repeat")
                or
                line.startswith("function")
            ):
                block_depth += 1

            elif line == "end":
                block_depth -= 1

        # JOIN CODE
        code = "\n".join(lines)

        # TOKENIZE
        lexer = Lexer(code)

        tokens = lexer.tokenize()

        # DEBUG TOKENS
        if debug_tokens:

            print()
            print("TOKENS:")
            print(tokens)
            print()

        # RUN
        interpreter.run(tokens)

    except Exception as e:

        print()
        print("ERROR:")
        print(e)
        print()