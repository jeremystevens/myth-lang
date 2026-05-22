"""
source_map.py — MYTH Lang Source Map System  (Phase 8b)
========================================================
Connects every layer of the execution pipeline back to the
original source code that produced it.

Pipeline
────────
  Source code (.my)
      ↓  lexer
  Tokens  (line numbers)
      ↓  parser
  AST nodes  (line + source_file)
      ↓  optimizer
  Optimised AST  (line preserved, _origin tracks pre-fold location)
      ↓  compiler
  Bytecode instructions  (line + source_file + ast_node_type)
      ↓  SourceMap
  SourceLocation records  (idx → file, line, node_type)
      ↓  VM
  VMTraceback  (call stack with file + line per frame)

Public API
──────────
  SourceLocation       — one mapping record
  SourceMap            — instruction-index → SourceLocation table
  VMTraceFrame         — one frame in a VM call stack
  VMRuntimeError       — VM error with full traceback attached
  format_vm_traceback  — renders a VMTraceback as a display string
"""

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# SOURCE LOCATION
# ---------------------------------------------------------------------------

@dataclass
class SourceLocation:
    """
    Maps one bytecode instruction index back to its source origin.

    Attributes
    ----------
    instruction_idx : int   — 0-based index in the chunk's instruction list
    source_file     : str   — path to the .my file (or '<repl>' / '<string>')
    line            : int   — 1-based source line number
    ast_node_type   : str   — type name of the AST node that produced this
                              instruction (e.g. 'BinaryOperationNode')
    was_optimised   : bool  — True if this node was rewritten by the optimiser
    origin_line     : int   — the original source line before optimisation
                              (same as line if not optimised)
    """

    instruction_idx : int
    source_file     : str   = "<unknown>"
    line            : int   = 0
    ast_node_type   : str   = ""
    was_optimised   : bool  = False
    origin_line     : int   = 0

    def __post_init__(self):
        if self.origin_line == 0:
            self.origin_line = self.line

    def __repr__(self):
        opt = " [opt]" if self.was_optimised else ""
        return (
            f"SourceLocation("
            f"idx={self.instruction_idx}, "
            f"{self.source_file}:{self.line}"
            f"{opt})"
        )


# ---------------------------------------------------------------------------
# SOURCE MAP
# ---------------------------------------------------------------------------

class SourceMap:
    """
    A lookup table from instruction index → SourceLocation.

    Built by the Compiler as it emits instructions.
    Travels with the Chunk it belongs to.

    Usage
    ─────
        loc = chunk.source_map.get(instruction_idx)
        if loc:
            print(f"{loc.source_file}:{loc.line}")
    """

    def __init__(self, source_file: str = "<unknown>"):
        self.source_file  = source_file
        self._entries: dict[int, SourceLocation] = {}

    def record(
        self,
        instruction_idx : int,
        line            : int,
        ast_node_type   : str  = "",
        was_optimised   : bool = False,
        origin_line     : int  = 0,
        source_file     : str  = None,
    ) -> SourceLocation:
        """
        Record a mapping for one instruction index.
        Returns the created SourceLocation.
        """
        loc = SourceLocation(
            instruction_idx = instruction_idx,
            source_file     = source_file or self.source_file,
            line            = line or 0,
            ast_node_type   = ast_node_type,
            was_optimised   = was_optimised,
            origin_line     = origin_line or line or 0,
        )
        self._entries[instruction_idx] = loc
        return loc

    def get(self, instruction_idx: int) -> Optional[SourceLocation]:
        """Return the SourceLocation for an instruction, or None."""
        return self._entries.get(instruction_idx)

    def lookup_line(self, instruction_idx: int) -> int:
        """Return the source line for an instruction, or 0."""
        loc = self._entries.get(instruction_idx)
        return loc.line if loc else 0

    def lookup_file(self, instruction_idx: int) -> str:
        """Return the source file for an instruction."""
        loc = self._entries.get(instruction_idx)
        return loc.source_file if loc else "<unknown>"

    def all_entries(self) -> list:
        """Return all SourceLocations sorted by instruction index."""
        return sorted(self._entries.values(), key=lambda e: e.instruction_idx)

    def summary(self) -> str:
        """Human-readable summary of the source map."""
        lines = [f"SourceMap ({len(self._entries)} entries, file={self.source_file})"]
        for loc in self.all_entries():
            opt = " [opt]" if loc.was_optimised else ""
            lines.append(
                f"  {loc.instruction_idx:04d}  "
                f"{loc.source_file}:{loc.line}"
                f"  <{loc.ast_node_type}>{opt}"
            )
        return "\n".join(lines)

    def __len__(self):
        return len(self._entries)


# ---------------------------------------------------------------------------
# VM TRACE FRAME
# ---------------------------------------------------------------------------

@dataclass
class VMTraceFrame:
    """
    One frame in a VM call stack traceback.

    Attributes
    ----------
    chunk_name      : str  — function/method name or '<main>'
    source_file     : str  — which .my file this frame lives in
    line            : int  — source line at the point of the call/error
    instruction_idx : int  — PC value when this frame was captured
    source_line_text: str  — the raw text of the source line (if available)
    """

    chunk_name      : str = "<main>"
    source_file     : str = "<unknown>"
    line            : int = 0
    instruction_idx : int = 0
    source_line_text: str = ""

    def __repr__(self):
        return (
            f"VMTraceFrame("
            f"{self.chunk_name}, "
            f"{self.source_file}:{self.line})"
        )


# ---------------------------------------------------------------------------
# VM RUNTIME ERROR
# ---------------------------------------------------------------------------

class VMRuntimeError(Exception):
    """
    A runtime error raised by the VM with full source-map context.

    Attributes
    ----------
    message     : str
    frames      : list[VMTraceFrame]  — call stack at error time
    source_file : str
    line        : int
    """

    def __init__(
        self,
        message     : str,
        frames      : list  = None,
        source_file : str   = "<unknown>",
        line        : int   = 0,
    ):
        super().__init__(message)
        self.message     = message
        self.frames      = frames or []
        self.source_file = source_file
        self.line        = line

    def format_traceback(self) -> str:
        return format_vm_traceback(self)


# ---------------------------------------------------------------------------
# TRACEBACK FORMATTER
# ---------------------------------------------------------------------------

def format_vm_traceback(error: VMRuntimeError) -> str:
    """
    Render a VM traceback in a clean, professional format:

    ────────────────────────────────────────────────────────────
      MYTH Lang VM Traceback (most recent call last)
    ────────────────────────────────────────────────────────────

      at <main>              game.my : 12
      at calculate_damage()  game.my : 42
         ▶  total = hp / 0

    ────────────────────────────────────────────────────────────
      Line 42: VMRuntimeError: Division by zero
    ────────────────────────────────────────────────────────────
    """

    sep   = "─" * 60
    lines = ["", sep, "  MYTH Lang VM Traceback (most recent call last)", sep]

    if error.frames:
        lines.append("")
        for frame in error.frames:
            name = frame.chunk_name
            file = frame.source_file
            ln   = frame.line
            lines.append(f"  at {name:<22} {file} : {ln}")
            if frame.source_line_text:
                lines.append(f"     ▶  {frame.source_line_text.strip()}")

    lines.append("")
    lines.append(sep)
    loc = f"  Line {error.line}: " if error.line else "  "
    lines.append(f"{loc}VMRuntimeError: {error.message}")
    lines.append(sep)
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SOURCE MAP UTILITIES
# ---------------------------------------------------------------------------

def source_line_text(
    source_lines: list,
    line_num    : int,
) -> str:
    """
    Safely retrieve the text of a 1-based source line.
    Returns empty string if out of range.
    """
    if source_lines and 0 < line_num <= len(source_lines):
        return source_lines[line_num - 1]
    return ""


def build_source_index(source: str) -> list:
    """
    Split source text into a list of lines for fast 1-based lookup.
    """
    return source.splitlines()
