# ruff: noqa: F403, F405
"""
vm.py — MyLang Stack-Based Virtual Machine  (Phase 7)
======================================================
Executes bytecode Chunks produced by compiler.py.

Architecture
────────────
The VM uses a classic stack-based design:

  ┌─────────────────────────────────────────────────────┐
  │  Value Stack         [ val, val, val, ... ]         │
  │  Call Stack          [ Frame, Frame, ... ]          │
  │  Program Counter     index into current Chunk        │
  └─────────────────────────────────────────────────────┘

Each Frame holds:
  - the Chunk being executed
  - the program counter (instruction index)
  - the local variable dict
  - the return address (caller's PC + frame index)

Execution model
───────────────
1. Instructions are fetched from the current Frame's Chunk
   at the current PC.
2. Each instruction manipulates the value stack and/or the
   environment.
3. CALL pushes a new Frame; RETURN pops it and leaves the
   return value on the stack.

This VM intentionally mirrors CPython's design at a high
level, making it easy to understand and extend.

Usage
─────
    from compiler import Compiler
    from optimizer import ASTOptimiser
    from vm import VM

    ast   = Parser(Lexer(code).tokenize()).parse()
    ast   = ASTOptimiser().optimise(ast)
    chunk = Compiler().compile(ast)

    vm = VM()
    vm.execute(chunk)
"""

from compiler import Chunk, Instruction
from ast_nodes import *
from source_map import VMRuntimeError, VMTraceFrame, SourceMap
import random as _random


# ---------------------------------------------------------------------------
# RUNTIME TYPES (reuse from interpreter where possible)
# ---------------------------------------------------------------------------

class VMObject:
    """An object instance in the VM."""
    def __init__(self, class_name, methods):
        self.class_name = class_name
        self.methods    = methods      # name → Chunk
        self.properties = {}

    def __repr__(self):
        return f"<{self.class_name} {self.properties}>"


class VMNamespace:
    """A module namespace in the VM."""
    def __init__(self, name, exports):
        self.name    = name
        self.exports = exports   # name → Chunk or value

    def __repr__(self):
        return f"<module '{self.name}'>"


# ---------------------------------------------------------------------------
# CALL FRAME
# ---------------------------------------------------------------------------

class Frame:
    def __init__(self, chunk: Chunk, locals_: dict = None, return_addr=None):
        self.chunk       = chunk
        self.pc          = 0
        self.locals      = locals_ or {}
        self.return_addr = return_addr   # (frame_index, pc) to restore

    def fetch(self) -> Instruction:
        ins     = self.chunk.instructions[self.pc]
        self.pc += 1
        return ins


# ---------------------------------------------------------------------------
# VIRTUAL MACHINE
# ---------------------------------------------------------------------------

class VM:
    """
    Executes a compiled Chunk.

    Phase 8b: tracks the current instruction's source location at all
    times and raises VMRuntimeError (from source_map.py) instead of
    plain Python exceptions — giving every VM error a full call-stack
    traceback mapped back to the original .my source lines.
    """

    def __init__(self):
        self.stack       : list  = []
        self.call_stack  : list  = []
        self.globals     : dict  = {}
        self.functions   : dict  = {}
        self.classes     : dict  = {}
        self.namespaces  : dict  = {}
        # Phase 8b: source tracking
        self._current_line   : int = 0
        self._current_file   : str = "<unknown>"
        self._source_lines   : dict = {}   # file → list[str]
        self._build_dispatch()
        self._build_builtins()

    # ── Execution entry point ──────────────────────────────────────────────

    def execute(self, chunk: Chunk) -> None:
        self._register_sub_chunks(chunk)
        frame = Frame(chunk, self.globals)
        self.call_stack = [frame]
        self._run()

    def load_source(self, source: str, file_path: str = "<unknown>"):
        """Cache source lines for traceback display."""
        self._source_lines[file_path] = source.splitlines()

    def _run(self):
        while self.call_stack:
            frame = self.call_stack[-1]

            if frame.pc >= len(frame.chunk.instructions):
                self.call_stack.pop()
                if self.call_stack:
                    self.stack.append(None)
                break

            ins = frame.fetch()

            # Phase 8b: update current source location
            if ins.line:
                self._current_line = ins.line
            if ins.source_file and ins.source_file != "<unknown>":
                self._current_file = ins.source_file

            handler = self._dispatch.get(ins.opcode)

            if handler is None:
                raise self._make_error(f"Unknown opcode: {ins.opcode}")

            try:
                result = handler(frame, ins)
            except VMRuntimeError:
                raise   # already wrapped — propagate
            except Exception as e:
                raise self._make_error(str(e)) from e

            if result == "HALT":
                break

    # ── Source-map error construction ──────────────────────────────────────

    def _make_error(self, message: str) -> "VMRuntimeError":
        """
        Build a VMRuntimeError with the current call stack mapped
        back to source locations.
        """
        from source_map import VMRuntimeError as VRE, VMTraceFrame, source_line_text

        frames = []
        for frame in self.call_stack:
            loc = frame.chunk.source_map.get(frame.pc - 1)
            if loc:
                line  = loc.line
                sfile = loc.source_file
            else:
                line  = self._current_line
                sfile = self._current_file

            src_lines = self._source_lines.get(sfile, [])
            src_text  = source_line_text(src_lines, line)

            frames.append(VMTraceFrame(
                chunk_name       = frame.chunk.name,
                source_file      = sfile,
                line             = line,
                instruction_idx  = frame.pc - 1,
                source_line_text = src_text,
            ))

        return VRE(
            message     = message,
            frames      = frames,
            source_file = self._current_file,
            line        = self._current_line,
        )

    # ── Dispatch table ─────────────────────────────────────────────────────

    def _build_dispatch(self):
        self._dispatch = {
            name[4:]: getattr(self, name)
            for name in dir(self)
            if name.startswith("_op_")
        }

    # ── Sub-chunk registration ─────────────────────────────────────────────

    def _register_sub_chunks(self, chunk: Chunk):
        for name, sub in chunk.sub_chunks.items():
            self.functions[name] = sub
            self._register_sub_chunks(sub)

    # ── Stack helpers ──────────────────────────────────────────────────────

    def push(self, val):      self.stack.append(val)
    def pop(self):            return self.stack.pop()
    def peek(self):           return self.stack[-1]

    # ── Opcode handlers ────────────────────────────────────────────────────

    def _op_HALT(self, frame, ins):
        return "HALT"

    # Stack ops
    def _op_PUSH_INT(self, frame, ins):  self.push(ins.operand)
    def _op_PUSH_STR(self, frame, ins):  self.push(ins.operand)
    def _op_PUSH_BOOL(self, frame, ins): self.push(ins.operand)
    def _op_PUSH_NULL(self, frame, ins): self.push(None)
    def _op_POP(self, frame, ins):       self.pop()
    def _op_DUP(self, frame, ins):       self.push(self.peek())

    # Variables
    def _op_LOAD_VAR(self, frame, ins):
        name = ins.operand
        # Check locals first, then globals
        if name in frame.locals:
            self.push(frame.locals[name])
        elif name in self.globals:
            self.push(self.globals[name])
        else:
            raise NameError(f"Undefined variable: {name}")

    def _op_STORE_VAR(self, frame, ins):
        frame.locals[ins.operand] = self.pop()

    # Arithmetic
    def _op_ADD(self, frame, ins):
        r, l = self.pop(), self.pop()
        if isinstance(l, str) or isinstance(r, str):
            self.push(str(l) + str(r))
        else:
            self.push(l + r)

    def _op_SUB(self, frame, ins): r = self.pop(); self.push(self.pop() - r)
    def _op_MUL(self, frame, ins): r = self.pop(); self.push(self.pop() * r)
    def _op_DIV(self, frame, ins): r = self.pop(); self.push(self.pop() // r)
    def _op_MOD(self, frame, ins): r = self.pop(); self.push(self.pop() % r)

    # Comparisons
    def _op_EQ(self, frame, ins):  r = self.pop(); self.push(self.pop() == r)
    def _op_GT(self, frame, ins):  r = self.pop(); self.push(self.pop() >  r)
    def _op_LT(self, frame, ins):  r = self.pop(); self.push(self.pop() <  r)
    def _op_LE(self, frame, ins):  r = self.pop(); self.push(self.pop() <= r)
    def _op_GE(self, frame, ins):  r = self.pop(); self.push(self.pop() >= r)
    def _op_NE(self, frame, ins):  r = self.pop(); self.push(self.pop() != r)

    # Logic
    def _op_NOT(self, frame, ins): self.push(not self.pop())
    def _op_NEG(self, frame, ins): self.push(-self.pop())

    # Control flow
    def _op_JUMP(self, frame, ins):
        frame.pc = ins.operand

    def _op_JUMP_IF_FALSE(self, frame, ins):
        val = self.pop()
        if not val:
            frame.pc = ins.operand

    def _op_JUMP_IF_TRUE(self, frame, ins):
        val = self.pop()
        if val:
            frame.pc = ins.operand

    # Output
    def _op_PRINT(self, frame, ins):
        val = self.pop()
        print(val)

    # Collections
    def _op_BUILD_LIST(self, frame, ins):
        n    = ins.operand
        items = [self.pop() for _ in range(n)]
        items.reverse()
        self.push(items)

    def _op_BUILD_DICT(self, frame, ins):
        n   = ins.operand
        d   = {}
        pairs = [(self.pop(), self.pop()) for _ in range(n)]
        for val, key in reversed(pairs):
            d[key] = val
        self.push(d)

    def _op_INDEX_GET(self, frame, ins):
        idx  = self.pop()
        coll = self.pop()
        self.push(coll[idx])

    def _op_INDEX_SET(self, frame, ins):
        val  = self.pop()
        idx  = self.pop()
        coll = self.pop()
        coll[idx] = val

    # Object operations
    def _op_LOAD_ATTR(self, frame, ins):
        obj  = self.pop()
        name = ins.operand
        if isinstance(obj, VMObject):
            self.push(obj.properties[name])
        elif isinstance(obj, VMNamespace):
            self.push(obj.exports.get(name))
        else:
            raise AttributeError(f"Cannot get attribute '{name}' on {type(obj).__name__}")

    def _op_STORE_ATTR(self, frame, ins):
        val  = self.pop()
        obj  = self.pop()
        if isinstance(obj, VMObject):
            obj.properties[ins.operand] = val
        else:
            raise AttributeError(f"Cannot set attribute on {type(obj).__name__}")

    def _op_CALL_METHOD(self, frame, ins):
        method_name, argc = ins.operand
        args = [self.pop() for _ in range(argc)]
        args.reverse()
        obj = self.pop()
        if isinstance(obj, VMObject):
            method_chunk = obj.methods.get(method_name)
            if method_chunk is None:
                raise NameError(f"No method '{method_name}' on {obj.class_name}")
            local = {"this": obj}
            local.update(dict(zip(method_chunk.params if hasattr(method_chunk, 'params') else [], args)))
            new_frame = Frame(method_chunk, local, return_addr=(len(self.call_stack)-1, frame.pc))
            self.call_stack.append(new_frame)

    # Functions
    def _op_MAKE_FUNCTION(self, frame, ins):
        name, params = ins.operand
        chunk = self.functions.get(name)
        if chunk:
            chunk.params = params
        frame.locals[name] = name   # register by name

    def _op_MAKE_CLASS(self, frame, ins):
        class_name, params, method_names = ins.operand
        self.classes[class_name] = (params, {
            m: self.functions.get(f"{class_name}.{m}")
            for m in method_names
        })

    def _op_CALL(self, frame, ins):
        name, argc = ins.operand
        args = [self.pop() for _ in range(argc)]
        args.reverse()

        # Class instantiation
        if name in self.classes:
            params, methods = self.classes[name]
            obj = VMObject(name, methods)
            init_chunk = self.functions.get(f"{name}.__init__")
            if init_chunk:
                local = {"this": obj}
                local.update(dict(zip(params, args)))
                new_frame = Frame(
                    init_chunk, local,
                    return_addr=(len(self.call_stack)-1, frame.pc)
                )
                self.call_stack.append(new_frame)
                # Run synchronously until this frame returns
                self._run_until_return(len(self.call_stack) - 1)
            self.push(obj)
            return

        # User function
        fn_chunk = self.functions.get(name)
        if fn_chunk is None:
            raise NameError(f"Undefined function: {name}")
        params = getattr(fn_chunk, 'params', [])
        local  = dict(zip(params, args))
        new_frame = Frame(fn_chunk, local)
        self.call_stack.append(new_frame)

    def _run_until_return(self, frame_idx: int):
        """Run until the frame at frame_idx has been popped."""
        while len(self.call_stack) > frame_idx:
            frame = self.call_stack[-1]
            if frame.pc >= len(frame.chunk.instructions):
                self.call_stack.pop()
                if self.call_stack:
                    self.stack.append(None)
                break
            ins = frame.fetch()
            handler = self._dispatch.get(ins.opcode)
            if handler:
                result = handler(frame, ins)
                if result == "HALT":
                    break

    def _op_RETURN(self, frame, ins):
        ret_val = self.pop() if self.stack else None
        self.call_stack.pop()
        if self.call_stack:
            self.stack.append(ret_val)

    # Builtins
    def _op_CALL_BUILTIN(self, frame, ins):
        name, argc = ins.operand
        args = [self.pop() for _ in range(argc)]
        args.reverse()
        fn = self._builtins.get(name)
        if fn is None:
            raise NameError(f"Unknown builtin: {name}")
        self.push(fn(args))

    # Modules
    def _op_IMPORT(self, frame, ins):
        pass   # Handled at a higher level in real use

    def _op_FROM_IMPORT(self, frame, ins):
        pass   # Handled at a higher level in real use

    def _op_EXPORT(self, frame, ins):
        pass   # Recorded during module execution

    # ── Built-in function table ────────────────────────────────────────────

    def _build_builtins(self):
        self._builtins = {
            "upper":        lambda a: str(a[0]).upper(),
            "lower":        lambda a: str(a[0]).lower(),
            "length":       lambda a: len(a[0]),
            "to_str":       lambda a: str(a[0]),
            "to_int":       lambda a: int(a[0]),
            "to_bool":      lambda a: bool(a[0]),
            "type_of":      lambda a: type(a[0]).__name__.upper(),
            "append":       lambda a: a[0] + [a[1]],
            "remove":       lambda a: [x for x in a[0] if x != a[1]],
            "first":        lambda a: a[0][0],
            "last":         lambda a: a[0][-1],
            "sort":         lambda a: sorted(a[0]),
            "reverse_list": lambda a: list(reversed(a[0])),
            "contains_item":lambda a: a[1] in a[0],
            "index_of":     lambda a: a[0].index(a[1]) if a[1] in a[0] else -1,
            "abs":          lambda a: abs(a[0]),
            "max":          lambda a: max(a[0], a[1]),
            "min":          lambda a: min(a[0], a[1]),
            "random":       lambda a: _random.randint(a[0], a[1]),
            "sqrt":         lambda a: int(a[0] ** 0.5),
            "pow":          lambda a: a[0] ** a[1],
            "floor":        lambda a: int(a[0]),
            "ceil":         lambda a: -(-a[0] // 1),
            "clamp":        lambda a: max(a[1], min(a[2], a[0])),
            "keys":         lambda a: list(a[0].keys()),
            "values":       lambda a: list(a[0].values()),
            "exists":       lambda a: a[1] in a[0],
            "get":          lambda a: a[0].get(a[1], a[2] if len(a) > 2 else None),
            "trim":         lambda a: str(a[0]).strip(),
            "replace":      lambda a: str(a[0]).replace(str(a[1]), str(a[2])),
            "split":        lambda a: str(a[0]).split(str(a[1])),
            "contains":     lambda a: str(a[1]) in str(a[0]),
            "starts_with":  lambda a: str(a[0]).startswith(str(a[1])),
            "ends_with":    lambda a: str(a[0]).endswith(str(a[1])),
            "repeat_str":   lambda a: str(a[0]) * int(a[1]),
            "reverse":      lambda a: str(a[0])[::-1],
            "print":        lambda a: (print(a[0]), None)[1],
        }
