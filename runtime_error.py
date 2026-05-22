"""
runtime_error.py — MyLang Phase 4 Error System
================================================
Provides rich, Python-style tracebacks for runtime errors including:
  - Full call stack with function names and call-site line numbers
  - Source line display for every frame
  - Local variable snapshot at the error point
  - Module import chain when errors occur inside imported files
  - Caret-pointer syntax errors showing the exact column
"""


# ===========================================================================
# TRACE FRAME
# ===========================================================================

class TraceFrame:
    """
    One frame in a MyLang call stack traceback.
    Stored in MyLangRuntimeError.traceback.
    """

    def __init__(
        self,
        kind,
        name,
        line,
        source_line=None,
        file_path=None,
        locals_snapshot=None,
    ):

        # "function" | "module" | "import"
        self.kind           = kind

        # Function or module name
        self.name           = name

        # 1-based line number where the call / error occurred
        self.line           = line

        # The raw source text of that line (may be None)
        self.source_line    = source_line

        # The file this frame belongs to (may be None for inline code)
        self.file_path      = file_path

        # Snapshot of local variables at this frame (dict, may be None)
        self.locals_snapshot= locals_snapshot or {}

    def __repr__(self):
        return (
            f"TraceFrame({self.kind!r}, "
            f"{self.name!r}, "
            f"line={self.line})"
        )


# ===========================================================================
# RUNTIME ERROR
# ===========================================================================

class MyLangRuntimeError(Exception):
    """
    Raised for all runtime errors in the MyLang interpreter.

    Attributes
    ----------
    message     : str
        The short error description.
    line        : int | None
        The 1-based source line where the error occurred.
    traceback   : list[TraceFrame]
        Full call stack from outermost to innermost frame.
    error_type  : str
        Human-readable error category (e.g. "NameError", "TypeError").
    import_chain: list[dict]
        List of {path, line} dicts showing the import chain that led
        to the file where the error occurred (outermost import first).
    """

    def __init__(
        self,
        message,
        line=None,
        traceback=None,
        error_type=None,
        import_chain=None,
    ):

        self.message      = message
        self.line         = line
        self.traceback    = traceback or []
        self.error_type   = error_type or "RuntimeError"
        self.import_chain = import_chain or []

        # Build the short form used by str(e)
        if line is not None:
            super().__init__(f"Line {line}: {message}")
        else:
            super().__init__(message)

    # -----------------------------------------------------------------------

    def format_traceback(self, source_lines=None) -> str:
        """
        Render a full, human-readable traceback similar to Python's.

        Parameters
        ----------
        source_lines : list[str] | None
            The source lines of the top-level script, used to annotate
            frames that have no stored source_line.

        Returns
        -------
        str
            Multi-line formatted traceback string.
        """

        lines = []
        sep   = "─" * 60

        lines.append("")
        lines.append(sep)
        lines.append(f"  MyLang Traceback (most recent call last)")
        lines.append(sep)

        # ── Import chain (if error happened inside an imported module) ──
        if self.import_chain:
            lines.append("")
            lines.append("  Import chain:")
            for entry in self.import_chain:
                path = entry.get("path", "?")
                ln   = entry.get("line", "?")
                lines.append(f"    import '{path}'  at line {ln}")

        # ── Call stack frames ────────────────────────────────────────────
        if self.traceback:
            lines.append("")
            for frame in self.traceback:
                self._format_frame(frame, lines, source_lines)

        # ── Error itself ─────────────────────────────────────────────────
        lines.append("")
        lines.append(sep)

        loc = f"  Line {self.line}: " if self.line else "  "

        lines.append(
            f"{loc}{self.error_type}: {self.message}"
        )

        # Show the source line of the error with a caret if available
        src = self._get_source_line(
            self.line, None, source_lines
        )
        if src:
            lines.append("")
            lines.append(f"    {src.rstrip()}")
            lines.append(f"    {'─' * max(1, len(src.rstrip()))}")

        lines.append(sep)
        lines.append("")

        return "\n".join(lines)

    def _format_frame(self, frame, lines, source_lines):

        # ── Frame header ──────────────────────────────────────────────
        if frame.kind == "function":
            label = f"  In function  {frame.name}()"
        elif frame.kind == "import":
            label = f"  In module    {frame.name}"
        else:
            label = f"  In           {frame.name}"

        location = (
            f"  line {frame.line}"
            if frame.line
            else ""
        )

        if frame.file_path:
            location += f"  [{frame.file_path}]"

        lines.append(f"  ┌{'─' * 56}┐")
        lines.append(f"  │  {label:<54}│")
        if location:
            lines.append(f"  │  {location:<54}│")

        # ── Source line ───────────────────────────────────────────────
        src = self._get_source_line(
            frame.line,
            frame.source_line,
            source_lines if not frame.file_path else None,
        )
        if src:
            trimmed = src.strip()
            # Truncate long lines
            if len(trimmed) > 50:
                trimmed = trimmed[:47] + "..."
            lines.append(f"  │    ▶  {trimmed:<48}│")

        # ── Local variables ───────────────────────────────────────────
        if frame.locals_snapshot:
            lines.append(f"  │  {'Variables:':<54}│")
            for k, v in list(frame.locals_snapshot.items())[:5]:
                val_repr = repr(v)
                if len(val_repr) > 35:
                    val_repr = val_repr[:32] + "..."
                entry = f"    {k} = {val_repr}"
                lines.append(f"  │  {entry:<54}│")
            if len(frame.locals_snapshot) > 5:
                more = len(frame.locals_snapshot) - 5
                lines.append(
                    f"  │    ... and {more} more variable(s)"
                    f"{'':>{54 - 26 - len(str(more))}}│"
                )

        lines.append(f"  └{'─' * 56}┘")

    @staticmethod
    def _get_source_line(line_num, stored_line, source_lines):
        if stored_line:
            return stored_line
        if source_lines and line_num and 0 < line_num <= len(source_lines):
            return source_lines[line_num - 1]
        return None


# ===========================================================================
# SYNTAX ERROR
# ===========================================================================

class MyLangSyntaxError(Exception):
    """
    Raised during lexing or parsing.

    Attributes
    ----------
    message     : str
    line        : int | None
    column      : int | None
        0-based column of the error token (used for caret display).
    source_line : str | None
        The raw text of the offending line.
    """

    def __init__(
        self,
        message,
        line=None,
        column=None,
        source_line=None,
    ):

        self.message     = message
        self.line        = line
        self.column      = column
        self.source_line = source_line

        if line is not None:
            super().__init__(f"Line {line}: {message}")
        else:
            super().__init__(message)

    # -----------------------------------------------------------------------

    def format_traceback(self, source_lines=None) -> str:
        """
        Render a formatted syntax error with a caret pointer.
        """

        lines = []
        sep   = "─" * 60

        lines.append("")
        lines.append(sep)
        lines.append("  MyLang SyntaxError")
        lines.append(sep)
        lines.append("")

        loc = f"  Line {self.line}: " if self.line else "  "
        lines.append(f"{loc}{self.message}")

        # Show the offending line with a caret
        src = self.source_line
        if not src and source_lines and self.line:
            if 0 < self.line <= len(source_lines):
                src = source_lines[self.line - 1]

        if src:
            lines.append("")
            lines.append(f"    {src.rstrip()}")
            # Place caret at the column if known
            col = self.column if self.column is not None else 0
            lines.append(f"    {' ' * col}^")

        lines.append("")
        lines.append(sep)
        lines.append("")

        return "\n".join(lines)
