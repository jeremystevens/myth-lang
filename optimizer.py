# ruff: noqa: F403, F405
"""
optimizer.py — MyLang AST Optimiser  (Phase 7)
===============================================
Performs a single pass over the AST before execution,
rewriting nodes that can be evaluated at compile time.

Currently implemented passes
─────────────────────────────
1. CONSTANT FOLDING
   Reduces pure constant expressions to their result:

     BinaryOperationNode(NumberNode(2), '*', NumberNode(3))
     → NumberNode(6)

     BinaryOperationNode(StringNode("Hello "), '+', StringNode("World"))
     → StringNode("Hello World")

   This is safe when both operands are literals with no side
   effects.  Variables, function calls, and I/O are never folded.

2. DEAD BRANCH ELIMINATION
   When an if-condition is a constant, the unused branch is removed:

     if true        → keep only true_body
     if false       → keep only false_body

Usage
─────
    from optimizer import ASTOptimiser
    optimised_ast = ASTOptimiser().optimise(ast_nodes)
"""

from ast_nodes import *


# ---------------------------------------------------------------------------
# OPERATOR IMPLEMENTATIONS  (mirrors the interpreter exactly)
# ---------------------------------------------------------------------------

def _fold_binary(op: str, left, right):
    """
    Attempt to fold a binary operation on two literal values.
    Returns the folded result, or raises ValueError if not foldable.
    """

    if op == "+":
        if isinstance(left, int) and isinstance(right, int):
            return left + right
        if isinstance(left, str) or isinstance(right, str):
            return str(left) + str(right)

    elif op == "-":
        if isinstance(left, int) and isinstance(right, int):
            return left - right

    elif op == "*":
        if isinstance(left, int) and isinstance(right, int):
            return left * right

    elif op == "/":
        if isinstance(left, int) and isinstance(right, int):
            if right == 0:
                raise ValueError("Division by zero")
            return left // right

    elif op == "%":
        if isinstance(left, int) and isinstance(right, int):
            if right == 0:
                raise ValueError("Modulo by zero")
            return left % right

    raise ValueError(f"Cannot fold {type(left).__name__} {op} {type(right).__name__}")


def _fold_compare(op: str, left, right):
    """Fold a comparison between two literal values."""
    if op == "==": return left == right
    if op == ">":  return left > right
    if op == "<":  return left < right
    raise ValueError(f"Unknown comparison: {op}")


# ---------------------------------------------------------------------------
# LITERAL EXTRACTION
# ---------------------------------------------------------------------------

def _literal_value(node):
    """
    If node is a pure literal (NumberNode or StringNode), return its
    Python value.  Otherwise raise ValueError — signals not foldable.
    """
    if isinstance(node, NumberNode):
        return node.value
    if isinstance(node, StringNode):
        return node.value
    raise ValueError("Not a literal")


def _make_literal(value, line=None, origin_line=None):
    """
    Wrap a Python value back into the appropriate AST literal node.
    Attaches _origin_line so the compiler can mark it as optimised
    and preserve the original source location in the source map.
    """
    if isinstance(value, str):
        node = StringNode(value, line)
    else:
        node = NumberNode(value, line)
    # Phase 8b: tag with origin so source_map can show [opt]
    node._origin_line    = origin_line or line
    node._was_optimised  = True
    return node


# ---------------------------------------------------------------------------
# OPTIMISER
# ---------------------------------------------------------------------------

class ASTOptimiser:
    """
    Single-pass AST optimiser.  Call optimise(nodes) on the top-level
    node list returned by the parser.  Returns a new list of nodes with
    all constant expressions pre-evaluated.
    """

    def __init__(self):
        self.stats = {
            "folded_binary":   0,
            "folded_compare":  0,
            "dead_branches":   0,
            "nodes_visited":   0,
        }

    # ── Public entry point ────────────────────────────────────────────────

    def optimise(self, nodes: list) -> list:
        """Optimise a list of AST nodes and return the new list."""
        return [
            result
            for node in nodes
            for result in [self._opt_stmt(node)]
            if result is not None
        ]

    # ── Statement-level optimisation ──────────────────────────────────────

    def _opt_stmt(self, node):
        self.stats["nodes_visited"] += 1
        t = type(node).__name__

        if t == "PrintNode":
            return PrintNode(self._opt_expr(node.value), node.line)

        if t == "AssignNode":
            return AssignNode(node.name, self._opt_expr(node.value), node.line)

        if t == "ReturnNode":
            return ReturnNode(self._opt_expr(node.value), node.line)

        if t == "IfNode":
            return self._opt_if(node)

        if t == "WhileNode":
            return WhileNode(
                self._opt_expr(node.condition),
                self.optimise(node.body),
                node.line,
            )

        if t == "ForNode":
            return ForNode(
                node.variable,
                self._opt_expr(node.start),
                self._opt_expr(node.end),
                self.optimise(node.body),
                node.line,
            )

        if t == "ForEachNode":
            return ForEachNode(
                node.variable,
                self._opt_expr(node.iterable),
                self.optimise(node.body),
                node.line,
            )

        if t == "FunctionNode":
            return FunctionNode(
                node.name,
                node.params,
                self.optimise(node.body),
                node.line,
            )

        if t == "ClassNode":
            opt_init = self.optimise(node.init_body)
            opt_methods = {
                name: FunctionNode(
                    m.name,
                    m.params,
                    self.optimise(m.body),
                    m.line,
                )
                for name, m in node.methods.items()
            }
            return ClassNode(
                node.name, node.params,
                opt_init, opt_methods, node.line,
            )

        if t == "CallNode":
            opt_args = [self._opt_expr(a) for a in node.args]
            return CallNode(node.name, opt_args, node.line)

        if t == "MethodCallNode":
            opt_args = [self._opt_expr(a) for a in node.args]
            return MethodCallNode(
                node.obj_expr, node.method_name, opt_args, node.line
            )

        if t == "PropertyAssignNode":
            return PropertyAssignNode(
                node.obj_expr,
                node.property_name,
                self._opt_expr(node.value),
                node.line,
            )

        if t == "IndexAssignNode":
            return IndexAssignNode(
                node.collection,
                self._opt_expr(node.index),
                self._opt_expr(node.value),
                node.line,
            )

        # Nodes with no child expressions — return as-is
        return node

    # ── Dead branch elimination ───────────────────────────────────────────

    def _opt_if(self, node: IfNode):
        condition = self._opt_expr(node.condition)

        try:
            const_val = _literal_value(condition)
            # Condition is a constant — eliminate the dead branch
            self.stats["dead_branches"] += 1
            if const_val:
                return self.optimise(node.true_body) or [node]
            else:
                return self.optimise(node.false_body or []) or [node]
        except ValueError:
            pass

        # Non-constant condition — optimise both branches
        return IfNode(
            condition,
            self.optimise(node.true_body),
            self.optimise(node.false_body or []),
            node.line,
        )

    # ── Expression-level optimisation ─────────────────────────────────────

    def _opt_expr(self, node):
        """
        Recursively optimise an expression node.
        Returns either the original node or a simpler replacement.
        """
        if node is None:
            return node

        self.stats["nodes_visited"] += 1
        t = type(node).__name__

        # ── Constant folding: binary operations ──────────────────────
        if t == "BinaryOperationNode":
            left  = self._opt_expr(node.left)
            right = self._opt_expr(node.right)
            try:
                lv = _literal_value(left)
                rv = _literal_value(right)
                result = _fold_binary(node.operator, lv, rv)
                self.stats["folded_binary"] += 1
                return _make_literal(result, node.line, origin_line=node.line)
            except (ValueError, TypeError):
                return BinaryOperationNode(left, node.operator, right, node.line)

        # ── Constant folding: comparisons ────────────────────────────
        if t == "CompareNode":
            left  = self._opt_expr(node.left)
            right = self._opt_expr(node.right)
            try:
                lv = _literal_value(left)
                rv = _literal_value(right)
                result = _fold_compare(node.operator, lv, rv)
                self.stats["folded_compare"] += 1
                return _make_literal(result, node.line, origin_line=node.line)
            except (ValueError, TypeError):
                return CompareNode(left, node.operator, right, node.line)

        # ── Constant folding: unary operations ───────────────────────
        if t == "UnaryOperationNode":
            operand = self._opt_expr(node.operand)
            if node.operator == "not":
                try:
                    v = _literal_value(operand)
                    self.stats["folded_binary"] += 1
                    return _make_literal(not v, node.line, origin_line=node.line)
                except ValueError:
                    pass
            return UnaryOperationNode(node.operator, operand, node.line)

        # ── Logical operations — short-circuit folding ───────────────
        if t == "LogicalOperationNode":
            left  = self._opt_expr(node.left)
            right = self._opt_expr(node.right)
            try:
                lv = _literal_value(left)
                if node.operator == "and":
                    if not lv:
                        # false and X → false
                        self.stats["folded_binary"] += 1
                        return _make_literal(False, node.line, origin_line=node.line)
                    else:
                        # true and X → X
                        self.stats["folded_binary"] += 1
                        return right
                elif node.operator == "or":
                    if lv:
                        # true or X → true
                        self.stats["folded_binary"] += 1
                        return _make_literal(True, node.line, origin_line=node.line)
                    else:
                        # false or X → X
                        self.stats["folded_binary"] += 1
                        return right
            except ValueError:
                pass
            return LogicalOperationNode(left, node.operator, right, node.line)

        # ── Index access — optimise the index ────────────────────────
        if t == "IndexNode":
            return IndexNode(
                node.collection,
                self._opt_expr(node.index),
                node.line,
            )

        # ── List literal — optimise all elements ─────────────────────
        if t == "ListNode":
            return ListNode(
                [self._opt_expr(e) for e in node.elements],
                node.line,
            )

        # ── Call arguments ────────────────────────────────────────────
        if t == "CallNode":
            return CallNode(
                node.name,
                [self._opt_expr(a) for a in node.args],
                node.line,
            )

        if t == "MethodCallNode":
            return MethodCallNode(
                node.obj_expr,
                node.method_name,
                [self._opt_expr(a) for a in node.args],
                node.line,
            )

        # ── Literals and leaves — return unchanged ────────────────────
        return node

    # ── Reporting ─────────────────────────────────────────────────────────

    def report(self) -> str:
        s = self.stats
        return (
            f"Optimiser report:\n"
            f"  Nodes visited:      {s['nodes_visited']}\n"
            f"  Binary ops folded:  {s['folded_binary']}\n"
            f"  Comparisons folded: {s['folded_compare']}\n"
            f"  Dead branches cut:  {s['dead_branches']}\n"
        )
