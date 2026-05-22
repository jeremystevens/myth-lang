from ast_nodes import *

from parser_error import (
    MyLangSyntaxError
)


class Parser:

    def __init__(self, tokens):

        self.tokens = tokens
        self.position = 0

        self.current_expression_line = None

    # -------------------------
    # TOKEN HELPERS
    # -------------------------

    def current_token(self):

        if self.position < len(self.tokens):
            return self.tokens[self.position]

        return None

    def advance(self):

        self.position += 1

    # -------------------------
    # FIND OPERATOR OUTSIDE
    # -------------------------

    def find_operator_outside(
        self,
        expr,
        operator
    ):

        # ─────────────────────────────────────────
        # Search RIGHT-TO-LEFT for the operator so
        # that binary expressions are LEFT-associative.
        #
        # Scanning left-to-right splits a + b + c
        # as left="a", right="b + c", producing:
        #   add(a, add(b, c))   ← right-associative WRONG
        #
        # Scanning right-to-left splits it as
        # left="a + b", right="c", producing:
        #   add(add(a, b), c)   ← left-associative CORRECT
        #
        # == uses left-to-right (non-associative).
        # ─────────────────────────────────────────

        n = len(expr)

        if operator == "==":

            # Left-to-right scan for ==
            depth = 0
            in_string = False
            i = 0
            while i < n:
                ch = expr[i]
                if ch == '"':
                    in_string = not in_string
                elif not in_string:
                    if ch in "([{":
                        depth += 1
                    elif ch in ")]}":
                        depth -= 1
                    if depth == 0 and expr[i:i+2] == "==":
                        return (expr[:i], expr[i+2:])
                i += 1
            return None

        # ── Right-to-left scan for all other operators ──────────────
        # Build position-level metadata in one forward pass:
        #   depth_at[i]  — bracket depth at position i
        #   in_str_at[i] — True if position i is inside a string

        depth_at  = [0] * n
        in_str_at = [False] * n

        d = 0
        s = False
        for i in range(n):
            ch = expr[i]
            if ch == '"':
                s = not s
            elif not s:
                if ch in "([{":
                    d += 1
                elif ch in ")]}":
                    d -= 1
            depth_at[i]  = d
            in_str_at[i] = s

        op_len = len(operator)
        i = n - op_len

        while i >= 0:

            if (
                not in_str_at[i]
                and depth_at[i] == 0
                and expr[i:i+op_len] == operator
            ):

                left  = expr[:i]
                right = expr[i+op_len:]

                # Guard: skip if nothing meaningful
                # on the left (unary sign).
                if left.strip():
                    return (left, right)

            i -= 1

        return None

    # -------------------------
    # SPLIT ARGUMENTS
    # -------------------------

    def split_arguments(self, expr):

        args = []

        current = ""

        depth = 0
        in_string = False

        for char in expr:

            if char == '"':

                in_string = not in_string

            if not in_string:

                if char in "([{":
                    depth += 1

                elif char in ")]}":
                    depth -= 1

            if (
                char == ","
                and
                depth == 0
                and
                not in_string
            ):

                args.append(
                    current.strip()
                )

                current = ""

            else:

                current += char

        if current.strip():

            args.append(
                current.strip()
            )

        return args

    # -------------------------
    # PARSE INDEX CHAIN
    # -------------------------

    def parse_index_chain(
        self,
        expr,
        line
    ):

        base_name = ""

        i = 0

        while (
            i < len(expr)
            and
            expr[i] != "["
        ):

            base_name += expr[i]
            i += 1

        node = VariableNode(
            base_name.strip(),
            line
        )

        while i < len(expr):

            if expr[i] == "[":

                depth = 1
                i += 1

                start = i

                while (
                    i < len(expr)
                    and
                    depth > 0
                ):

                    if expr[i] == "[":
                        depth += 1

                    elif expr[i] == "]":
                        depth -= 1

                    i += 1

                index_expr = (
                    expr[start:i-1]
                )

                node = IndexNode(
                    node,
                    self.parse_expression(
                        index_expr,
                        line
                    ),
                    line
                )

        return node

    # -------------------------
    # PRIMARY EXPRESSIONS
    # -------------------------

    def parse_primary(self, expr):

        expr = expr.strip()

        line = self.current_expression_line

        # STRING
        if (
            expr.startswith('"')
            and
            expr.endswith('"')
        ):

            raw = expr[1:-1]

            # Process escape sequences so that
            # \n, \t, and \\ work inside string
            # literals, matching what virtually
            # every beginner language supports.
            raw = raw.replace("\\n", "\n")
            raw = raw.replace("\\t", "\t")
            raw = raw.replace("\\\\", "\\")

            return StringNode(
                raw,
                line
            )

        # NUMBER (positive integer)
        if expr.isdigit():

            return NumberNode(
                int(expr),
                line
            )

        # NUMBER (multi-digit positive integer
        # e.g. "123" — isdigit() handles single
        # digits; this handles the general case)
        try:
            return NumberNode(int(expr), line)
        except ValueError:
            pass

        # NEGATIVE NUMBER LITERAL
        # Handles -42, -0, etc. so that negative
        # literals passed as function arguments
        # are not mis-parsed as subtraction.
        if (
            expr.startswith("-")
            and
            expr[1:].isdigit()
        ):

            return NumberNode(
                -int(expr[1:]),
                line
            )

        # PARENTHESES
        if (
            expr.startswith("(")
            and
            expr.endswith(")")
        ):

            return self.parse_expression(
                expr[1:-1],
                line
            )

        # FUNCTION CALL
        # ─────────────────────────────────────────
        # Guard: only treat expr as a call when
        # the text before the first ( is a valid
        # simple identifier.  Without this guard,
        # an expression like:
        #
        #   "rolled" + to_str(score)
        #
        # would be mistakenly parsed as a call
        # with name '"rolled" + to_str' because
        # expr.index("(") finds the ( inside
        # to_str, not the start of a call.
        #
        # A valid call name: only letters, digits,
        # underscores, and dots (for future method
        # syntax).  No spaces, quotes, or operators.

        if (
            "(" in expr
            and
            expr.endswith(")")
        ):

            # Find the FIRST ( at depth 0 that
            # could open a call argument list.
            call_open = -1
            _depth = 0
            _in_str = False
            for _i, _ch in enumerate(expr):
                if _ch == '"':
                    _in_str = not _in_str
                elif not _in_str:
                    if _ch in "([{":
                        _depth += 1
                    elif _ch in ")]}":
                        _depth -= 1
                    if _ch == "(" and _depth == 1:
                        call_open = _i
                        break

            if call_open > 0:

                function_name = (
                    expr[:call_open].strip()
                )

                # Validate: must be a simple
                # identifier (letters, digits,
                # underscores only — no operators,
                # quotes, or whitespace).
                import re as _re
                _valid = bool(
                    _re.match(
                        r'^[A-Za-z_][A-Za-z0-9_]*$',
                        function_name
                    )
                )

                if _valid:

                    args_string = (
                        expr[call_open + 1:-1]
                    )

                    raw_args = (
                        self.split_arguments(
                            args_string
                        )
                    )

                    parsed_args = []

                    for arg in raw_args:

                        parsed_args.append(
                            self.parse_expression(
                                arg,
                                line
                            )
                        )

                    return CallNode(
                        function_name,
                        parsed_args,
                        line
                    )

        # INDEX CHAIN
        if (
            "[" in expr
            and
            expr.endswith("]")
            and
            not expr.startswith("[")
        ):

            return self.parse_index_chain(
                expr,
                line
            )

        # DICTIONARY
        if (
            expr.startswith("{")
            and
            expr.endswith("}")
        ):

            inner = expr[1:-1].strip()

            pairs = []

            if inner:

                raw_pairs = self.split_arguments(
                    inner
                )

                for pair in raw_pairs:

                    if ":" not in pair:

                        raise MyLangSyntaxError(
                            "Invalid dictionary syntax",
                            line
                        )

                    key, value = pair.split(
                        ":",
                        1
                    )

                    parsed_key = (
                        self.parse_expression(
                            key.strip(),
                            line
                        )
                    )

                    parsed_value = (
                        self.parse_expression(
                            value.strip(),
                            line
                        )
                    )

                    pairs.append(
                        (
                            parsed_key,
                            parsed_value
                        )
                    )

            return DictionaryNode(
                pairs,
                line
            )

        # LIST
        if (
            expr.startswith("[")
            and
            expr.endswith("]")
        ):

            inner = expr[1:-1].strip()

            elements = []

            if inner:

                raw_elements = (
                    self.split_arguments(
                        inner
                    )
                )

                for element in raw_elements:

                    elements.append(
                        self.parse_expression(
                            element,
                            line
                        )
                    )

            return ListNode(
                elements,
                line
            )

        # VARIABLE
        return VariableNode(
            expr,
            line
        )

    # -------------------------
    # MULTIPLICATION / DIVISION
    # -------------------------

    def parse_multiplication(self, expr):

        line = self.current_expression_line

        for operator in ["*", "/", "%"]:

            result = self.find_operator_outside(
                expr,
                operator
            )

            if result:

                left, right = result

                return BinaryOperationNode(
                    self.parse_multiplication(left),
                    operator,
                    self.parse_primary(right),
                    line
                )

        return self.parse_primary(expr)

    # -------------------------
    # ADDITION / SUBTRACTION
    # -------------------------

    def parse_addition(self, expr):

        line = self.current_expression_line

        for operator in ["+", "-"]:

            result = self.find_operator_outside(
                expr,
                operator
            )

            if result:

                left, right = result

                return BinaryOperationNode(
                    self.parse_addition(left),
                    operator,
                    self.parse_multiplication(right),
                    line
                )

        return self.parse_multiplication(expr)

    # -------------------------
    # COMPARISON
    # -------------------------

    def parse_comparison(self, expr):

        line = self.current_expression_line

        for operator in ["==", ">", "<"]:

            result = self.find_operator_outside(
                expr,
                operator
            )

            if result:

                left, right = result

                return CompareNode(
                    self.parse_expression(left, line),
                    operator,
                    self.parse_expression(right, line),
                    line
                )

        return self.parse_addition(expr)

    # -------------------------
    # NOT
    # -------------------------

    def parse_not(self, expr):

        expr = expr.strip()

        line = self.current_expression_line

        if expr.startswith("not "):

            return UnaryOperationNode(
                "not",
                self.parse_comparison(
                    expr[4:]
                ),
                line
            )

        return self.parse_comparison(expr)

    # -------------------------
    # BOOLEAN AND
    # -------------------------

    def parse_and(self, expr):

        result = self.find_operator_outside(
            expr,
            " and "
        )

        line = self.current_expression_line

        if result:

            left, right = result

            return LogicalOperationNode(
                self.parse_expression(left, line),
                "and",
                self.parse_expression(right, line),
                line
            )

        return self.parse_not(expr)

    # -------------------------
    # BOOLEAN OR
    # -------------------------

    def parse_or(self, expr):

        result = self.find_operator_outside(
            expr,
            " or "
        )

        line = self.current_expression_line

        if result:

            left, right = result

            return LogicalOperationNode(
                self.parse_expression(left, line),
                "or",
                self.parse_expression(right, line),
                line
            )

        return self.parse_and(expr)

    # -------------------------
    # MAIN EXPRESSION PARSER
    # -------------------------

    def parse_expression(
        self,
        expr,
        line=None
    ):

        if line is not None:

            self.current_expression_line = line

        return self.parse_or(expr)

    # -------------------------
    # BLOCK PARSER
    # -------------------------

    def parse_block(
        self,
        owner_token
    ):

        body = []

        while (
            self.current_token()
            and
            self.current_token().type
            not in ["END", "ELSE"]
        ):

            statement = self.parse_statement()

            if statement:
                body.append(statement)

        if not self.current_token():

            raise MyLangSyntaxError(
                f"Missing END statement for "
                f"{owner_token.type}",
                owner_token.line
            )

        return body

    # -------------------------
    # STATEMENTS
    # -------------------------

    def parse_statement(self):

        token = self.current_token()

        # PRINT
        if token.type == "PRINT":

            node = PrintNode(
                self.parse_expression(
                    token.value,
                    token.line
                ),
                token.line
            )

            self.advance()

            return node

        # INDEX ASSIGNMENT
        elif (
            token.type == "ASSIGN"
            and
            "[" in token.value[0]
        ):

            target, value = token.value

            target_node = (
                self.parse_expression(
                    target,
                    token.line
                )
            )

            if not isinstance(
                target_node,
                IndexNode
            ):

                raise MyLangSyntaxError(
                    "Invalid index assignment",
                    token.line
                )

            node = IndexAssignNode(
                target_node.collection,
                target_node.index,
                self.parse_expression(
                    value,
                    token.line
                ),
                token.line
            )

            self.advance()

            return node

        # ASSIGN
        elif token.type == "ASSIGN":

            name, value = token.value

            node = AssignNode(
                name,
                self.parse_expression(
                    value,
                    token.line
                ),
                token.line
            )

            self.advance()

            return node

        # RETURN
        elif token.type == "RETURN":

            node = ReturnNode(
                self.parse_expression(
                    token.value,
                    token.line
                ),
                token.line
            )

            self.advance()

            return node

        # FUNCTION
        elif token.type == "FUNCTION":

            name, params = token.value

            self.advance()

            body = self.parse_block(
                token
            )

            self.advance()

            return FunctionNode(
                name,
                params,
                body,
                token.line
            )

        # IF
        elif token.type == "IF":

            condition = self.parse_expression(
                token.value,
                token.line
            )

            self.advance()

            true_body = self.parse_block(
                token
            )

            false_body = []

            if (
                self.current_token()
                and
                self.current_token().type == "ELSE"
            ):

                self.advance()

                false_body = self.parse_block(
                    token
                )

            self.advance()

            return IfNode(
                condition,
                true_body,
                false_body,
                token.line
            )

        # WHILE
        elif token.type == "WHILE":

            condition = self.parse_expression(
                token.value,
                token.line
            )

            self.advance()

            body = self.parse_block(
                token
            )

            self.advance()

            return WhileNode(
                condition,
                body,
                token.line
            )

        # FOR
        elif token.type == "FOR":

            variable, start, end = token.value

            self.advance()

            body = self.parse_block(
                token
            )

            self.advance()

            return ForNode(
                variable,
                self.parse_expression(
                    start,
                    token.line
                ),
                self.parse_expression(
                    end,
                    token.line
                ),
                body,
                token.line
            )

        # FOREACH
        elif token.type == "FOREACH":

            variable, iterable = token.value

            self.advance()

            body = self.parse_block(
                token
            )

            self.advance()

            return ForEachNode(
                variable,
                self.parse_expression(
                    iterable,
                    token.line
                ),
                body,
                token.line
            )

        # IMPORT
        elif token.type == "IMPORT":

            node = ImportNode(
                token.value,
                token.line
            )

            self.advance()

            return node

        # CALL
        elif token.type == "CALL":

            name, args = token.value

            parsed_args = []

            for arg in args:

                parsed_args.append(
                    self.parse_expression(
                        arg,
                        token.line
                    )
                )

            self.advance()

            return CallNode(
                name,
                parsed_args,
                token.line
            )

        return None

    # -------------------------
    # MAIN PARSER
    # -------------------------

    def parse(self):

        nodes = []

        while self.current_token():

            statement = self.parse_statement()

            if statement:
                nodes.append(statement)

        return nodes