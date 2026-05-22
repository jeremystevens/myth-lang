"""
parser_error.py — MyLang Phase 4 Syntax Error
==============================================
Provides rich formatted syntax errors with caret pointer.
"""


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
        Render a formatted syntax error with a caret pointer showing
        exactly where in the source the error was detected.
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

        # ── Source line with caret ────────────────────────────────────
        src = self.source_line
        if not src and source_lines and self.line:
            if 0 < self.line <= len(source_lines):
                src = source_lines[self.line - 1]

        if src:
            lines.append("")
            lines.append(f"    {src.rstrip()}")
            col = self.column if self.column is not None else 0
            lines.append(f"    {' ' * col}^")

        lines.append("")
        lines.append(sep)
        lines.append("")

        return "\n".join(lines)
