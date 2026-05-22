from stdlib import StandardLibrary


class Interpreter:

    def __init__(self):

        self.variables = {}
        self.functions = {}
        self.return_value = None

        self.stdlib = StandardLibrary()

    # -------------------------
    # ERROR HANDLING
    # -------------------------

    def runtime_error(self, line, message):

        raise Exception(
            f"Line {line}: {message}"
        )

    # -------------------------
    # EVALUATION
    # -------------------------

    def evaluate(self, expr, line=0):

        expr = str(expr).strip()

        # -------------------------
        # STRING
        # -------------------------

        if (
            expr.startswith('"')
            and
            expr.endswith('"')
        ):
            return expr[1:-1]

        # -------------------------
        # LIST
        # -------------------------

        if expr.startswith("[") and expr.endswith("]"):

            inner = expr[1:-1]

            if not inner.strip():
                return []

            items = inner.split(",")

            result = []

            for item in items:

                result.append(
                    self.evaluate(
                        item.strip(),
                        line
                    )
                )

            return result

        # -------------------------
        # BUILTIN upper
        # -------------------------

        if expr.startswith("upper "):

            value = expr[6:]

            return self.stdlib.upper(
                self.evaluate(value, line)
            )

        # -------------------------
        # BUILTIN lower
        # -------------------------

        if expr.startswith("lower "):

            value = expr[6:]

            return self.stdlib.lower(
                self.evaluate(value, line)
            )

        # -------------------------
        # BUILTIN length
        # -------------------------

        if expr.startswith("length "):

            value = expr[7:]

            return self.stdlib.length(
                self.evaluate(value, line)
            )

        # -------------------------
        # BUILTIN random
        # -------------------------

        if expr.startswith("random "):

            parts = expr.split()

            return self.stdlib.random(
                self.evaluate(parts[1], line),
                self.evaluate(parts[2], line)
            )

        # -------------------------
        # FUNCTION CALL
        # -------------------------

        parts = expr.split()

        if len(parts) > 0:

            function_name = parts[0]

            if function_name in self.functions:

                args = parts[1:]

                evaluated_args = []

                for arg in args:

                    evaluated_args.append(
                        self.evaluate(arg, line)
                    )

                return self.call_function(
                    function_name,
                    evaluated_args,
                    line
                )

        # -------------------------
        # ==
        # -------------------------

        if "==" in expr:

            left, right = expr.split(
                "==",
                1
            )

            return (
                self.evaluate(left, line)
                ==
                self.evaluate(right, line)
            )

        # -------------------------
        # >
        # -------------------------

        if ">" in expr:

            left, right = expr.split(
                ">",
                1
            )

            return (
                self.evaluate(left, line)
                >
                self.evaluate(right, line)
            )

        # -------------------------
        # <
        # -------------------------

        if "<" in expr:

            left, right = expr.split(
                "<",
                1
            )

            return (
                self.evaluate(left, line)
                <
                self.evaluate(right, line)
            )

        # -------------------------
        # +
        # -------------------------

        if "+" in expr:

            left, right = expr.split(
                "+",
                1
            )

            left = self.evaluate(left, line)
            right = self.evaluate(right, line)

            if (
                isinstance(left, int)
                and
                isinstance(right, int)
            ):
                return left + right

            return str(left) + str(right)

        # -------------------------
        # NUMBER
        # -------------------------

        if expr.isdigit():
            return int(expr)

        # -------------------------
        # VARIABLE
        # -------------------------

        if expr in self.variables:
            return self.variables[expr]

        # -------------------------
        # UNKNOWN VARIABLE
        # -------------------------

        if expr.isidentifier():

            self.runtime_error(
                line,
                f"Unknown variable: {expr}"
            )

        return expr

    # -------------------------
    # BLOCK FINDER
    # -------------------------

    def find_block_end(
        self,
        tokens,
        start_index
    ):

        depth = 1
        i = start_index

        while i < len(tokens):

            if tokens[i].type in [
                "IF",
                "WHILE",
                "REPEAT",
                "FUNCTION"
            ]:
                depth += 1

            elif tokens[i].type == "END":

                depth -= 1

                if depth == 0:
                    return i

            i += 1

        return len(tokens) - 1

    # -------------------------
    # FUNCTION CALLS
    # -------------------------

    def call_function(
        self,
        function_name,
        args,
        line
    ):

        if function_name not in self.functions:

            self.runtime_error(
                line,
                f"Unknown function: {function_name}"
            )

        function_data = self.functions[
            function_name
        ]

        params = function_data["params"]
        tokens = function_data["tokens"]

        old_variables = self.variables.copy()

        for i in range(len(params)):

            if i < len(args):

                self.variables[
                    params[i]
                ] = args[i]

        self.return_value = None

        self.run(tokens)

        result = self.return_value

        self.variables = old_variables

        return result

    # -------------------------
    # MAIN RUNTIME
    # -------------------------

    def run(self, tokens):

        i = 0

        while i < len(tokens):

            token = tokens[i]

            # -------------------------
            # ASSIGN
            # -------------------------

            if token.type == "ASSIGN":

                name, value = token.value

                self.variables[name] = (
                    self.evaluate(
                        value,
                        token.line
                    )
                )

            # -------------------------
            # INPUT
            # -------------------------

            elif token.type == "INPUT":

                name, prompt = token.value

                user_input = input(
                    self.evaluate(
                        prompt,
                        token.line
                    )
                )

                self.variables[name] = (
                    user_input
                )

            # -------------------------
            # PRINT
            # -------------------------

            elif token.type == "PRINT":

                print(
                    self.evaluate(
                        token.value,
                        token.line
                    )
                )

            # -------------------------
            # RETURN
            # -------------------------

            elif token.type == "RETURN":

                self.return_value = (
                    self.evaluate(
                        token.value,
                        token.line
                    )
                )

                return

            # -------------------------
            # FUNCTION
            # -------------------------

            elif token.type == "FUNCTION":

                function_name, params = (
                    token.value
                )

                block_start = i + 1

                block_end = (
                    self.find_block_end(
                        tokens,
                        block_start
                    )
                )

                function_tokens = (
                    tokens[
                        block_start:block_end
                    ]
                )

                self.functions[
                    function_name
                ] = {
                    "params": params,
                    "tokens": function_tokens
                }

                i = block_end

            # -------------------------
            # FUNCTION CALL
            # -------------------------

            elif token.type == "CALL":

                function_name, args = (
                    token.value
                )

                evaluated_args = []

                for arg in args:

                    evaluated_args.append(
                        self.evaluate(
                            arg,
                            token.line
                        )
                    )

                self.call_function(
                    function_name,
                    evaluated_args,
                    token.line
                )

            # -------------------------
            # REPEAT
            # -------------------------

            elif token.type == "REPEAT":

                count = self.evaluate(
                    token.value,
                    token.line
                )

                block_start = i + 1

                block_end = (
                    self.find_block_end(
                        tokens,
                        block_start
                    )
                )

                block_tokens = (
                    tokens[
                        block_start:block_end
                    ]
                )

                for _ in range(count):

                    self.run(block_tokens)

                i = block_end

            # -------------------------
            # WHILE
            # -------------------------

            elif token.type == "WHILE":

                block_start = i + 1

                block_end = (
                    self.find_block_end(
                        tokens,
                        block_start
                    )
                )

                block_tokens = (
                    tokens[
                        block_start:block_end
                    ]
                )

                while self.evaluate(
                    token.value,
                    token.line
                ):

                    self.run(block_tokens)

                i = block_end

            # -------------------------
            # IF
            # -------------------------

            elif token.type == "IF":

                condition_result = (
                    self.evaluate(
                        token.value,
                        token.line
                    )
                )

                block_start = i + 1

                block_end = (
                    self.find_block_end(
                        tokens,
                        block_start
                    )
                )

                else_pos = None

                j = block_start
                depth = 1

                while j < block_end:

                    if tokens[j].type == "IF":
                        depth += 1

                    elif tokens[j].type == "END":
                        depth -= 1

                    elif (
                        tokens[j].type
                        == "ELSE"
                    ):

                        if depth == 1:
                            else_pos = j

                    j += 1

                # TRUE BLOCK
                if condition_result:

                    if else_pos is not None:

                        true_block = (
                            tokens[
                                block_start:else_pos
                            ]
                        )

                    else:

                        true_block = (
                            tokens[
                                block_start:block_end
                            ]
                        )

                    self.run(true_block)

                # FALSE BLOCK
                else:

                    if else_pos is not None:

                        false_block = (
                            tokens[
                                else_pos + 1:block_end
                            ]
                        )

                        self.run(false_block)

                i = block_end

            i += 1