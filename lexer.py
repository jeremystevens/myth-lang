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

            # CALL
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

                raise Exception(
                    f"Line {line_number}: "
                    f"Unknown syntax: {line}"
                )

        return self.tokens