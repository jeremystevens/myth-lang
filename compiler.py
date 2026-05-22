# ruff: noqa: F403, F405
"""
compiler.py — MyLang Bytecode Compiler  (Phase 7)
==================================================
Compiles a MyLang AST into a flat sequence of Instructions.

Each Instruction has:
    opcode  : str   — the operation name
    operand : any   — optional argument (name, value, offset)
    line    : int   — source line for error reporting

Instruction Set
───────────────
Stack manipulation
  PUSH_INT   n         — push integer n
  PUSH_STR   s         — push string s
  PUSH_BOOL  b         — push boolean
  PUSH_NULL             — push None
  POP                   — discard top of stack
  DUP                   — duplicate top of stack

Variables
  LOAD_VAR   name      — push value of variable
  STORE_VAR  name      — pop and store into variable

Arithmetic & logic
  ADD, SUB, MUL, DIV, MOD
  EQ, GT, LT
  AND, OR, NOT

Control flow
  JUMP_IF_FALSE offset — pop; if falsy jump by offset
  JUMP          offset — unconditional jump
  JUMP_IF_TRUE  offset — pop; if truthy jump by offset

Functions
  CALL          name, argc  — call named function with argc args from stack
  CALL_BUILTIN  name, argc  — call builtin function
  RETURN                     — return top of stack from current function
  MAKE_FUNCTION name, params, body_chunk

Collections
  BUILD_LIST    n       — pop n items, push list
  BUILD_DICT    n       — pop n key/value pairs, push dict
  INDEX_GET              — pop index, pop collection, push result
  INDEX_SET              — pop value, pop index, pop collection

Output
  PRINT                  — pop and print top of stack

Objects (Phase 5)
  LOAD_ATTR   name       — pop object, push property
  STORE_ATTR  name       — pop value, pop object, set property
  CALL_METHOD name argc  — pop object + argc args, call method

Modules (Phase 6)
  IMPORT      path       — import module as namespace
  FROM_IMPORT path names — selective import
  LOAD_NS     name attr  — load from namespace

Usage
─────
    from compiler import Compiler
    from optimizer import ASTOptimiser

    ast    = Parser(Lexer(code).tokenize()).parse()
    ast    = ASTOptimiser().optimise(ast)
    chunk  = Compiler().compile(ast)
    chunk.disassemble()
"""

from ast_nodes import *
from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# INSTRUCTION
# ---------------------------------------------------------------------------

@dataclass
class Instruction:
    opcode  : str
    operand : Any = None
    line    : Optional[int] = None

    def __repr__(self):
        if self.operand is not None:
            return f"{self.opcode:<18} {self.operand!r}"
        return self.opcode


# ---------------------------------------------------------------------------
# CHUNK  (a compiled unit — top-level script or function body)
# ---------------------------------------------------------------------------

class Chunk:
    """
    A compiled sequence of instructions representing one execution unit.
    Top-level scripts and each function body get their own Chunk.
    """

    def __init__(self, name: str = "<main>"):
        self.name         = name
        self.instructions : list[Instruction] = []
        self.constants    : list = []        # constant pool
        self.sub_chunks   : dict = {}        # name → Chunk (functions)

    # ── Emit helpers ──────────────────────────────────────────────────────

    def emit(self, opcode: str, operand=None, line: int = None) -> int:
        """Append an instruction and return its index."""
        self.instructions.append(Instruction(opcode, operand, line))
        return len(self.instructions) - 1

    def patch_jump(self, idx: int):
        """
        Back-patch a JUMP* instruction at index idx so its operand
        points to the current end of the instruction list.
        The operand becomes an absolute instruction index.
        """
        self.instructions[idx].operand = len(self.instructions)

    # ── Disassembler ──────────────────────────────────────────────────────

    def disassemble(self, indent: int = 0) -> str:
        pad   = "  " * indent
        lines = [f"{pad}=== chunk: {self.name} ({len(self.instructions)} instructions) ==="]

        for i, ins in enumerate(self.instructions):
            src = f"  ; L{ins.line}" if ins.line else ""
            lines.append(f"{pad}  {i:04d}  {ins!r}{src}")

        for name, sub in self.sub_chunks.items():
            lines.append("")
            lines.append(sub.disassemble(indent + 1))

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# COMPILER
# ---------------------------------------------------------------------------

class Compiler:
    """
    Walks a MyLang AST and emits bytecode into a Chunk.

    The compiler does NOT execute any code — it only translates
    the AST structure into a flat instruction sequence.
    """

    def compile(self, nodes: list) -> Chunk:
        """Compile a top-level node list into the main chunk."""
        chunk = Chunk("<main>")
        self._compile_block(nodes, chunk)
        chunk.emit("HALT")
        return chunk

    # ── Block (list of statements) ────────────────────────────────────────

    def _compile_block(self, nodes: list, chunk: Chunk):
        for node in nodes:
            self._compile_stmt(node, chunk)

    # ── Statements ────────────────────────────────────────────────────────

    def _compile_stmt(self, node, chunk: Chunk):
        t = type(node).__name__

        # PRINT
        if t == "PrintNode":
            self._compile_expr(node.value, chunk)
            chunk.emit("PRINT", line=node.line)

        # ASSIGN
        elif t == "AssignNode":
            self._compile_expr(node.value, chunk)
            chunk.emit("STORE_VAR", node.name, node.line)

        # RETURN
        elif t == "ReturnNode":
            if node.value is not None:
                self._compile_expr(node.value, chunk)
            else:
                chunk.emit("PUSH_NULL", line=node.line)
            chunk.emit("RETURN", line=node.line)

        # IF
        elif t == "IfNode":
            self._compile_if(node, chunk)

        # WHILE
        elif t == "WhileNode":
            self._compile_while(node, chunk)

        # FOR
        elif t == "ForNode":
            self._compile_for(node, chunk)

        # FOREACH
        elif t == "ForEachNode":
            self._compile_foreach(node, chunk)

        # FUNCTION DEFINITION
        elif t == "FunctionNode":
            self._compile_function(node, chunk)

        # CLASS DEFINITION
        elif t == "ClassNode":
            self._compile_class(node, chunk)

        # STANDALONE CALL
        elif t == "CallNode":
            self._compile_call(node, chunk)
            chunk.emit("POP", line=node.line)  # discard return value

        # STANDALONE METHOD CALL
        elif t == "MethodCallNode":
            self._compile_expr(node, chunk)
            chunk.emit("POP", line=node.line)

        # PROPERTY ASSIGN
        elif t == "PropertyAssignNode":
            self._compile_expr(node.obj_expr, chunk)
            self._compile_expr(node.value, chunk)
            chunk.emit("STORE_ATTR", node.property_name, node.line)

        # INDEX ASSIGN
        elif t == "IndexAssignNode":
            self._compile_expr(node.collection, chunk)
            self._compile_expr(node.index, chunk)
            self._compile_expr(node.value, chunk)
            chunk.emit("INDEX_SET", line=node.line)

        # IMPORT
        elif t == "ImportNode":
            chunk.emit("IMPORT", node.path, node.line)

        # FROM IMPORT
        elif t == "FromImportNode":
            chunk.emit("FROM_IMPORT", (node.path, node.names), node.line)

        # EXPORT
        elif t == "ExportNode":
            chunk.emit("EXPORT", node.name, node.line)

    # ── Control flow ──────────────────────────────────────────────────────

    def _compile_if(self, node, chunk: Chunk):
        # Compile condition
        self._compile_expr(node.condition, chunk)

        # JUMP_IF_FALSE to else branch (back-patched)
        jump_to_else = chunk.emit("JUMP_IF_FALSE", None, node.line)

        # True branch
        self._compile_block(node.true_body, chunk)

        if node.false_body:
            # JUMP past the else branch (back-patched)
            jump_past_else = chunk.emit("JUMP", None, node.line)

            # Patch the JUMP_IF_FALSE to here (start of else)
            chunk.patch_jump(jump_to_else)

            # False branch
            self._compile_block(node.false_body, chunk)

            # Patch JUMP to here (past else)
            chunk.patch_jump(jump_past_else)
        else:
            chunk.patch_jump(jump_to_else)

    def _compile_while(self, node, chunk: Chunk):
        loop_start = len(chunk.instructions)

        self._compile_expr(node.condition, chunk)
        jump_out = chunk.emit("JUMP_IF_FALSE", None, node.line)

        self._compile_block(node.body, chunk)
        chunk.emit("JUMP", loop_start, node.line)   # back-edge

        chunk.patch_jump(jump_out)

    def _compile_for(self, node, chunk: Chunk):
        # Store loop variable = start
        self._compile_expr(node.start, chunk)
        chunk.emit("STORE_VAR", node.variable, node.line)

        loop_start = len(chunk.instructions)

        # Condition: variable <= end
        chunk.emit("LOAD_VAR", node.variable, node.line)
        self._compile_expr(node.end, chunk)
        chunk.emit("LE", line=node.line)    # <=  (not yet in parser, but in VM spec)
        jump_out = chunk.emit("JUMP_IF_FALSE", None, node.line)

        self._compile_block(node.body, chunk)

        # Increment
        chunk.emit("LOAD_VAR", node.variable, node.line)
        chunk.emit("PUSH_INT", 1, node.line)
        chunk.emit("ADD", line=node.line)
        chunk.emit("STORE_VAR", node.variable, node.line)

        chunk.emit("JUMP", loop_start, node.line)
        chunk.patch_jump(jump_out)

    def _compile_foreach(self, node, chunk: Chunk):
        # Compile the iterable, store in a hidden temp var
        self._compile_expr(node.iterable, chunk)
        tmp_iter  = f"__iter_{node.variable}"
        tmp_index = f"__idx_{node.variable}"
        chunk.emit("STORE_VAR", tmp_iter,  node.line)
        chunk.emit("PUSH_INT",  0,          node.line)
        chunk.emit("STORE_VAR", tmp_index, node.line)

        loop_start = len(chunk.instructions)

        # Condition: index < length(iter)
        chunk.emit("LOAD_VAR",  tmp_index, node.line)
        chunk.emit("LOAD_VAR",  tmp_iter,  node.line)
        chunk.emit("CALL_BUILTIN", ("length", 1), node.line)
        chunk.emit("LT", line=node.line)
        jump_out = chunk.emit("JUMP_IF_FALSE", None, node.line)

        # Load current element
        chunk.emit("LOAD_VAR",   tmp_iter,  node.line)
        chunk.emit("LOAD_VAR",   tmp_index, node.line)
        chunk.emit("INDEX_GET",  line=node.line)
        chunk.emit("STORE_VAR",  node.variable, node.line)

        self._compile_block(node.body, chunk)

        # Increment index
        chunk.emit("LOAD_VAR",  tmp_index, node.line)
        chunk.emit("PUSH_INT",  1,          node.line)
        chunk.emit("ADD",  line=node.line)
        chunk.emit("STORE_VAR", tmp_index, node.line)

        chunk.emit("JUMP", loop_start, node.line)
        chunk.patch_jump(jump_out)

    # ── Functions and classes ─────────────────────────────────────────────

    def _compile_function(self, node, chunk: Chunk):
        sub = Chunk(node.name)
        self._compile_block(node.body, sub)
        sub.emit("PUSH_NULL")
        sub.emit("RETURN")
        chunk.sub_chunks[node.name] = sub
        chunk.emit("MAKE_FUNCTION", (node.name, node.params), node.line)

    def _compile_class(self, node, chunk: Chunk):
        # Compile init body as a sub-chunk
        init_chunk = Chunk(f"{node.name}.__init__")
        self._compile_block(node.init_body, init_chunk)
        init_chunk.emit("RETURN")

        # Compile each method
        method_chunks = {}
        for mname, mnode in node.methods.items():
            mc = Chunk(f"{node.name}.{mname}")
            self._compile_block(mnode.body, mc)
            mc.emit("PUSH_NULL")
            mc.emit("RETURN")
            method_chunks[mname] = mc

        chunk.sub_chunks[f"{node.name}.__init__"] = init_chunk
        for mname, mc in method_chunks.items():
            chunk.sub_chunks[f"{node.name}.{mname}"] = mc

        chunk.emit(
            "MAKE_CLASS",
            (node.name, node.params, list(method_chunks.keys())),
            node.line,
        )

    # ── Expressions ───────────────────────────────────────────────────────

    def _compile_expr(self, node, chunk: Chunk):
        if node is None:
            chunk.emit("PUSH_NULL")
            return

        t = type(node).__name__

        if t == "NumberNode":
            if isinstance(node.value, bool):
                chunk.emit("PUSH_BOOL", node.value, node.line)
            else:
                chunk.emit("PUSH_INT", node.value, node.line)

        elif t == "StringNode":
            chunk.emit("PUSH_STR", node.value, node.line)

        elif t == "VariableNode":
            chunk.emit("LOAD_VAR", node.name, node.line)

        elif t == "BinaryOperationNode":
            self._compile_expr(node.left, chunk)
            self._compile_expr(node.right, chunk)
            op_map = {
                "+": "ADD", "-": "SUB",
                "*": "MUL", "/": "DIV", "%": "MOD",
            }
            chunk.emit(op_map.get(node.operator, "ADD"), line=node.line)

        elif t == "CompareNode":
            self._compile_expr(node.left, chunk)
            self._compile_expr(node.right, chunk)
            op_map = {"==": "EQ", ">": "GT", "<": "LT"}
            chunk.emit(op_map.get(node.operator, "EQ"), line=node.line)

        elif t == "LogicalOperationNode":
            self._compile_logical(node, chunk)

        elif t == "UnaryOperationNode":
            self._compile_expr(node.operand, chunk)
            chunk.emit("NOT" if node.operator == "not" else "NEG", line=node.line)

        elif t == "CallNode":
            self._compile_call(node, chunk)

        elif t == "MethodCallNode":
            self._compile_expr(node.obj_expr, chunk)
            for arg in node.args:
                self._compile_expr(arg, chunk)
            chunk.emit("CALL_METHOD", (node.method_name, len(node.args)), node.line)

        elif t == "PropertyAccessNode":
            self._compile_expr(node.obj_expr, chunk)
            chunk.emit("LOAD_ATTR", node.property_name, node.line)

        elif t == "IndexNode":
            self._compile_expr(node.collection, chunk)
            self._compile_expr(node.index, chunk)
            chunk.emit("INDEX_GET", line=node.line)

        elif t == "ListNode":
            for elem in node.elements:
                self._compile_expr(elem, chunk)
            chunk.emit("BUILD_LIST", len(node.elements), node.line)

        elif t == "DictionaryNode":
            for key, val in node.pairs.items():
                chunk.emit("PUSH_STR", key, node.line)
                self._compile_expr(val, chunk)
            chunk.emit("BUILD_DICT", len(node.pairs), node.line)

    def _compile_logical(self, node, chunk: Chunk):
        """Short-circuit AND / OR with conditional jumps."""
        if node.operator == "and":
            self._compile_expr(node.left, chunk)
            chunk.emit("DUP", line=node.line)
            jump_false = chunk.emit("JUMP_IF_FALSE", None, node.line)
            chunk.emit("POP", line=node.line)
            self._compile_expr(node.right, chunk)
            chunk.patch_jump(jump_false)

        elif node.operator == "or":
            self._compile_expr(node.left, chunk)
            chunk.emit("DUP", line=node.line)
            jump_true = chunk.emit("JUMP_IF_TRUE", None, node.line)
            chunk.emit("POP", line=node.line)
            self._compile_expr(node.right, chunk)
            chunk.patch_jump(jump_true)

    def _compile_call(self, node: CallNode, chunk: Chunk):
        from ast_interpreter import ASTInterpreter
        builtins = set(ASTInterpreter({}).builtins.keys()) if hasattr(ASTInterpreter, 'builtins') else set()
        for arg in node.args:
            self._compile_expr(arg, chunk)
        if node.name in builtins:
            chunk.emit("CALL_BUILTIN", (node.name, len(node.args)), node.line)
        else:
            chunk.emit("CALL", (node.name, len(node.args)), node.line)
