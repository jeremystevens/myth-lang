import re

from parser_error import MyLangSyntaxError


class Token:

    def __init__(
        self,
        token_type,
        value,
        line
    ):

        self.type = token_type
        self.value = value
        self.line = line

    def __repr__(self):

        if self.value is not None:

            return (
                f"{self.type}:{self.value}"
            )

        return self.type


class Lexer:

    def __init__(self, source_code):

        self.source_code = source_code
        self.tokens = []

    # -------------------------
    # BALANCED CHECK
    # -------------------------

    def is_balanced(self, text):

        pairs = {
            "(": ")",
            "[": "]",
            "{": "}"
        }

        stack = []

        in_string = False

        for char in text:

            if char == '"':

                in_string = not in_string

            elif not in_string:

                if char in pairs:

                    stack.append(char)

                elif char in pairs.values():

                    if not stack:
                        return False

                    opening = stack.pop()

                    if pairs[opening] != char:
                        return False

        return len(stack) == 0

    # -------------------------
    # MAIN TOKENIZER
    # -------------------------

    def tokenize(self):

        lines = self.source_code.splitlines()

        i = 0

        while i < len(lines):

            raw_line = lines[i]

            line_number = i + 1

            line = raw_line.strip()

            i += 1

            # EMPTY
            if not line:
                continue

            # COMMENTS
            if line.startswith("#"):
                continue

            # MULTILINE ACCUMULATION
            if (
                "=" in line
                and
                not self.is_balanced(line)
            ):

                combined = line

                while (
                    i < len(lines)
                    and
                    not self.is_balanced(combined)
                ):

                    combined += " " + (
                        lines[i].strip()
                    )

                    i += 1

                line = combined

            # PRINT
            if line.startswith("print "):

                value = line[6:].strip()

                self.tokens.append(
                    Token(
                        "PRINT",
                        value,
                        line_number
                    )
                )

            # IF
            elif line.startswith("if "):

                condition = (
                    line[3:].strip()
                )

                # Strip optional trailing 'then'
                # keyword so that both:
                #   if x < y then
                #   if x < y
                # produce the same token value.
                if condition.endswith(" then"):
                    condition = condition[:-5].strip()
                elif condition == "then":
                    condition = ""

                self.tokens.append(
                    Token(
                        "IF",
                        condition,
                        line_number
                    )
                )

            # ELSE
            elif line == "else":

                self.tokens.append(
                    Token(
                        "ELSE",
                        None,
                        line_number
                    )
                )

            # WHILE
            elif line.startswith("while "):

                condition = (
                    line[6:].strip()
                )

                # Strip optional trailing 'then'
                # for consistency with IF.
                if condition.endswith(" then"):
                    condition = condition[:-5].strip()

                self.tokens.append(
                    Token(
                        "WHILE",
                        condition,
                        line_number
                    )
                )

            # FOR
            elif line.startswith("for "):

                remaining = (
                    line[4:].strip()
                )

                variable, range_part = (
                    remaining.split(
                        "=",
                        1
                    )
                )

                start, end = (
                    range_part.split(
                        "to"
                    )
                )

                self.tokens.append(
                    Token(
                        "FOR",
                        (
                            variable.strip(),
                            start.strip(),
                            end.strip()
                        ),
                        line_number
                    )
                )

            # FOREACH
            elif line.startswith("foreach "):

                remaining = (
                    line[8:].strip()
                )

                variable, iterable = (
                    remaining.split(
                        "in",
                        1
                    )
                )

                self.tokens.append(
                    Token(
                        "FOREACH",
                        (
                            variable.strip(),
                            iterable.strip()
                        ),
                        line_number
                    )
                )

            # FUNCTION
            elif line.startswith("function "):

                remaining = (
                    line[9:].strip()
                )

                parts = remaining.split()

                name = parts[0]

                params = parts[1:]

                self.tokens.append(
                    Token(
                        "FUNCTION",
                        (
                            name,
                            params
                        ),
                        line_number
                    )
                )

            # RETURN
            elif line.startswith("return "):

                value = (
                    line[7:].strip()
                )

                self.tokens.append(
                    Token(
                        "RETURN",
                        value,
                        line_number
                    )
                )

            # END
            elif line == "end":

                self.tokens.append(
                    Token(
                        "END",
                        None,
                        line_number
                    )
                )

            # IMPORT
            elif line.startswith("import "):

                module_path = line[7:].strip()

                self.tokens.append(
                    Token(
                        "IMPORT",
                        module_path,
                        line_number
                    )
                )

            # CLASS
            elif line.startswith("class "):

                class_name = line[6:].strip()

                self.tokens.append(
                    Token(
                        "CLASS",
                        class_name,
                        line_number
                    )
                )

            # INIT (constructor inside class)
            elif line.startswith("init ") or line == "init":

                params_str = (
                    line[5:].strip()
                    if line.startswith("init ")
                    else ""
                )

                params = (
                    params_str.split()
                    if params_str
                    else []
                )

                self.tokens.append(
                    Token(
                        "INIT",
                        params,
                        line_number
                    )
                )

            # METHOD (method inside class)
            elif line.startswith("method "):

                rest   = line[7:].strip()

                # Strip trailing () for zero-param methods
                # e.g. "method is_alive()" → name="is_alive", params=[]
                if rest.endswith("()"):
                    rest = rest[:-2].strip()

                parts  = rest.split()
                mname  = parts[0] if parts else ""
                params = parts[1:] if len(parts) > 1 else []

                self.tokens.append(
                    Token(
                        "METHOD",
                        (mname, params),
                        line_number
                    )
                )

            # CALL
            # ─────────────────────────────────────
            # A standalone function call on its own
            # line.  Must have the form:
            #
            #   identifier(args)
            #
            # `print(...)` is treated as the print
            # keyword so both styles work:
            #   print "hello"
            #   print("hello")

            elif (
                "(" in line
                and
                line.endswith(")")
                and
                "=" not in line
                and
                not line.startswith("print ")
            ):

                function_name = (
                    line[:line.index("(")]
                    .strip()
                )

                args_string = (
                    line[
                        line.index("(")+1:-1
                    ]
                )

                # ── print(...) → treat as PRINT ──
                if function_name == "print":

                    self.tokens.append(
                        Token(
                            "PRINT",
                            args_string.strip(),
                            line_number
                        )
                    )

                # ── obj.method(...) → METHOD_CALL token ──
                elif re.match(
                    r'^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$',
                    function_name
                ):

                    obj_name, mname = function_name.split(".", 1)

                    args = []
                    if args_string.strip():
                        args = [
                            arg.strip()
                            for arg in
                            args_string.split(",")
                        ]

                    self.tokens.append(
                        Token(
                            "METHOD_CALL",
                            (obj_name, mname, args),
                            line_number
                        )
                    )

                # ── Validate: name must be an identifier ──
                elif not re.match(
                    r'^[A-Za-z_][A-Za-z0-9_]*$',
                    function_name
                ):

                    raise MyLangSyntaxError(
                        f"Invalid function call syntax: "
                        f"'{function_name}' is not a valid "
                        f"function name",
                        line_number
                    )

                else:

                    args = []

                    if args_string.strip():

                        args = [
                            arg.strip()
                            for arg in
                            args_string.split(",")
                        ]

                    self.tokens.append(
                        Token(
                            "CALL",
                            (
                                function_name,
                                args
                            ),
                            line_number
                        )
                    )

            # PROPERTY ASSIGNMENT  obj.prop = value  /  this.prop = value
            elif (
                "." in line
                and "=" in line
                and not line.startswith("if ")
                and not line.startswith("while ")
            ):
                # Split on first '=' to get left and right sides
                dot_eq = line.split("=", 1)
                lhs    = dot_eq[0].strip()   # e.g. "this.hp"  "obj.name"
                rhs    = dot_eq[1].strip()   # value expression

                # Only treat as prop assign if lhs is obj.prop pattern
                if re.match(
                    r'^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$',
                    lhs
                ):
                    obj_name, prop_name = lhs.split(".", 1)

                    self.tokens.append(
                        Token(
                            "PROP_ASSIGN",
                            (obj_name, prop_name, rhs),
                            line_number
                        )
                    )

                else:
                    # Fall through to regular assignment
                    name, value = line.split("=", 1)

                    self.tokens.append(
                        Token(
                            "ASSIGN",
                            (name.strip(), value.strip()),
                            line_number
                        )
                    )

            # ASSIGNMENT
            elif "=" in line:

                name, value = (
                    line.split(
                        "=",
                        1
                    )
                )

                self.tokens.append(
                    Token(
                        "ASSIGN",
                        (
                            name.strip(),
                            value.strip()
                        ),
                        line_number
                    )
                )

            # UNKNOWN
            else:

                # ── Detect BASIC-style bare calls ─────────────────────
                # Pattern: identifier followed by arguments without parens
                # e.g.  greet "Jeremy"   add 10 20   length players
                # Give a specific, actionable error rather than a generic
                # "Unknown syntax" message.

                _bare_call = re.match(
                    r'^([A-Za-z_][A-Za-z0-9_]*)\s+(.+)$',
                    line.strip()
                )

                if _bare_call:

                    name    = _bare_call.group(1)
                    raw_args= _bare_call.group(2).strip()

                    # Build a suggested parenthesized call
                    # Split raw args on spaces for the suggestion
                    suggested_args = ", ".join(
                        a for a in raw_args.split()
                        if a
                    )
                    suggestion = (
                        f"{name}({suggested_args})"
                    )

                    raise MyLangSyntaxError(
                        f"Function calls require parentheses.\n"
                        f"\n"
                        f"  Invalid:  {line.strip()}\n"
                        f"  Valid:    {suggestion}",
                        line_number
                    )

                raise MyLangSyntaxError(
                    f"Unknown syntax: {line}",
                    line_number
                )

        return self.tokens