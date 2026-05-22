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
    opcode       : str
    operand      : Any = None
    line         : Optional[int] = None
    source_file  : str = "<unknown>"   # Phase 8b: which .my file
    ast_node_type: str = ""            # Phase 8b: originating AST node type

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

    def __init__(self, name: str = "<main>", source_file: str = "<unknown>"):
        self.name         = name
        self.source_file  = source_file
        self.instructions : list[Instruction] = []
        self.constants    : list = []
        self.sub_chunks   : dict = {}
        # Phase 8b: source map for this chunk
        from source_map import SourceMap
        self.source_map   = SourceMap(source_file)

    # ── Emit helpers ──────────────────────────────────────────────────────

    def emit(
        self,
        opcode       : str,
        operand      = None,
        line         : int  = None,
        source_file  : str  = None,
        ast_node_type: str  = "",
        was_optimised: bool = False,
        origin_line  : int  = 0,
    ) -> int:
        """
        Append an instruction and record it in the source map.
        Returns the instruction's index.
        """
        sf  = source_file or self.source_file
        ins = Instruction(
            opcode        = opcode,
            operand       = operand,
            line          = line,
            source_file   = sf,
            ast_node_type = ast_node_type,
        )
        idx = len(self.instructions)
        self.instructions.append(ins)

        # Register in source map
        if line:
            self.source_map.record(
                instruction_idx = idx,
                line            = line,
                ast_node_type   = ast_node_type,
                was_optimised   = was_optimised,
                origin_line     = origin_line,
                source_file     = sf,
            )

        return idx

    def patch_jump(self, idx: int):
        """
        Back-patch a JUMP* instruction at index idx so its operand
        points to the current end of the instruction list.
        """
        self.instructions[idx].operand = len(self.instructions)

    # ── Disassembler ──────────────────────────────────────────────────────

    def disassemble(self, indent: int = 0) -> str:
        pad   = "  " * indent
        lines = [
            f"{pad}=== chunk: {self.name} "
            f"({len(self.instructions)} instructions) "
            f"[{self.source_file}] ==="
        ]

        for i, ins in enumerate(self.instructions):
            # Phase 8b: show file:line and node type in disassembly
            loc   = self.source_map.get(i)
            src   = ""
            if loc and loc.line:
                fname = loc.source_file.split("/")[-1].split("\\")[-1]
                src   = f"  ; {fname}:{loc.line}"
                if loc.ast_node_type:
                    src += f" <{loc.ast_node_type}>"
                if loc.was_optimised:
                    src += " [opt]"
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

    Phase 8b: accepts source_file so every instruction is mapped
    back to its origin file.
    """

    def __init__(self, source_file: str = "<unknown>"):
        self.source_file = source_file

    def compile(self, nodes: list) -> Chunk:
        """Compile a top-level node list into the main chunk."""
        chunk = Chunk("<main>", source_file=self.source_file)
        self._compile_block(nodes, chunk)
        chunk.emit("HALT")
        return chunk

    # ── Source-aware emit helper ──────────────────────────────────────────

    def _emit(
        self,
        chunk        : Chunk,
        opcode       : str,
        operand      = None,
        node         = None,
        was_optimised: bool = False,
    ) -> int:
        """
        Emit an instruction with full source-map metadata.
        `node` is the originating AST node (for line + type).
        Phase 8b: reads _was_optimised and _origin_line from
        optimizer-folded nodes automatically.
        """
        line          = getattr(node, "line", None)
        ast_node_type = type(node).__name__ if node is not None else ""
        source_file   = getattr(node, "source_file", None) or self.source_file
        origin_line   = getattr(node, "_origin_line", None) or line or 0
        # Nodes tagged by optimizer carry _was_optimised = True
        was_opt       = was_optimised or getattr(node, "_was_optimised", False)

        return chunk.emit(
            opcode,
            operand,
            line          = line,
            source_file   = source_file,
            ast_node_type = ast_node_type,
            was_optimised = was_opt,
            origin_line   = origin_line,
        )

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
            self._emit(chunk, "PRINT", node=node)

        # ASSIGN
        elif t == "AssignNode":
            self._compile_expr(node.value, chunk)
            self._emit(chunk, "STORE_VAR", node.name, node=node)

        # RETURN
        elif t == "ReturnNode":
            if node.value is not None:
                self._compile_expr(node.value, chunk)
            else:
                self._emit(chunk, "PUSH_NULL", node=node)
            self._emit(chunk, "RETURN", node=node)

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
            self._emit(chunk, "POP", node=node)

        # STANDALONE METHOD CALL
        elif t == "MethodCallNode":
            self._compile_expr(node, chunk)
            self._emit(chunk, "POP", node=node)

        # PROPERTY ASSIGN
        elif t == "PropertyAssignNode":
            self._compile_expr(node.obj_expr, chunk)
            self._compile_expr(node.value, chunk)
            self._emit(chunk, "STORE_ATTR", node.property_name, node=node)

        # INDEX ASSIGN
        elif t == "IndexAssignNode":
            self._compile_expr(node.collection, chunk)
            self._compile_expr(node.index, chunk)
            self._compile_expr(node.value, chunk)
            self._emit(chunk, "INDEX_SET", node=node)

        # IMPORT
        elif t == "ImportNode":
            self._emit(chunk, "IMPORT", node.path, node=node)

        # FROM IMPORT
        elif t == "FromImportNode":
            self._emit(chunk, "FROM_IMPORT", (node.path, node.names), node=node)

        # EXPORT
        elif t == "ExportNode":
            self._emit(chunk, "EXPORT", node.name, node=node)

    # ── Control flow ──────────────────────────────────────────────────────

    def _compile_if(self, node, chunk: Chunk):
        self._compile_expr(node.condition, chunk)
        jump_to_else = self._emit(chunk, "JUMP_IF_FALSE", None, node=node)
        self._compile_block(node.true_body, chunk)
        if node.false_body:
            jump_past_else = self._emit(chunk, "JUMP", None, node=node)
            chunk.patch_jump(jump_to_else)
            self._compile_block(node.false_body, chunk)
            chunk.patch_jump(jump_past_else)
        else:
            chunk.patch_jump(jump_to_else)

    def _compile_while(self, node, chunk: Chunk):
        loop_start = len(chunk.instructions)
        self._compile_expr(node.condition, chunk)
        jump_out = self._emit(chunk, "JUMP_IF_FALSE", None, node=node)
        self._compile_block(node.body, chunk)
        self._emit(chunk, "JUMP", loop_start, node=node)
        chunk.patch_jump(jump_out)

    def _compile_for(self, node, chunk: Chunk):
        self._compile_expr(node.start, chunk)
        self._emit(chunk, "STORE_VAR", node.variable, node=node)
        loop_start = len(chunk.instructions)
        self._emit(chunk, "LOAD_VAR", node.variable, node=node)
        self._compile_expr(node.end, chunk)
        self._emit(chunk, "LE", node=node)
        jump_out = self._emit(chunk, "JUMP_IF_FALSE", None, node=node)
        self._compile_block(node.body, chunk)
        self._emit(chunk, "LOAD_VAR", node.variable, node=node)
        self._emit(chunk, "PUSH_INT", 1, node=node)
        self._emit(chunk, "ADD", node=node)
        self._emit(chunk, "STORE_VAR", node.variable, node=node)
        self._emit(chunk, "JUMP", loop_start, node=node)
        chunk.patch_jump(jump_out)

    def _compile_foreach(self, node, chunk: Chunk):
        self._compile_expr(node.iterable, chunk)
        tmp_iter  = f"__iter_{node.variable}"
        tmp_index = f"__idx_{node.variable}"
        self._emit(chunk, "STORE_VAR", tmp_iter, node=node)
        self._emit(chunk, "PUSH_INT", 0, node=node)
        self._emit(chunk, "STORE_VAR", tmp_index, node=node)
        loop_start = len(chunk.instructions)
        self._emit(chunk, "LOAD_VAR", tmp_index, node=node)
        self._emit(chunk, "LOAD_VAR", tmp_iter, node=node)
        self._emit(chunk, "CALL_BUILTIN", ("length", 1), node=node)
        self._emit(chunk, "LT", node=node)
        jump_out = self._emit(chunk, "JUMP_IF_FALSE", None, node=node)
        self._emit(chunk, "LOAD_VAR", tmp_iter, node=node)
        self._emit(chunk, "LOAD_VAR", tmp_index, node=node)
        self._emit(chunk, "INDEX_GET", node=node)
        self._emit(chunk, "STORE_VAR", node.variable, node=node)
        self._compile_block(node.body, chunk)
        self._emit(chunk, "LOAD_VAR", tmp_index, node=node)
        self._emit(chunk, "PUSH_INT", 1, node=node)
        self._emit(chunk, "ADD", node=node)
        self._emit(chunk, "STORE_VAR", tmp_index, node=node)
        self._emit(chunk, "JUMP", loop_start, node=node)
        chunk.patch_jump(jump_out)

    # ── Functions and classes ─────────────────────────────────────────────

    def _compile_function(self, node, chunk: Chunk):
        sub = Chunk(node.name, source_file=self.source_file)
        self._compile_block(node.body, sub)
        sub.emit("PUSH_NULL")
        sub.emit("RETURN")
        chunk.sub_chunks[node.name] = sub
        self._emit(chunk, "MAKE_FUNCTION", (node.name, node.params), node=node)

    def _compile_class(self, node, chunk: Chunk):
        init_chunk = Chunk(f"{node.name}.__init__", source_file=self.source_file)
        self._compile_block(node.init_body, init_chunk)
        init_chunk.emit("RETURN")

        method_chunks = {}
        for mname, mnode in node.methods.items():
            mc = Chunk(f"{node.name}.{mname}", source_file=self.source_file)
            self._compile_block(mnode.body, mc)
            mc.emit("PUSH_NULL")
            mc.emit("RETURN")
            method_chunks[mname] = mc

        chunk.sub_chunks[f"{node.name}.__init__"] = init_chunk
        for mname, mc in method_chunks.items():
            chunk.sub_chunks[f"{node.name}.{mname}"] = mc

        self._emit(
            chunk,
            "MAKE_CLASS",
            (node.name, node.params, list(method_chunks.keys())),
            node=node,
        )

    # ── Expressions ───────────────────────────────────────────────────────

    def _compile_expr(self, node, chunk: Chunk):
        if node is None:
            chunk.emit("PUSH_NULL")
            return

        t = type(node).__name__

        if t == "NumberNode":
            if isinstance(node.value, bool):
                self._emit(chunk, "PUSH_BOOL", node.value, node=node)
            else:
                self._emit(chunk, "PUSH_INT", node.value, node=node)

        elif t == "StringNode":
            self._emit(chunk, "PUSH_STR", node.value, node=node)

        elif t == "VariableNode":
            self._emit(chunk, "LOAD_VAR", node.name, node=node)

        elif t == "BinaryOperationNode":
            self._compile_expr(node.left, chunk)
            self._compile_expr(node.right, chunk)
            op_map = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV", "%": "MOD"}
            self._emit(chunk, op_map.get(node.operator, "ADD"), node=node)

        elif t == "CompareNode":
            self._compile_expr(node.left, chunk)
            self._compile_expr(node.right, chunk)
            op_map = {"==": "EQ", ">": "GT", "<": "LT"}
            self._emit(chunk, op_map.get(node.operator, "EQ"), node=node)

        elif t == "LogicalOperationNode":
            self._compile_logical(node, chunk)

        elif t == "UnaryOperationNode":
            self._compile_expr(node.operand, chunk)
            self._emit(chunk, "NOT" if node.operator == "not" else "NEG", node=node)

        elif t == "CallNode":
            self._compile_call(node, chunk)

        elif t == "MethodCallNode":
            self._compile_expr(node.obj_expr, chunk)
            for arg in node.args:
                self._compile_expr(arg, chunk)
            self._emit(chunk, "CALL_METHOD", (node.method_name, len(node.args)), node=node)

        elif t == "PropertyAccessNode":
            self._compile_expr(node.obj_expr, chunk)
            self._emit(chunk, "LOAD_ATTR", node.property_name, node=node)

        elif t == "IndexNode":
            self._compile_expr(node.collection, chunk)
            self._compile_expr(node.index, chunk)
            self._emit(chunk, "INDEX_GET", node=node)

        elif t == "ListNode":
            for elem in node.elements:
                self._compile_expr(elem, chunk)
            self._emit(chunk, "BUILD_LIST", len(node.elements), node=node)

        elif t == "DictionaryNode":
            for key, val in node.pairs.items():
                self._emit(chunk, "PUSH_STR", key, node=node)
                self._compile_expr(val, chunk)
            self._emit(chunk, "BUILD_DICT", len(node.pairs), node=node)

    def _compile_logical(self, node, chunk: Chunk):
        if node.operator == "and":
            self._compile_expr(node.left, chunk)
            self._emit(chunk, "DUP", node=node)
            jump_false = self._emit(chunk, "JUMP_IF_FALSE", None, node=node)
            self._emit(chunk, "POP", node=node)
            self._compile_expr(node.right, chunk)
            chunk.patch_jump(jump_false)
        elif node.operator == "or":
            self._compile_expr(node.left, chunk)
            self._emit(chunk, "DUP", node=node)
            jump_true = self._emit(chunk, "JUMP_IF_TRUE", None, node=node)
            self._emit(chunk, "POP", node=node)
            self._compile_expr(node.right, chunk)
            chunk.patch_jump(jump_true)

    def _compile_call(self, node: "CallNode", chunk: Chunk):
        from ast_interpreter import ASTInterpreter
        builtins = set(ASTInterpreter({}).builtins.keys()) if hasattr(ASTInterpreter, 'builtins') else set()
        for arg in node.args:
            self._compile_expr(arg, chunk)
        if node.name in builtins:
            self._emit(chunk, "CALL_BUILTIN", (node.name, len(node.args)), node=node)
        else:
            self._emit(chunk, "CALL", (node.name, len(node.args)), node=node)
