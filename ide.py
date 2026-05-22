"""
MyLang IDE — Phase 4  (PySide6)
================================
QBasic-inspired, modern-feel development environment for MyLang.

Phase 4 adds:
  • Autocomplete popup  — triggered after 2 chars, Ctrl+Space to force
  • Function signature hints  — shown when cursor is inside a call
  • Symbol table  — live extraction of functions, variables, imports
  • Module navigation panel  — symbol tree with jump-to-definition
  • Find References  — Shift+F12 / right-click to find all uses
  • Go to Definition  — F12 jumps to where a function is defined
  • Code formatter  — Shift+Alt+F auto-formats the whole document
  • Project explorer upgrade  — two tabs: Files and Symbols

Install:
    pip install PySide6

Run:
    python ide.py
    python ide.py examples/hello.my
"""

import sys
import os
import io
import re
import json
import zipfile
import shutil
import pathlib
import tempfile
import subprocess
import urllib.request
import urllib.error
import threading
import traceback

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QSplitter,
    QPlainTextEdit, QTextEdit, QTreeWidget, QTreeWidgetItem,
    QToolBar, QStatusBar, QDockWidget, QMenuBar, QMenu,
    QFileDialog, QMessageBox, QLabel, QComboBox, QFrame,
    QVBoxLayout, QHBoxLayout, QSizePolicy, QPushButton,
    QDialog, QDialogButtonBox, QSpinBox, QFormLayout,
    QTabWidget, QToolButton, QHeaderView, QAbstractItemView,
    QListWidget, QListWidgetItem, QLineEdit,
)
from PySide6.QtGui import (
    QFont, QFontMetrics, QColor, QPainter, QTextFormat,
    QSyntaxHighlighter, QTextCharFormat, QKeySequence,
    QAction, QPalette, QTextCursor, QIcon, QTextOption,
    QPen, QBrush,
)
from PySide6.QtCore import (
    Qt, QRect, QSize, QThread, Signal, QObject,
    QTimer, QRegularExpression, QPoint, QProcess,
    QProcessEnvironment,
)

# ---------------------------------------------------------------------------
# MyLang runtime
# ---------------------------------------------------------------------------

IDE_DIR = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, IDE_DIR)

from lexer import Lexer
from parser import Parser
from ast_interpreter import ASTInterpreter
from runtime_error import MyLangRuntimeError
from parser_error import MyLangSyntaxError
import ast_nodes as AN

VERSION   = "0.8.0"
IDE_PHASE = "Phase 4"

# ===========================================================================
# BUILTIN CATALOGUE  (name → signature string)
# ===========================================================================

BUILTINS = {
    # String
    "upper":       ("upper(s)",              "Convert string to uppercase"),
    "lower":       ("lower(s)",              "Convert string to lowercase"),
    "length":      ("length(s)",             "Length of string, list, or dict"),
    "trim":        ("trim(s)",               "Strip leading/trailing whitespace"),
    "replace":     ("replace(s, old, new)",  "Replace all occurrences"),
    "split":       ("split(s, delim)",       "Split string into list"),
    "contains":    ("contains(s, sub)",      "True if s contains sub"),
    "starts_with": ("starts_with(s, pre)",   "True if s starts with pre"),
    "ends_with":   ("ends_with(s, suf)",     "True if s ends with suf"),
    "repeat_str":  ("repeat_str(s, n)",      "Repeat string n times"),
    "reverse":     ("reverse(s)",            "Reverse a string"),
    # Math
    "abs":         ("abs(n)",                "Absolute value"),
    "max":         ("max(a, b)",             "Larger of two numbers"),
    "min":         ("min(a, b)",             "Smaller of two numbers"),
    "pow":         ("pow(base, exp)",        "Raise to a power"),
    "floor":       ("floor(n)",              "Round down to integer"),
    "ceil":        ("ceil(n)",               "Round up to integer"),
    "sqrt":        ("sqrt(n)",               "Integer square root"),
    "clamp":       ("clamp(val, lo, hi)",    "Constrain value to range"),
    "random":      ("random(a, b)",          "Random integer between a and b"),
    # List
    "append":      ("append(list, item)",    "Add item to end of list"),
    "remove":      ("remove(list, item)",    "Remove first occurrence"),
    "first":       ("first(list)",           "Return first element"),
    "last":        ("last(list)",            "Return last element"),
    "reverse_list":("reverse_list(list)",    "Return reversed list"),
    "slice":       ("slice(list, start, end)","Return sub-list"),
    "contains_item":("contains_item(list, val)","True if val in list"),
    "sort":        ("sort(list)",            "Return sorted list"),
    "index_of":    ("index_of(list, val)",   "Index of val, or -1"),
    "flatten":     ("flatten(list)",         "Collapse one level of nesting"),
    # Dict
    "keys":        ("keys(dict)",            "Return list of keys"),
    "values":      ("values(dict)",          "Return list of values"),
    "exists":      ("exists(dict, key)",     "True if key in dict"),
    "get":         ("get(dict, key, default)","Return value or default"),
    "delete":      ("delete(dict, key)",     "Remove key, return dict"),
    "merge":       ("merge(a, b)",           "Combine two dicts"),
    # Type
    "to_int":      ("to_int(v)",             "Convert to integer"),
    "to_str":      ("to_str(v)",             "Convert to string"),
    "to_bool":     ("to_bool(v)",            "Convert to boolean"),
    "type_of":     ("type_of(v)",            "Return type name string"),
    # IO
    "input":       ("input(prompt?)",        "Read a line from stdin"),
    "read_file":   ("read_file(path)",       "Read entire file as string"),
    "write_file":  ("write_file(path, content)","Write string to file"),
    "append_file": ("append_file(path, content)","Append string to file"),
    "file_exists": ("file_exists(path)",     "True if file exists"),
    "delete_file": ("delete_file(path)",     "Delete a file"),
}

KEYWORDS = [
    "print","if","else","end","while","for","foreach",
    "function","return","import","in","to","and","or","not",
]

# ===========================================================================
# SYMBOL TABLE
# ===========================================================================

class SymbolTable:
    """
    Extracted from the AST after each analysis pass.
    Provides all the data needed by autocomplete, hints,
    module navigation, and find-references.
    """

    def __init__(self):
        self.functions  = {}   # name → {params, line, doc}
        self.variables  = {}   # name → {line, value_repr}
        self.imports    = []   # [{path, line}]
        self.calls      = []   # [{name, line, arg_count}]

    def build(self, ast_nodes: list, source_lines: list):
        """Walk the AST and populate all symbol categories."""

        self.functions = {}
        self.variables = {}
        self.imports   = []
        self.calls     = []

        self._walk(ast_nodes, source_lines)

    def _walk(self, nodes, source_lines):
        for node in nodes:
            t = type(node).__name__

            if t == "FunctionNode":
                self.functions[node.name] = {
                    "params": list(node.params),
                    "line":   node.line or 0,
                    "doc":    self._extract_doc(node, source_lines),
                }
                # Walk function body too
                self._walk(node.body, source_lines)

            elif t == "AssignNode":
                self.variables[node.name] = {
                    "line":        node.line or 0,
                    "value_repr":  type(node.value).__name__,
                }
                self._walk_expr(node.value)

            elif t == "ImportNode":
                self.imports.append({
                    "path": node.path,
                    "line": node.line or 0,
                })

            elif t == "CallNode":
                self.calls.append({
                    "name":      node.name,
                    "line":      node.line or 0,
                    "arg_count": len(node.args),
                })
                for arg in node.args:
                    self._walk_expr(arg)

            elif t in ("IfNode",):
                self._walk(node.true_body,  source_lines)
                self._walk(node.false_body, source_lines)

            elif t == "WhileNode":
                self._walk(node.body, source_lines)

            elif t in ("ForNode", "ForEachNode"):
                self._walk(node.body, source_lines)

            elif t == "PrintNode":
                self._walk_expr(node.value)

    def _walk_expr(self, node):
        if node is None: return
        t = type(node).__name__
        if t == "CallNode":
            self.calls.append({
                "name":      node.name,
                "line":      node.line or 0,
                "arg_count": len(node.args),
            })
            for arg in node.args:
                self._walk_expr(arg)
        elif t in ("BinaryOperationNode", "CompareNode", "LogicalOperationNode"):
            self._walk_expr(node.left)
            self._walk_expr(node.right)
        elif t == "UnaryOperationNode":
            self._walk_expr(node.operand)

    def _extract_doc(self, func_node, source_lines) -> str:
        """Look for a # comment on the line before the function definition."""
        ln = (func_node.line or 1) - 2   # 0-based, one above
        if 0 <= ln < len(source_lines):
            line = source_lines[ln].strip()
            if line.startswith("#"):
                return line[1:].strip()
        return ""

    def signature(self, name: str) -> str:
        """Return a human-readable signature string for a function."""
        if name in self.functions:
            info   = self.functions[name]
            params = ", ".join(info["params"])
            return f"{name}({params})"
        if name in BUILTINS:
            return BUILTINS[name][0]
        return f"{name}(…)"

    def hint(self, name: str) -> str:
        """Return the one-line description/doc for a function."""
        if name in self.functions:
            return self.functions[name].get("doc", "")
        if name in BUILTINS:
            return BUILTINS[name][1]
        return ""

    def all_completions(self) -> list:
        """All identifiers the autocomplete should offer."""
        names = set(KEYWORDS)
        names |= set(BUILTINS.keys())
        names |= set(self.functions.keys())
        names |= set(self.variables.keys())
        return sorted(names)

    def find_references(self, name: str, source: str) -> list:
        """
        Return list of (line_num_1based, line_text) for every line in source
        that contains the identifier `name` as a whole word.
        """
        results = []
        pattern = re.compile(rf'\b{re.escape(name)}\b')
        for i, line in enumerate(source.splitlines(), 1):
            if pattern.search(line):
                results.append((i, line.rstrip()))
        return results

    def definition_line(self, name: str) -> int:
        """Return 1-based line number of the definition, or -1."""
        if name in self.functions:
            return self.functions[name]["line"]
        if name in self.variables:
            return self.variables[name]["line"]
        return -1


# ===========================================================================
# CODE FORMATTER
# ===========================================================================

class CodeFormatter:
    """
    Formats MyLang source code:
      - Normalises indentation (4 spaces per level)
      - Ensures blank lines between top-level function definitions
      - Cleans up spacing around operators in assignment expressions
      - Removes trailing whitespace
      - Normalises comment style (# with one space)
    """

    INDENT_IN  = {"function", "if", "else", "while", "for", "foreach"}
    INDENT_OUT = {"end", "else"}

    def format(self, source: str) -> str:
        lines  = source.splitlines()
        result = []
        depth  = 0
        prev_was_function_end = False

        for raw_line in lines:
            stripped = raw_line.strip()

            if not stripped:
                result.append("")
                prev_was_function_end = False
                continue

            # Determine dedent before writing
            first_word = stripped.split()[0] if stripped.split() else ""

            if first_word in self.INDENT_OUT:
                depth = max(0, depth - 1)

            # Blank line before top-level function
            if first_word == "function" and depth == 0 and result and result[-1] != "":
                result.append("")

            # Format the line content
            formatted = self._format_line(stripped)

            result.append("    " * depth + formatted)

            # Determine indent for next line
            if first_word in self.INDENT_IN:
                depth += 1
            if first_word == "else":
                depth += 1

            prev_was_function_end = (first_word == "end" and depth == 0)

        # Remove trailing blank lines, keep one
        while result and result[-1] == "":
            result.pop()
        result.append("")

        return "\n".join(result)

    def _format_line(self, line: str) -> str:
        # Normalise comment spacing: # followed by one space
        if line.startswith("#"):
            content = line[1:].strip()
            return f"# {content}" if content else "#"

        # Clean spacing around = in assignments (not ==)
        # Only do this for simple x = expr lines, not inside strings
        if "=" in line and not line.startswith("if") and not line.startswith("while"):
            line = re.sub(r'\s*(?<!=)=(?!=)\s*', ' = ', line, count=1)

        # Clean up multiple spaces (but not inside strings)
        parts = re.split(r'(".*?")', line)
        cleaned = []
        for i, part in enumerate(parts):
            if i % 2 == 0:   # outside strings
                part = re.sub(r' {2,}', ' ', part)
            cleaned.append(part)
        return "".join(cleaned).strip()


# ===========================================================================
# THEMES
# ===========================================================================

def _make_theme(c):
    return f"""
    QMainWindow, QWidget {{
        background: {c['bg']}; color: {c['fg']};
        font-family: "Segoe UI", Arial, sans-serif; font-size: 13px;
    }}
    QMenuBar {{
        background: {c['menubar_bg']}; color: {c['menubar_fg']};
        padding: 2px 0; border-bottom: 1px solid {c['border']};
    }}
    QMenuBar::item {{ padding: 4px 12px; background: transparent; }}
    QMenuBar::item:selected {{ background: {c['accent']}; color: {c['accent_fg']}; border-radius: 4px; }}
    QMenu {{
        background: {c['menu_bg']}; color: {c['fg']};
        border: 1px solid {c['border']}; padding: 4px;
    }}
    QMenu::item {{ padding: 6px 24px 6px 12px; border-radius: 3px; }}
    QMenu::item:selected {{ background: {c['accent']}; color: {c['accent_fg']}; }}
    QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 8px; }}
    QToolBar {{
        background: {c['toolbar_bg']}; border-bottom: 1px solid {c['border']};
        padding: 4px 6px; spacing: 4px;
    }}
    QToolBar QToolButton {{
        background: {c['btn_bg']}; color: {c['btn_fg']};
        border: 1px solid {c['btn_border']}; border-radius: 5px;
        padding: 5px 14px; font-size: 13px;
    }}
    QToolBar QToolButton:hover {{ background: {c['btn_hover']}; border-color: {c['accent']}; }}
    QToolBar QToolButton:pressed {{ background: {c['accent']}; color: {c['accent_fg']}; }}
    QToolBar QToolButton:disabled {{ background: {c['btn_disabled']}; color: {c['fg_dim']}; border-color: {c['border']}; }}
    QToolBar QToolButton#dbg_step  {{ background: {c['dbg_btn']}; color: {c['dbg_btn_fg']}; border-color: {c['dbg_border']}; }}
    QToolBar QToolButton#dbg_step:hover  {{ background: {c['dbg_btn_hover']}; }}
    QToolBar QToolButton#dbg_cont  {{ background: {c['dbg_btn']}; color: {c['dbg_btn_fg']}; border-color: {c['dbg_border']}; }}
    QToolBar QToolButton#dbg_cont:hover  {{ background: {c['dbg_btn_hover']}; }}
    QToolBar QToolButton#dbg_clear {{ background: {c['btn_bg']}; }}
    QToolBar::separator {{ width: 1px; background: {c['border']}; margin: 4px 6px; }}
    QComboBox {{
        background: {c['btn_bg']}; color: {c['btn_fg']};
        border: 1px solid {c['btn_border']}; border-radius: 5px;
        padding: 4px 10px; min-width: 90px;
    }}
    QComboBox:hover {{ border-color: {c['accent']}; }}
    QComboBox QAbstractItemView {{
        background: {c['menu_bg']}; color: {c['fg']};
        selection-background-color: {c['accent']}; selection-color: {c['accent_fg']};
        border: 1px solid {c['border']};
    }}
    QComboBox::drop-down {{ border: none; width: 20px; }}
    QSpinBox {{
        background: {c['btn_bg']}; color: {c['btn_fg']};
        border: 1px solid {c['btn_border']}; border-radius: 4px; padding: 4px 8px;
    }}
    QSpinBox:focus {{ border-color: {c['accent']}; }}
    QLineEdit {{
        background: {c['btn_bg']}; color: {c['btn_fg']};
        border: 1px solid {c['btn_border']}; border-radius: 4px; padding: 4px 8px;
    }}
    QLineEdit:focus {{ border-color: {c['accent']}; }}
    QDockWidget {{ color: {c['fg']}; font-weight: bold; }}
    QDockWidget::title {{
        background: {c['panel_header']}; color: {c['panel_header_fg']};
        padding: 6px 10px; border-bottom: 1px solid {c['border']};
        text-align: left; font-size: 11px; font-weight: bold;
        letter-spacing: 1px; text-transform: uppercase;
    }}
    QTabWidget::pane {{ border: 1px solid {c['border']}; background: {c['bg']}; }}
    QTabBar::tab {{
        background: {c['btn_bg']}; color: {c['fg']};
        border: 1px solid {c['border']}; padding: 6px 14px;
        border-bottom: none; border-top-left-radius: 4px; border-top-right-radius: 4px;
    }}
    QTabBar::tab:selected {{ background: {c['accent']}; color: {c['accent_fg']}; }}
    QTabBar::tab:hover {{ background: {c['btn_hover']}; }}
    QSplitter::handle {{ background: {c['border']}; }}
    QSplitter::handle:horizontal {{ width: 2px; }}
    QSplitter::handle:vertical   {{ height: 2px; }}
    QPlainTextEdit {{
        background: {c['editor_bg']}; color: {c['editor_fg']}; border: none;
        selection-background-color: {c['selection']}; selection-color: {c['selection_fg']};
        font-family: "Courier New", Consolas, monospace; font-size: 14px; padding: 4px 0;
    }}
    QTextEdit {{
        background: {c['console_bg']}; color: {c['console_fg']}; border: none;
        font-family: "Courier New", Consolas, monospace; font-size: 13px; padding: 6px;
    }}
    QTreeWidget {{
        background: {c['tree_bg']}; color: {c['fg']}; border: none; font-size: 12px;
    }}
    QTreeWidget::item {{ padding: 2px 4px; border-radius: 3px; }}
    QTreeWidget::item:selected {{ background: {c['accent']}; color: {c['accent_fg']}; }}
    QTreeWidget::item:hover {{ background: {c['btn_hover']}; }}
    QListWidget {{
        background: {c['menu_bg']}; color: {c['fg']};
        border: 1px solid {c['border']}; font-size: 13px;
        font-family: "Courier New", Consolas, monospace;
    }}
    QListWidget::item {{ padding: 3px 8px; }}
    QListWidget::item:selected {{ background: {c['accent']}; color: {c['accent_fg']}; }}
    QListWidget::item:hover {{ background: {c['btn_hover']}; }}
    QHeaderView::section {{
        background: {c['panel_header']}; color: {c['panel_header_fg']};
        padding: 4px 8px; border: none; border-bottom: 1px solid {c['border']};
        font-size: 11px; font-weight: bold; letter-spacing: 1px; text-transform: uppercase;
    }}
    QScrollBar:vertical {{ background: {c['scrollbar_track']}; width: 10px; border: none; }}
    QScrollBar::handle:vertical {{ background: {c['scrollbar_thumb']}; border-radius: 5px; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: {c['accent']}; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QScrollBar:horizontal {{ background: {c['scrollbar_track']}; height: 10px; border: none; }}
    QScrollBar::handle:horizontal {{ background: {c['scrollbar_thumb']}; border-radius: 5px; min-width: 24px; }}
    QScrollBar::handle:horizontal:hover {{ background: {c['accent']}; }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
    QStatusBar {{
        background: {c['statusbar_bg']}; color: {c['statusbar_fg']};
        font-size: 12px; padding: 0 8px; border-top: 1px solid {c['border']};
    }}
    QStatusBar QLabel {{ color: {c['statusbar_fg']}; padding: 0 8px; }}
    QDialog {{ background: {c['bg']}; color: {c['fg']}; }}
    QDialogButtonBox QPushButton {{
        background: {c['btn_bg']}; color: {c['btn_fg']};
        border: 1px solid {c['btn_border']}; border-radius: 5px; padding: 5px 18px;
    }}
    QDialogButtonBox QPushButton:hover {{ background: {c['btn_hover']}; }}
    QDialogButtonBox QPushButton:pressed {{ background: {c['accent']}; color: {c['accent_fg']}; }}
    """

_DARK = dict(
    bg="#1c1c2e", fg="#cdd6f4", fg_dim="#585b70",
    accent="#89b4fa", accent_fg="#1e1e2e", border="#313244",
    menubar_bg="#181825", menubar_fg="#cdd6f4", menu_bg="#24243e",
    toolbar_bg="#181825", panel_header="#11111b", panel_header_fg="#89b4fa",
    btn_bg="#2a2a45", btn_fg="#cdd6f4", btn_border="#45475a",
    btn_hover="#313255", btn_disabled="#1e1e2e",
    editor_bg="#1e1e2e", editor_fg="#cdd6f4",
    selection="#264f78", selection_fg="#ffffff",
    console_bg="#11111b", console_fg="#cdd6f4", tree_bg="#1a1a2e",
    scrollbar_track="#181825", scrollbar_thumb="#45475a",
    statusbar_bg="#11111b", statusbar_fg="#89b4fa",
    dbg_btn="#2d1b4e", dbg_btn_fg="#c9b0f0",
    dbg_btn_hover="#3d2b5e", dbg_border="#7c5cbf",
    bp_color="#f38ba8", exec_color="#a6e3a1",
)
_LIGHT = dict(
    bg="#f8f8f2", fg="#282a36", fg_dim="#aaaaaa",
    accent="#6272a4", accent_fg="#ffffff", border="#d0d0e0",
    menubar_bg="#f0f0fa", menubar_fg="#282a36", menu_bg="#ffffff",
    toolbar_bg="#f0f0fa", panel_header="#e8e8f5", panel_header_fg="#6272a4",
    btn_bg="#e8e8f5", btn_fg="#282a36", btn_border="#c8c8dc",
    btn_hover="#dcdcf5", btn_disabled="#f0f0f5",
    editor_bg="#ffffff", editor_fg="#282a36",
    selection="#b5d5ff", selection_fg="#000000",
    console_bg="#f5f5ff", console_fg="#282a36", tree_bg="#f8f8fe",
    scrollbar_track="#f0f0f0", scrollbar_thumb="#c0c0d0",
    statusbar_bg="#6272a4", statusbar_fg="#ffffff",
    dbg_btn="#ede7f6", dbg_btn_fg="#4527a0",
    dbg_btn_hover="#d1c4e9", dbg_border="#9575cd",
    bp_color="#c0392b", exec_color="#27ae60",
)
_QBASIC = dict(
    bg="#0000aa", fg="#ffff55", fg_dim="#aaaaaa",
    accent="#ffff55", accent_fg="#0000aa", border="#5555ff",
    menubar_bg="#0000cc", menubar_fg="#ffffff", menu_bg="#0000aa",
    toolbar_bg="#0000cc", panel_header="#000088", panel_header_fg="#55ffff",
    btn_bg="#0000cc", btn_fg="#ffff55", btn_border="#5555ff",
    btn_hover="#0000ee", btn_disabled="#000088",
    editor_bg="#0000aa", editor_fg="#ffff55",
    selection="#aaaaaa", selection_fg="#000000",
    console_bg="#000055", console_fg="#ffffff", tree_bg="#000088",
    scrollbar_track="#000088", scrollbar_thumb="#5555ff",
    statusbar_bg="#aaaaaa", statusbar_fg="#000000",
    dbg_btn="#000066", dbg_btn_fg="#55ffff",
    dbg_btn_hover="#0000aa", dbg_border="#55ffff",
    bp_color="#ff5555", exec_color="#55ff55",
)

THEMES      = {"Dark": _make_theme(_DARK), "Light": _make_theme(_LIGHT), "QBasic": _make_theme(_QBASIC)}
THEME_COLORS= {"Dark": _DARK,             "Light": _LIGHT,              "QBasic": _QBASIC}
DEFAULT_THEME = "Dark"


# ===========================================================================
# SYNTAX HIGHLIGHTER
# ===========================================================================

class MyLangHighlighter(QSyntaxHighlighter):

    def __init__(self, document, theme_name=DEFAULT_THEME):
        super().__init__(document)
        self.rules       = []
        self.error_lines = set()
        self.apply_theme(theme_name)

    def apply_theme(self, theme_name):
        self.theme_name = theme_name

        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:   f.setFontWeight(QFont.Bold)
            if italic: f.setFontItalic(True)
            return f

        if theme_name == "QBasic":
            kw, st, nu, cm, fn, op = "#55ffff","#ff5555","#55ff55","#aaaaaa","#ffffff","#ffaa00"
        elif theme_name == "Light":
            kw, st, nu, cm, fn, op = "#0000cc","#cc3300","#008800","#888888","#7700bb","#aa6600"
        else:
            kw, st, nu, cm, fn, op = "#89b4fa","#f38ba8","#a6e3a1","#6c7086","#cba6f7","#fab387"

        self.rules = []
        for w in KEYWORDS:
            self.rules.append((QRegularExpression(rf"\b{w}\b"), fmt(kw, bold=True)))
        for w in BUILTINS:
            self.rules.append((QRegularExpression(rf"\b{w}\b"), fmt(fn)))
        self.rules.append((QRegularExpression(r"[=<>!+\-*/%&|(){}\[\]]"), fmt(op)))
        self.rules.append((QRegularExpression(r"\b-?\d+(\.\d+)?\b"),      fmt(nu)))
        self.rules.append((QRegularExpression(r'"[^"]*"'),                 fmt(st)))
        self.rules.append((QRegularExpression(r'#[^\n]*'), fmt(cm, italic=True)))

        self.error_fmt = QTextCharFormat()
        self.error_fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        self.error_fmt.setUnderlineColor(QColor("#ff5555"))
        self.rehighlight()

    def set_error_lines(self, lines: set):
        self.error_lines = lines
        self.rehighlight()

    def clear_errors(self):
        self.error_lines = set()
        self.rehighlight()

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            it = pattern.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)
        block_num = self.currentBlock().blockNumber()
        if block_num in self.error_lines:
            stripped = text.rstrip()
            start    = len(text) - len(text.lstrip())
            self.setFormat(start, max(1, len(stripped) - start), self.error_fmt)


# ===========================================================================
# AUTOCOMPLETE POPUP
# ===========================================================================

class AutoCompletePopup(QListWidget):
    """
    Frameless floating list shown below the cursor.
    Populated dynamically from the current SymbolTable.
    """

    item_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setMaximumHeight(200)
        self.setMinimumWidth(220)
        self.itemClicked.connect(self._on_item_clicked)

    def populate(self, prefix: str, completions: list):
        """Show completions that start with prefix (case-insensitive)."""
        self.clear()
        low = prefix.lower()
        matched = [c for c in completions if c.lower().startswith(low) and c != prefix]
        for name in matched[:30]:   # cap at 30 items
            item = QListWidgetItem(name)
            if name in KEYWORDS:
                item.setForeground(QColor("#89b4fa"))
            elif name in BUILTINS:
                item.setForeground(QColor("#cba6f7"))
            self.addItem(item)
        return len(matched) > 0

    def current_text(self) -> str:
        item = self.currentItem()
        return item.text() if item else ""

    def _on_item_clicked(self, item):
        self.item_selected.emit(item.text())
        self.hide()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            item = self.currentItem()
            if item:
                self.item_selected.emit(item.text())
                self.hide()
                return
        elif event.key() == Qt.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)


# ===========================================================================
# FUNCTION HINT BAR
# ===========================================================================

class FunctionHintBar(QLabel):
    """
    A single-line bar shown below the main toolbar that displays
    the current function signature when the cursor is inside a call.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setFixedHeight(26)
        self.setContentsMargins(10, 0, 10, 0)
        self.hide()

    def show_hint(self, signature: str, doc: str, active_arg: int, param_names: list):
        """
        Build a rich-text hint like:   greet( name, age )
        where the active argument is bold.
        """
        if not param_names:
            self.setText(f"  {signature}   {doc}")
            self.show()
            return

        parts = []
        for i, p in enumerate(param_names):
            if i == active_arg:
                parts.append(f"<b><u>{p}</u></b>")
            else:
                parts.append(p)

        sig_html = f"  <b>{signature.split('(')[0]}</b>( {', '.join(parts)} )"
        doc_html = f"  <span style='color:#585b70;font-style:italic;'>  {doc}</span>" if doc else ""
        self.setText(sig_html + doc_html)
        self.show()

    def clear_hint(self):
        self.setText("")
        self.hide()


# ===========================================================================
# FIND REFERENCES DIALOG
# ===========================================================================

class FindReferencesDialog(QDialog):

    def __init__(self, parent, name: str, results: list):
        super().__init__(parent)
        self.setWindowTitle(f"References — {name}")
        self.setMinimumSize(600, 380)
        self._parent_ide = parent

        layout = QVBoxLayout(self)

        header = QLabel(f"  {len(results)} reference(s) to  <b>{name}</b>")
        layout.addWidget(header)

        self.list = QListWidget()
        self.list.setFont(QFont("Courier New", 12))
        for line_num, line_text in results:
            item = QListWidgetItem(f"  Ln {line_num:4d}   {line_text.strip()}")
            item.setData(Qt.UserRole, line_num)
            self.list.addItem(item)

        self.list.itemDoubleClicked.connect(self._jump)
        layout.addWidget(self.list)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _jump(self, item):
        line_num = item.data(Qt.UserRole)
        self._parent_ide.editor.jump_to_line(line_num)
        self.accept()


# ===========================================================================
# LINE NUMBER GUTTER
# ===========================================================================

class LineNumberGutter(QWidget):

    breakpoint_clicked = Signal(int)

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.gutter_width(), 0)

    def paintEvent(self, event):
        self.editor.paint_gutter(event)

    def mousePressEvent(self, event):
        block     = self.editor.firstVisibleBlock()
        block_num = block.blockNumber()
        top       = int(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())
        bottom    = top + int(self.editor.blockBoundingRect(block).height())
        while block.isValid():
            if block.isVisible() and top <= event.position().y() <= bottom:
                self.breakpoint_clicked.emit(block_num + 1)
                return
            block     = block.next()
            top       = bottom
            bottom    = top + int(self.editor.blockBoundingRect(block).height())
            block_num += 1


# ===========================================================================
# CODE EDITOR  (Phase 4: autocomplete trigger, hint detection)
# ===========================================================================

class CodeEditor(QPlainTextEdit):

    autocomplete_requested = Signal(str, QPoint)
    hint_requested         = Signal(str, int)
    hint_cleared           = Signal()

    def __init__(self, theme_name=DEFAULT_THEME):
        super().__init__()
        self.gutter      = LineNumberGutter(self)
        self.theme_name  = theme_name
        self.breakpoints = set()
        self.exec_line   = -1

        self.setFont(QFont("Courier New", 13))
        self.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.setTabStopDistance(QFontMetrics(self.font()).horizontalAdvance(" ") * 4)

        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self.gutter.breakpoint_clicked.connect(self.toggle_breakpoint)

        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        self._update_gutter_width()
        self._highlight_current_line()

    def apply_theme(self, name):
        self.theme_name = name

    def gutter_width(self):
        digits = max(3, len(str(max(1, self.blockCount()))))
        return 22 + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_gutter_width(self):
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _update_gutter(self, rect, dy):
        if dy: self.gutter.scroll(0, dy)
        else:  self.gutter.update(0, rect.y(), self.gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.gutter.setGeometry(QRect(cr.left(), cr.top(), self.gutter_width(), cr.height()))

    def paint_gutter(self, event):
        c       = THEME_COLORS[self.theme_name]
        painter = QPainter(self.gutter)
        painter.fillRect(event.rect(), QColor(c["panel_header"]))
        num_font   = QFont("Courier New", 11)
        painter.setFont(num_font)
        block      = self.firstVisibleBlock()
        block_num  = block.blockNumber()
        top        = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom     = top + int(self.blockBoundingRect(block).height())
        current_ln = self.textCursor().blockNumber()
        line_h     = self.fontMetrics().height()

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                ln = block_num + 1
                if ln == self.exec_line:
                    painter.setPen(QColor(c["exec_color"]))
                    painter.setFont(QFont("Courier New", 11, QFont.Bold))
                    painter.drawText(2, top, 14, line_h, Qt.AlignLeft, "▶")
                    painter.setFont(num_font)
                if ln in self.breakpoints:
                    painter.setPen(Qt.NoPen)
                    painter.setBrush(QBrush(QColor(c["bp_color"])))
                    cy = top + line_h // 2
                    painter.drawEllipse(QPoint(16, cy), min(5, line_h // 2 - 1), min(5, line_h // 2 - 1))
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QColor(c["accent"] if block_num == current_ln else c["fg_dim"]))
                painter.drawText(0, top, self.gutter.width() - 4, line_h, Qt.AlignRight, str(ln))
            block     = block.next()
            top       = bottom
            bottom    = top + int(self.blockBoundingRect(block).height())
            block_num += 1

    def _highlight_current_line(self):
        c = THEME_COLORS[self.theme_name]
        extra = []
        if not self.isReadOnly():
            sel = QTextEdit.ExtraSelection()
            sel.format.setBackground(QColor(c["btn_hover"]))
            sel.format.setProperty(QTextFormat.FullWidthSelection, True)
            sel.cursor = self.textCursor()
            sel.cursor.clearSelection()
            extra.append(sel)
        self.setExtraSelections(extra)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab:
            self.insertPlainText("    ")
            return

        super().keyPressEvent(event)

        # ── Autocomplete trigger ──────────────────────────────────────────
        if event.key() not in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter,
                                Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right,
                                Qt.Key_Backspace, Qt.Key_Delete):
            prefix = self._word_before_cursor()
            if len(prefix) >= 2:
                cursor_rect = self.cursorRect()
                global_pos  = self.viewport().mapToGlobal(
                    cursor_rect.bottomLeft()
                )
                self.autocomplete_requested.emit(prefix, global_pos)

        # ── Function hint trigger ─────────────────────────────────────────
        self._check_function_hint()

    def _word_before_cursor(self) -> str:
        cursor = self.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        return cursor.selectedText()

    def word_at_cursor(self) -> str:
        cursor = self.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        return cursor.selectedText()

    def _check_function_hint(self):
        """
        Detect if cursor is inside funcname(...) and emit hint_requested.
        Scans backwards from the cursor to find an unclosed '('.
        """
        cursor   = self.textCursor()
        line_text= cursor.block().text()
        col      = cursor.columnNumber()
        before   = line_text[:col]

        depth = 0
        for i in range(len(before) - 1, -1, -1):
            ch = before[i]
            if ch == ')': depth += 1
            elif ch == '(':
                if depth == 0:
                    # Find the function name before this '('
                    name_match = re.search(r'\b(\w+)\s*$', before[:i])
                    if name_match:
                        func_name  = name_match.group(1)
                        arg_index  = before[i+1:].count(',')
                        self.hint_requested.emit(func_name, arg_index)
                        return
                    break
                else:
                    depth -= 1

        self.hint_cleared.emit()

    def jump_to_line(self, line_num: int):
        block = self.document().findBlockByLineNumber(line_num - 1)
        if block.isValid():
            cursor = QTextCursor(block)
            self.setTextCursor(cursor)
            self.centerCursor()
            self.setFocus()

    def toggle_breakpoint(self, line: int):
        if line in self.breakpoints: self.breakpoints.discard(line)
        else:                        self.breakpoints.add(line)
        self.gutter.update()

    def clear_all_breakpoints(self):
        self.breakpoints.clear()
        self.exec_line = -1
        self.gutter.update()

    def set_exec_line(self, line: int):
        self.exec_line = line
        self.gutter.update()
        if line > 0: self.jump_to_line(line)

    def clear_exec_line(self):
        self.exec_line = -1
        self.gutter.update()

    # ── Context menu (right-click) ────────────────────────────────────────

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        word = self.word_at_cursor()

        if word:
            menu.addAction(
                QAction(f'Find References: "{word}"', self,
                        triggered=lambda: self.hint_requested.emit(f"__refs__{word}", 0))
            )
            menu.addAction(
                QAction(f'Go to Definition: "{word}"', self,
                        triggered=lambda: self.hint_requested.emit(f"__def__{word}", 0))
            )
            menu.addSeparator()

        menu.addAction(QAction("Cut",   self, triggered=self.cut))
        menu.addAction(QAction("Copy",  self, triggered=self.copy))
        menu.addAction(QAction("Paste", self, triggered=self.paste))
        menu.addSeparator()
        menu.addAction(QAction("Select All", self, triggered=self.selectAll))
        menu.exec(self.viewport().mapToGlobal(pos))


# ===========================================================================
# ANALYSIS SIGNALS + WORKER  (now also emits SymbolTable)
# ===========================================================================

class AnalysisSignals(QObject):
    result = Signal(list, object, str, int, object)
    # (tokens, ast_nodes, err_msg, err_line, symbol_table)


class AnalysisWorker(QThread):

    def __init__(self, code: str):
        super().__init__()
        self.code    = code
        self.signals = AnalysisSignals()

    def run(self):
        tokens = []; ast_nodes = []; err_msg = ""; err_line = -1
        sym    = SymbolTable()

        try:
            tokens = Lexer(self.code).tokenize()
        except Exception as e:
            err_msg  = str(e)
            err_line = self._extract_line(err_msg)
            self.signals.result.emit(tokens, ast_nodes, err_msg, err_line, sym)
            return

        try:
            ast_nodes = Parser(tokens).parse()
            src_lines = self.code.splitlines()
            sym.build(ast_nodes, src_lines)
        except MyLangSyntaxError as e:
            err_msg  = str(e)
            err_line = e.line if hasattr(e, "line") and e.line else self._extract_line(err_msg)
        except Exception as e:
            err_msg  = str(e)
            err_line = self._extract_line(err_msg)

        self.signals.result.emit(tokens, ast_nodes, err_msg, err_line, sym)

    @staticmethod
    def _extract_line(msg: str) -> int:
        m = re.search(r"[Ll]ine\s+(\d+)", msg)
        return int(m.group(1)) if m else -1


# ===========================================================================
# RUN + DEBUG WORKERS  (unchanged from Phase 3)
# ===========================================================================

class RunSignals(QObject):
    output   = Signal(str, str)
    finished = Signal()

class RunWorker(QThread):
    def __init__(self, code, script_dir, pkg_dir=""):
        super().__init__()
        self.code = code; self.script_dir = script_dir
        self.pkg_dir = pkg_dir
        self.signals = RunSignals()

    def run(self):
        class _R(io.TextIOBase):
            def __init__(self, s, t): self._s, self._t = s, t
            def write(self, x):
                if x: self._s.emit(x, self._t)
                return len(x)
            def flush(self): pass

        old_o, old_e = sys.stdout, sys.stderr
        sys.stdout = _R(self.signals.output, "out")
        sys.stderr = _R(self.signals.output, "err")
        try:
            search = [self.script_dir]
            if self.pkg_dir and self.pkg_dir not in search:
                search.append(self.pkg_dir)
            ASTInterpreter(
                module_search_paths=search,
                file_root=self.script_dir,
            ).run(Parser(Lexer(self.code).tokenize()).parse())
        except MyLangSyntaxError as e:
            self.signals.output.emit(f"\nSYNTAX ERROR:\n{e}\n", "err")
        except MyLangRuntimeError as e:
            self.signals.output.emit(f"\nRUNTIME ERROR:\n{e}\n", "err")
        except Exception:
            self.signals.output.emit(f"\nINTERNAL ERROR:\n{traceback.format_exc()}\n", "err")
        finally:
            sys.stdout = old_o; sys.stderr = old_e
            self.signals.finished.emit()


class DebugSignals(QObject):
    paused    = Signal(int, dict, list)
    resumed   = Signal()
    exception = Signal(str, str, int)

class DebugController:
    def __init__(self, breakpoints, signals):
        self.breakpoints = set(breakpoints)
        self.signals     = signals
        self._event      = threading.Event()
        self._step_mode  = False
        self._stop       = False

    def on_line(self, line, variables, call_stack):
        if self._stop:
            raise KeyboardInterrupt("Debug stop")
        if self._step_mode or line in self.breakpoints:
            var_snap = {k: repr(v) for k, v in variables.items()}
            self._event.clear()
            self.signals.paused.emit(line, var_snap, list(call_stack))
            self._event.wait()
        if self._stop:
            raise KeyboardInterrupt("Debug stop")

    def resume(self): self._step_mode = False; self._event.set()
    def step(self):   self._step_mode = True;  self._event.set()
    def stop(self):   self._stop = True;        self._event.set()

class DebugWorker(QThread):
    def __init__(self, code, script_dir, controller, pkg_dir=""):
        super().__init__()
        self.code = code; self.script_dir = script_dir
        self.controller = controller; self.signals = RunSignals()
        self.pkg_dir = pkg_dir

    def run(self):
        class _R(io.TextIOBase):
            def __init__(self, s, t): self._s, self._t = s, t
            def write(self, x):
                if x: self._s.emit(x, self._t)
                return len(x)
            def flush(self): pass

        old_o, old_e = sys.stdout, sys.stderr
        sys.stdout = _R(self.signals.output, "out")
        sys.stderr = _R(self.signals.output, "err")
        try:
            search = [self.script_dir]
            if self.pkg_dir and self.pkg_dir not in search:
                search.append(self.pkg_dir)
            interp = ASTInterpreter(
                module_search_paths=search,
                file_root=self.script_dir,
            )
            interp.set_debug_controller(self.controller)
            interp.run(Parser(Lexer(self.code).tokenize()).parse())
        except KeyboardInterrupt:
            self.signals.output.emit("\n─── Debug session stopped ───\n", "out")
        except MyLangSyntaxError as e:
            self.controller.signals.exception.emit("SyntaxError", str(e),
                                                    e.line if hasattr(e, "line") and e.line else -1)
        except MyLangRuntimeError as e:
            self.controller.signals.exception.emit("RuntimeError", str(e),
                                                    e.line if hasattr(e, "line") and e.line else -1)
        except Exception:
            self.controller.signals.exception.emit("InternalError", traceback.format_exc(), -1)
        finally:
            sys.stdout = old_o; sys.stderr = old_e
            self.signals.finished.emit()


# ===========================================================================
# PHASE 5 — ECOSYSTEM CONSTANTS
# ===========================================================================

MYLANG_HOME   = pathlib.Path.home() / ".mylang"
PKG_DIR       = MYLANG_HOME / "packages"
PLUGIN_DIR    = MYLANG_HOME / "plugins"
TEMPLATE_DIR  = MYLANG_HOME / "templates"

def _ensure_dirs():
    for d in (MYLANG_HOME, PKG_DIR, PLUGIN_DIR, TEMPLATE_DIR):
        d.mkdir(parents=True, exist_ok=True)

_ensure_dirs()

# ===========================================================================
# BUILT-IN PROJECT TEMPLATES
# ===========================================================================

BUILTIN_TEMPLATES = {
    "Hello World": {
        "description": "The simplest possible MyLang program.",
        "files": {
            "main.my": (
                '# Hello World\n'
                'print "Hello, World!"\n'
            ),
        },
    },
    "Calculator": {
        "description": "A simple calculator with functions.",
        "files": {
            "calculator.my": (
                '# Simple Calculator\n\n'
                'function add a b\n'
                '    return a + b\n'
                'end\n\n'
                'function subtract a b\n'
                '    return a - b\n'
                'end\n\n'
                'function multiply a b\n'
                '    return a * b\n'
                'end\n\n'
                'print add(10, 5)\n'
                'print subtract(10, 5)\n'
                'print multiply(10, 5)\n'
            ),
        },
    },
    "File Logger": {
        "description": "Read, write and append to log files.",
        "files": {
            "logger.my": (
                '# File Logger\n\n'
                'function log_message msg\n'
                '    append_file("app.log", msg + "\\n")\n'
                'end\n\n'
                'log_message("Application started")\n'
                'log_message("Processing data")\n'
                'log_message("Done")\n\n'
                'contents = read_file("app.log")\n'
                'print contents\n'
            ),
        },
    },
    "Data Processor": {
        "description": "List and dictionary processing example.",
        "files": {
            "processor.my": (
                '# Data Processor\n\n'
                'scores = [85, 92, 78, 95, 88, 76, 91]\n\n'
                'function average nums\n'
                '    total = 0\n'
                '    foreach n in nums\n'
                '        total = total + n\n'
                '    end\n'
                '    return total\n'
                'end\n\n'
                'total = average(scores)\n'
                'print total\n'
                'print length(scores)\n'
                'print first(sort(scores))\n'
                'print last(sort(scores))\n'
            ),
        },
    },
    "Module Library": {
        "description": "A two-file project — a library and a main script.",
        "files": {
            "main.my": (
                '# Main script\n'
                'import utils\n\n'
                'result = double(21)\n'
                'print result\n\n'
                'greeting = make_greeting("World")\n'
                'print greeting\n'
            ),
            "utils.my": (
                '# Utility functions\n\n'
                'function double n\n'
                '    return n + n\n'
                'end\n\n'
                'function make_greeting name\n'
                '    return "Hello, " + name\n'
                'end\n'
            ),
        },
    },
    "Interactive Input": {
        "description": "A program that reads user input.",
        "files": {
            "interactive.my": (
                '# Interactive Input\n\n'
                'print "What is your name?"\n'
                'name = input("> ")\n'
                'print "Hello, " + name + "!"\n\n'
                'print "Enter a number:"\n'
                'raw = input("> ")\n'
                'n = to_int(raw)\n'
                'print "Double: " + to_str(n + n)\n'
            ),
        },
    },
}


# ===========================================================================
# PACKAGE MANAGER
# ===========================================================================

class PackageManager:
    """
    Manages MyLang packages stored in ~/.mylang/packages/.
    A package is a directory containing .my files and an optional
    package.json with metadata: name, version, description, author.
    """

    def list_packages(self) -> list:
        packages = []
        try:
            for entry in sorted(PKG_DIR.iterdir()):
                if entry.is_dir():
                    meta = self._read_meta(entry)
                    packages.append({
                        "name":        meta.get("name", entry.name),
                        "version":     meta.get("version", "?"),
                        "description": meta.get("description", ""),
                        "author":      meta.get("author", ""),
                        "path":        str(entry),
                    })
                elif entry.suffix == ".my":
                    packages.append({
                        "name":        entry.stem,
                        "version":     "—",
                        "description": f"Single-file package: {entry.name}",
                        "author":      "—",
                        "path":        str(entry),
                    })
        except OSError:
            pass
        return packages

    def install_from_path(self, src_path: str) -> tuple:
        """
        Install a package from a local path (file or directory).
        Returns (success: bool, message: str).
        """
        src = pathlib.Path(src_path)
        if not src.exists():
            return False, f"Path not found: {src_path}"

        if src.is_file() and src.suffix == ".my":
            dest = PKG_DIR / src.name
            shutil.copy2(src, dest)
            return True, f"Installed {src.name} → {dest}"

        if src.is_dir():
            dest = PKG_DIR / src.name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            return True, f"Installed package '{src.name}' → {dest}"

        return False, "Source must be a .my file or a directory."

    def install_from_url(self, url: str) -> tuple:
        """
        Download and install a package from a URL.
        Supports plain .my files and .zip archives.
        Returns (success: bool, message: str).
        """
        try:
            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = pathlib.Path(tmp)
                fname    = url.split("/")[-1].split("?")[0] or "package"
                dest_tmp = tmp_path / fname

                with urllib.request.urlopen(url, timeout=15) as resp:
                    dest_tmp.write_bytes(resp.read())

                if fname.endswith(".zip"):
                    with zipfile.ZipFile(dest_tmp) as zf:
                        zf.extractall(tmp_path / "extracted")
                    extracted = tmp_path / "extracted"
                    dirs = [d for d in extracted.iterdir() if d.is_dir()]
                    if dirs:
                        return self.install_from_path(str(dirs[0]))
                    return self.install_from_path(str(extracted))

                elif fname.endswith(".my"):
                    final = PKG_DIR / fname
                    shutil.copy2(dest_tmp, final)
                    return True, f"Installed {fname} from URL."

                return False, "URL must point to a .my file or a .zip archive."

        except urllib.error.URLError as e:
            return False, f"Network error: {e}"
        except Exception as e:
            return False, f"Install failed: {e}"

    def uninstall(self, name: str) -> tuple:
        """Remove a package by name. Returns (success, message)."""
        for entry in PKG_DIR.iterdir():
            if entry.name == name or entry.stem == name:
                if entry.is_dir():
                    shutil.rmtree(entry)
                else:
                    entry.unlink()
                return True, f"Removed package '{name}'."
        return False, f"Package '{name}' not found."

    @staticmethod
    def _read_meta(pkg_dir: pathlib.Path) -> dict:
        meta_file = pkg_dir / "package.json"
        if meta_file.exists():
            try:
                return json.loads(meta_file.read_text())
            except Exception:
                pass
        return {}

    @property
    def search_path(self) -> str:
        return str(PKG_DIR)


# ===========================================================================
# PACKAGE MANAGER DIALOG
# ===========================================================================

class PackageManagerDialog(QDialog):

    def __init__(self, parent, pkg_manager: PackageManager):
        super().__init__(parent)
        self.pm = pkg_manager
        self.setWindowTitle("Package Manager")
        self.setMinimumSize(700, 480)

        layout = QVBoxLayout(self)

        # Header
        header = QLabel(
            f"  MyLang Package Manager  —  "
            f"packages stored in  <code>{PKG_DIR}</code>"
        )
        layout.addWidget(header)

        # Installed list
        self.pkg_tree = QTreeWidget()
        self.pkg_tree.setColumnCount(4)
        self.pkg_tree.setHeaderLabels(["Name", "Version", "Author", "Description"])
        self.pkg_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.pkg_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.pkg_tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.pkg_tree.header().setSectionResizeMode(3, QHeaderView.Stretch)
        self.pkg_tree.setAlternatingRowColors(True)
        layout.addWidget(self.pkg_tree)

        # Install from path row
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to .my file or package folder…")
        path_row.addWidget(self.path_input)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        install_path_btn = QPushButton("Install from Path")
        install_path_btn.clicked.connect(self._install_from_path)
        path_row.addWidget(install_path_btn)
        layout.addLayout(path_row)

        # Install from URL row
        url_row = QHBoxLayout()
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com/package.my  or  .zip URL…")
        url_row.addWidget(self.url_input)
        install_url_btn = QPushButton("Install from URL")
        install_url_btn.clicked.connect(self._install_from_url)
        url_row.addWidget(install_url_btn)
        layout.addLayout(url_row)

        # Uninstall + status row
        action_row = QHBoxLayout()
        uninstall_btn = QPushButton("Uninstall Selected")
        uninstall_btn.clicked.connect(self._uninstall)
        action_row.addWidget(uninstall_btn)
        self.status_label = QLabel("")
        action_row.addWidget(self.status_label, 1)
        layout.addLayout(action_row)

        # Close
        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._refresh()

    def _refresh(self):
        self.pkg_tree.clear()
        for pkg in self.pm.list_packages():
            item = QTreeWidgetItem([
                pkg["name"], pkg["version"],
                pkg["author"], pkg["description"],
            ])
            item.setData(0, Qt.UserRole, pkg["name"])
            self.pkg_tree.addTopLevelItem(item)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Package File", str(PKG_DIR),
            "MyLang Files (*.my);;All Files (*.*)"
        )
        if path:
            self.path_input.setText(path)

    def _install_from_path(self):
        path = self.path_input.text().strip()
        if not path:
            return
        ok, msg = self.pm.install_from_path(path)
        self.status_label.setText(msg)
        if ok:
            self._refresh()

    def _install_from_url(self):
        url = self.url_input.text().strip()
        if not url:
            return
        self.status_label.setText("Downloading…")
        QApplication.processEvents()
        ok, msg = self.pm.install_from_url(url)
        self.status_label.setText(msg)
        if ok:
            self._refresh()

    def _uninstall(self):
        item = self.pkg_tree.currentItem()
        if not item:
            return
        name = item.data(0, Qt.UserRole)
        ok, msg = self.pm.uninstall(name)
        self.status_label.setText(msg)
        if ok:
            self._refresh()


# ===========================================================================
# PLUGIN SYSTEM
# ===========================================================================

class PluginManager:
    """
    Loads Python plugins from ~/.mylang/plugins/.
    Each plugin is a .py file that must expose:
        def register(ide):  ...
    The register() function receives the MyLangIDE instance and can:
      - Add menu actions via ide.menuBar()
      - Add toolbar buttons via ide._tb_btn()
      - Connect to editor signals
      - Read/write editor content via ide.editor
    """

    def __init__(self):
        self._loaded   = {}   # name → module
        self._disabled = set()
        self._errors   = {}   # name → error string
        self._load_state()

    def _state_file(self):
        return MYLANG_HOME / "plugin_state.json"

    def _load_state(self):
        sf = self._state_file()
        if sf.exists():
            try:
                data = json.loads(sf.read_text())
                self._disabled = set(data.get("disabled", []))
            except Exception:
                pass

    def _save_state(self):
        self._state_file().write_text(
            json.dumps({"disabled": list(self._disabled)}, indent=2)
        )

    def available_plugins(self) -> list:
        plugins = []
        try:
            for f in sorted(PLUGIN_DIR.glob("*.py")):
                name    = f.stem
                enabled = name not in self._disabled
                error   = self._errors.get(name, "")
                plugins.append({
                    "name":    name,
                    "path":    str(f),
                    "enabled": enabled,
                    "loaded":  name in self._loaded,
                    "error":   error,
                })
        except OSError:
            pass
        return plugins

    def load_all(self, ide) -> list:
        """Load and register all enabled plugins. Returns list of (name, ok, msg)."""
        results = []
        for f in sorted(PLUGIN_DIR.glob("*.py")):
            name = f.stem
            if name in self._disabled:
                results.append((name, None, "disabled"))
                continue
            ok, msg = self._load_one(name, f, ide)
            results.append((name, ok, msg))
        return results

    def _load_one(self, name: str, path: pathlib.Path, ide) -> tuple:
        import importlib.util
        try:
            spec   = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, "register"):
                module.register(ide)
            self._loaded[name] = module
            self._errors.pop(name, None)
            return True, "loaded"
        except Exception as e:
            msg = str(e)
            self._errors[name] = msg
            return False, msg

    def enable(self, name: str):
        self._disabled.discard(name)
        self._save_state()

    def disable(self, name: str):
        self._disabled.add(name)
        self._save_state()

    def create_example_plugin(self) -> str:
        """Write an example plugin file and return its path."""
        example = PLUGIN_DIR / "example_plugin.py"
        example.write_text(
            '"""\nexample_plugin.py — MyLang IDE Plugin Example\n\nThis plugin adds a "Hello from Plugin" item to the Tools menu.\n"""\n\n'
            'def register(ide):\n'
            '    """Called by the IDE when the plugin is loaded."""\n'
            '    from PySide6.QtGui import QAction\n'
            '    action = QAction("Hello from Plugin", ide)\n'
            '    action.triggered.connect(lambda: ide._console_info("Plugin says hello!\\n"))\n'
            '    # Find the Tools menu and add to it\n'
            '    for menu in ide.menuBar().findChildren(ide.menuBar().__class__):\n'
            '        if menu.title() == "&Tools":\n'
            '            menu.addSeparator()\n'
            '            menu.addAction(action)\n'
            '            break\n'
        )
        return str(example)


# ===========================================================================
# PLUGIN MANAGER DIALOG
# ===========================================================================

class PluginManagerDialog(QDialog):

    def __init__(self, parent, plugin_manager: PluginManager):
        super().__init__(parent)
        self.pm  = plugin_manager
        self.ide = parent
        self.setWindowTitle("Plugin Manager")
        self.setMinimumSize(640, 420)

        layout = QVBoxLayout(self)

        header = QLabel(
            f"  MyLang Plugin Manager  —  "
            f"plugins stored in  <code>{PLUGIN_DIR}</code>"
        )
        layout.addWidget(header)

        self.plugin_tree = QTreeWidget()
        self.plugin_tree.setColumnCount(3)
        self.plugin_tree.setHeaderLabels(["Plugin", "Status", "Error"])
        self.plugin_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.plugin_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.plugin_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.plugin_tree.setAlternatingRowColors(True)
        layout.addWidget(self.plugin_tree)

        action_row = QHBoxLayout()
        enable_btn  = QPushButton("Enable")
        enable_btn.clicked.connect(self._enable)
        disable_btn = QPushButton("Disable")
        disable_btn.clicked.connect(self._disable)
        example_btn = QPushButton("Create Example Plugin")
        example_btn.clicked.connect(self._create_example)
        open_dir_btn = QPushButton("Open Plugin Folder")
        open_dir_btn.clicked.connect(self._open_dir)
        for b in (enable_btn, disable_btn, example_btn, open_dir_btn):
            action_row.addWidget(b)
        layout.addLayout(action_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        note = QLabel(
            "  <i>Note: Plugin changes take effect after restarting the IDE.</i>"
        )
        layout.addWidget(note)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        self._refresh()

    def _refresh(self):
        self.plugin_tree.clear()
        for p in self.pm.available_plugins():
            status = "✓ Enabled" if p["enabled"] else "✗ Disabled"
            if p["error"]:
                status = f"⚠ Error"
            item = QTreeWidgetItem([p["name"], status, p["error"]])
            item.setData(0, Qt.UserRole, p["name"])
            self.plugin_tree.addTopLevelItem(item)

    def _enable(self):
        item = self.plugin_tree.currentItem()
        if item:
            self.pm.enable(item.data(0, Qt.UserRole))
            self._refresh()
            self.status_label.setText("Enabled — restart the IDE to activate.")

    def _disable(self):
        item = self.plugin_tree.currentItem()
        if item:
            self.pm.disable(item.data(0, Qt.UserRole))
            self._refresh()
            self.status_label.setText("Disabled — takes effect on restart.")

    def _create_example(self):
        path = self.pm.create_example_plugin()
        self._refresh()
        self.status_label.setText(f"Created: {path}")

    def _open_dir(self):
        import subprocess as sp
        try:
            if sys.platform == "win32":
                sp.Popen(["explorer", str(PLUGIN_DIR)])
            elif sys.platform == "darwin":
                sp.Popen(["open", str(PLUGIN_DIR)])
            else:
                sp.Popen(["xdg-open", str(PLUGIN_DIR)])
        except Exception as e:
            self.status_label.setText(str(e))


# ===========================================================================
# TERMINAL WIDGET
# ===========================================================================

class TerminalWidget(QWidget):
    """
    An embedded terminal that runs the system shell via QProcess.
    Output is displayed in a read-only QTextEdit.
    Commands are typed in a QLineEdit at the bottom.
    """

    def __init__(self, theme_name=DEFAULT_THEME, parent=None):
        super().__init__(parent)
        self.theme_name = theme_name
        self._history   = []
        self._hist_idx  = -1
        self._process   = None
        self._cwd       = str(pathlib.Path.home())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Output area
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Courier New", 12))
        layout.addWidget(self.output)

        # Input row
        input_row = QHBoxLayout()
        input_row.setContentsMargins(4, 2, 4, 4)

        self.prompt_label = QLabel("$")
        self.prompt_label.setFont(QFont("Courier New", 12))
        input_row.addWidget(self.prompt_label)

        self.input_line = QLineEdit()
        self.input_line.setFont(QFont("Courier New", 12))
        self.input_line.setPlaceholderText("Type a command and press Enter…")
        self.input_line.returnPressed.connect(self._run_command)
        self.input_line.installEventFilter(self)
        input_row.addWidget(self.input_line)

        layout.addLayout(input_row)

        self._print_banner()

    def _print_banner(self):
        c = THEME_COLORS[self.theme_name]
        self._append(
            f"MyLang IDE — Integrated Terminal\n"
            f"Working directory: {self._cwd}\n"
            f"Type 'help' for available commands.\n\n",
            c["panel_header_fg"]
        )
        self._print_prompt()

    def _print_prompt(self):
        c = THEME_COLORS[self.theme_name]
        cwd_short = pathlib.Path(self._cwd).name or self._cwd
        self.prompt_label.setText(f"  {cwd_short} $")

    def _run_command(self):
        cmd = self.input_line.text().strip()
        self.input_line.clear()
        if not cmd:
            return

        self._history.append(cmd)
        self._hist_idx = len(self._history)

        c = THEME_COLORS[self.theme_name]
        cwd_short = pathlib.Path(self._cwd).name or self._cwd
        self._append(f"  {cwd_short} $ {cmd}\n", c["accent"])

        # Built-in commands
        if cmd == "help":
            self._append(
                "Built-ins: help, clear, cd <dir>, pwd, exit\n"
                "Any other command runs in the system shell.\n\n",
                c["console_fg"]
            )
            self._print_prompt()
            return

        if cmd == "clear" or cmd == "cls":
            self.output.clear()
            self._print_prompt()
            return

        if cmd == "pwd":
            self._append(self._cwd + "\n", c["console_fg"])
            self._print_prompt()
            return

        if cmd.startswith("cd "):
            target = cmd[3:].strip().strip('"')
            new_dir = pathlib.Path(self._cwd) / target
            try:
                new_dir = new_dir.resolve()
                if new_dir.is_dir():
                    self._cwd = str(new_dir)
                    self._print_prompt()
                else:
                    self._append(f"cd: no such directory: {target}\n", c["bp_color"])
            except Exception as e:
                self._append(str(e) + "\n", c["bp_color"])
            return

        # Run via system shell
        try:
            if sys.platform == "win32":
                shell_cmd = ["cmd", "/c", cmd]
            else:
                shell_cmd = ["sh", "-c", cmd]

            result = subprocess.run(
                shell_cmd,
                cwd=self._cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.stdout:
                self._append(result.stdout, c["console_fg"])
            if result.stderr:
                self._append(result.stderr, c["bp_color"])
        except subprocess.TimeoutExpired:
            self._append("Command timed out (30s).\n", c["bp_color"])
        except Exception as e:
            self._append(f"Error: {e}\n", c["bp_color"])

        self._print_prompt()

    def _append(self, text: str, color: str):
        self.output.moveCursor(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        self.output.textCursor().insertText(text, fmt)
        self.output.moveCursor(QTextCursor.End)

    def eventFilter(self, obj, event):
        if obj is self.input_line:
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.KeyPress:
                if event.key() == Qt.Key_Up:
                    if self._history and self._hist_idx > 0:
                        self._hist_idx -= 1
                        self.input_line.setText(self._history[self._hist_idx])
                    return True
                if event.key() == Qt.Key_Down:
                    if self._hist_idx < len(self._history) - 1:
                        self._hist_idx += 1
                        self.input_line.setText(self._history[self._hist_idx])
                    else:
                        self._hist_idx = len(self._history)
                        self.input_line.clear()
                    return True
        return super().eventFilter(obj, event)

    def set_cwd(self, path: str):
        """Set the terminal working directory to match the open file."""
        if pathlib.Path(path).is_dir():
            self._cwd = path
            self._print_prompt()

    def apply_theme(self, theme_name: str):
        self.theme_name = theme_name
        c = THEME_COLORS[theme_name]
        self.output.setStyleSheet(
            f"background:{c['console_bg']}; color:{c['console_fg']};"
        )
        self.input_line.setStyleSheet(
            f"background:{c['btn_bg']}; color:{c['btn_fg']};"
            f"border:1px solid {c['btn_border']}; border-radius:4px;"
            f"font-family:Courier New; font-size:12px; padding:3px 6px;"
        )
        self.prompt_label.setStyleSheet(f"color:{c['accent']}; font-weight:bold;")


# ===========================================================================
# NEW FROM TEMPLATE DIALOG
# ===========================================================================

class NewFromTemplateDialog(QDialog):

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("New Project from Template")
        self.setMinimumSize(640, 480)
        self._chosen_template = None
        self._chosen_dir      = None

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("  Select a template:"))

        self.tmpl_tree = QTreeWidget()
        self.tmpl_tree.setColumnCount(2)
        self.tmpl_tree.setHeaderLabels(["Template", "Description"])
        self.tmpl_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tmpl_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tmpl_tree.itemSelectionChanged.connect(self._on_select)
        layout.addWidget(self.tmpl_tree)

        # Built-in templates
        bi_root = QTreeWidgetItem(["Built-in Templates", ""])
        self.tmpl_tree.addTopLevelItem(bi_root)
        for name, info in BUILTIN_TEMPLATES.items():
            item = QTreeWidgetItem([f"  {name}", info["description"]])
            item.setData(0, Qt.UserRole, ("builtin", name))
            bi_root.addChild(item)
        bi_root.setExpanded(True)

        # User templates from ~/.mylang/templates/
        user_tmpls = list(TEMPLATE_DIR.glob("*.my")) + list(TEMPLATE_DIR.glob("*.json"))
        if user_tmpls:
            user_root = QTreeWidgetItem(["My Templates", ""])
            self.tmpl_tree.addTopLevelItem(user_root)
            for f in sorted(user_tmpls):
                item = QTreeWidgetItem([f"  {f.stem}", str(f)])
                item.setData(0, Qt.UserRole, ("user", str(f)))
                user_root.addChild(item)
            user_root.setExpanded(True)

        # Preview
        layout.addWidget(QLabel("  Preview:"))
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setFont(QFont("Courier New", 11))
        self.preview.setMaximumHeight(160)
        layout.addWidget(self.preview)

        # Destination
        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("  Save to:"))
        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("Choose destination folder…")
        dest_row.addWidget(self.dest_input)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_dest)
        dest_row.addWidget(browse_btn)
        layout.addLayout(dest_row)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_select(self):
        items = self.tmpl_tree.selectedItems()
        if not items:
            return
        item = items[0]
        data = item.data(0, Qt.UserRole)
        if data is None:
            return
        kind, ref = data
        if kind == "builtin":
            info    = BUILTIN_TEMPLATES[ref]
            # Show first file content in preview
            first   = next(iter(info["files"].values()))
            self.preview.setPlainText(first)
            self._chosen_template = ("builtin", ref)
        elif kind == "user":
            try:
                self.preview.setPlainText(pathlib.Path(ref).read_text())
            except Exception:
                self.preview.setPlainText("(could not read template)")
            self._chosen_template = ("user", ref)

    def _browse_dest(self):
        d = QFileDialog.getExistingDirectory(self, "Choose destination folder")
        if d:
            self.dest_input.setText(d)

    def _on_ok(self):
        if not self._chosen_template:
            QMessageBox.warning(self, "No template", "Please select a template.")
            return
        dest = self.dest_input.text().strip()
        if not dest:
            QMessageBox.warning(self, "No destination", "Please choose a destination folder.")
            return
        self._chosen_dir = dest
        self.accept()

    def result_template(self):
        return self._chosen_template

    def result_dir(self):
        return self._chosen_dir


# ===========================================================================
# EXPORT DIALOG
# ===========================================================================

class ExportDialog(QDialog):
    """
    Four export modes:
      1. Standalone — copies .my file + launcher + interpreter files into a folder
      2. Package    — zips the project for distribution
      3. Docs       — generates Markdown documentation from function symbols
      4. Syntax     — exports token list and AST as JSON
    """

    def __init__(self, parent, current_file: str, symbol_table: SymbolTable,
                 source: str, tokens: list, ast_nodes: list):
        super().__init__(parent)
        self.current_file  = current_file
        self.sym           = symbol_table
        self.source        = source
        self.tokens        = tokens
        self.ast_nodes     = ast_nodes
        self.ide_dir       = IDE_DIR

        self.setWindowTitle("Export / Build")
        self.setMinimumSize(620, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("  Choose export type:"))

        self.mode_tree = QTreeWidget()
        self.mode_tree.setColumnCount(2)
        self.mode_tree.setHeaderLabels(["Mode", "Description"])
        self.mode_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.mode_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)

        modes = [
            ("📦  Standalone Script",
             "Copy the script + interpreter files into a runnable folder"),
            ("🗜  Package ZIP",
             "Create a distributable .zip of the project"),
            ("📄  Generate Documentation",
             "Write a Markdown doc from function signatures and doc comments"),
            ("🔍  Syntax Report (JSON)",
             "Export token list and AST as a JSON file"),
        ]
        for label, desc in modes:
            item = QTreeWidgetItem([label, desc])
            self.mode_tree.addTopLevelItem(item)

        self.mode_tree.setCurrentItem(self.mode_tree.topLevelItem(0))
        layout.addWidget(self.mode_tree)

        # Destination
        dest_row = QHBoxLayout()
        dest_row.addWidget(QLabel("  Output folder:"))
        self.dest_input = QLineEdit()
        self.dest_input.setPlaceholderText("Choose output folder…")
        if current_file:
            self.dest_input.setText(os.path.dirname(current_file))
        dest_row.addWidget(self.dest_input)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse)
        dest_row.addWidget(browse_btn)
        layout.addLayout(dest_row)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._do_export)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _browse(self):
        d = QFileDialog.getExistingDirectory(self, "Choose output folder")
        if d:
            self.dest_input.setText(d)

    def _do_export(self):
        item = self.mode_tree.currentItem()
        if not item:
            return
        mode = self.mode_tree.indexOfTopLevelItem(item)
        dest = self.dest_input.text().strip()
        if not dest:
            QMessageBox.warning(self, "No destination", "Please choose an output folder.")
            return

        try:
            if mode == 0:
                path = self._export_standalone(dest)
            elif mode == 1:
                path = self._export_zip(dest)
            elif mode == 2:
                path = self._export_docs(dest)
            elif mode == 3:
                path = self._export_syntax(dest)
            else:
                return

            self.status_label.setText(f"✓  Exported to: {path}")
            QMessageBox.information(self, "Export Complete", f"Exported to:\n{path}")
            self.accept()

        except Exception as e:
            self.status_label.setText(f"✗  Error: {e}")
            QMessageBox.critical(self, "Export Error", str(e))

    # ── Standalone ──────────────────────────────────────────────────────────

    def _export_standalone(self, dest: str) -> str:
        if not self.current_file:
            raise ValueError("No file is currently open.")

        script_name = pathlib.Path(self.current_file).stem
        out_dir     = pathlib.Path(dest) / f"{script_name}_standalone"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Copy the .my script
        shutil.copy2(self.current_file, out_dir)

        # Copy interpreter files
        interp_files = [
            "lexer.py", "parser.py", "ast_nodes.py",
            "ast_interpreter.py", "runtime_error.py", "parser_error.py",
        ]
        for fname in interp_files:
            src = pathlib.Path(self.ide_dir) / fname
            if src.exists():
                shutil.copy2(src, out_dir)

        # Write a simple launcher
        launcher = out_dir / "run.py"
        script_base = pathlib.Path(self.current_file).name
        launcher.write_text(
            f'#!/usr/bin/env python3\n'
            f'"""Launcher for {script_name}"""\n'
            f'import sys, os\n'
            f'sys.path.insert(0, os.path.dirname(__file__))\n'
            f'from lexer import Lexer\n'
            f'from parser import Parser\n'
            f'from ast_interpreter import ASTInterpreter\n'
            f'from runtime_error import MyLangRuntimeError\n'
            f'from parser_error import MyLangSyntaxError\n\n'
            f'SCRIPT = os.path.join(os.path.dirname(__file__), "{script_base}")\n\n'
            f'with open(SCRIPT, "r") as f:\n'
            f'    code = f.read()\n\n'
            f'try:\n'
            f'    script_dir = os.path.dirname(os.path.abspath(SCRIPT))\n'
            f'    ASTInterpreter(\n'
            f'        module_search_paths=[script_dir],\n'
            f'        file_root=script_dir,\n'
            f'    ).run(__import__("parser").Parser('
            f'__import__("lexer").Lexer(code).tokenize()).parse())\n'
            f'except MyLangSyntaxError as e:\n'
            f'    print(f"SYNTAX ERROR:\\n{{e}}")\n'
            f'except MyLangRuntimeError as e:\n'
            f'    print(f"RUNTIME ERROR:\\n{{e}}")\n'
        )

        # Write README
        readme = out_dir / "README.txt"
        readme.write_text(
            f"{script_name} — MyLang Standalone\n"
            f"{'=' * 40}\n\n"
            f"Run with:\n    python run.py\n\n"
            f"Requires Python 3.10+\n"
        )

        return str(out_dir)

    # ── ZIP package ─────────────────────────────────────────────────────────

    def _export_zip(self, dest: str) -> str:
        if not self.current_file:
            raise ValueError("No file is currently open.")

        script_name = pathlib.Path(self.current_file).stem
        zip_path    = pathlib.Path(dest) / f"{script_name}.zip"
        script_dir  = pathlib.Path(self.current_file).parent

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Add all .my files from the script's directory
            for my_file in sorted(script_dir.glob("*.my")):
                zf.write(my_file, my_file.name)
            # Add a manifest
            manifest = {
                "name":    script_name,
                "entry":   pathlib.Path(self.current_file).name,
                "created": __import__("datetime").datetime.now().isoformat(),
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        return str(zip_path)

    # ── Documentation ───────────────────────────────────────────────────────

    def _export_docs(self, dest: str) -> str:
        if not self.current_file:
            raise ValueError("No file is currently open.")

        script_name = pathlib.Path(self.current_file).stem
        doc_path    = pathlib.Path(dest) / f"{script_name}_docs.md"

        lines = []
        lines.append(f"# {script_name} — Documentation\n")
        lines.append(f"*Generated by MyLang IDE*\n\n")

        if self.sym.imports:
            lines.append("## Imports\n")
            for imp in self.sym.imports:
                lines.append(f"- `import {imp['path']}`  (line {imp['line']})\n")
            lines.append("\n")

        if self.sym.functions:
            lines.append("## Functions\n")
            for name, info in sorted(self.sym.functions.items()):
                params = ", ".join(info["params"])
                lines.append(f"### `{name}({params})`\n")
                lines.append(f"*Defined at line {info['line']}*\n\n")
                if info.get("doc"):
                    lines.append(f"{info['doc']}\n\n")
                else:
                    lines.append("*(no documentation comment)*\n\n")

        if self.sym.variables:
            lines.append("## Module-Level Variables\n")
            for name, info in sorted(self.sym.variables.items()):
                lines.append(
                    f"- **`{name}`**  —  {info['value_repr']}  "
                    f"(line {info['line']})\n"
                )
            lines.append("\n")

        doc_path.write_text("".join(lines), encoding="utf-8")
        return str(doc_path)

    # ── Syntax report ───────────────────────────────────────────────────────

    def _export_syntax(self, dest: str) -> str:
        if not self.current_file:
            raise ValueError("No file is currently open.")

        script_name = pathlib.Path(self.current_file).stem
        json_path   = pathlib.Path(dest) / f"{script_name}_syntax.json"

        def node_to_dict(node):
            if node is None:
                return None
            d = {"type": type(node).__name__}
            for attr in vars(node):
                if attr.startswith("_"):
                    continue
                val = getattr(node, attr)
                if isinstance(val, list):
                    d[attr] = [node_to_dict(v) if hasattr(v, "__class__") and
                               v.__class__.__module__ == "ast_nodes" else repr(v)
                               for v in val]
                elif hasattr(val, "__class__") and val.__class__.__module__ == "ast_nodes":
                    d[attr] = node_to_dict(val)
                else:
                    d[attr] = repr(val)
            return d

        report = {
            "file":   pathlib.Path(self.current_file).name,
            "tokens": [
                {"line": t.line, "type": t.type, "value": repr(t.value)}
                for t in self.tokens
            ],
            "ast": [node_to_dict(n) for n in self.ast_nodes],
        }

        json_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        return str(json_path)


# ===========================================================================
# JUMP-TO-LINE DIALOG
# ===========================================================================

class JumpToLineDialog(QDialog):
    def __init__(self, parent, max_line, current_line):
        super().__init__(parent)
        self.setWindowTitle("Jump to Line"); self.setModal(True); self.setFixedSize(300, 120)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.spin = QSpinBox(); self.spin.setRange(1, max_line); self.spin.setValue(current_line)
        self.spin.selectAll(); form.addRow("Line number:", self.spin); layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)
    def line_number(self): return self.spin.value()


# ===========================================================================
# MAIN WINDOW
# ===========================================================================

class MyLangIDE(QMainWindow):

    def __init__(self, initial_file=None):
        super().__init__()

        self.current_file     = None
        self.is_modified      = False
        self.worker           = None
        self.analysis_worker  = None
        self.debug_controller = None
        self.theme_name       = DEFAULT_THEME
        self._debug_mode      = False
        self._autocomplete_on = True
        self._symbol_table    = SymbolTable()
        self._formatter       = CodeFormatter()
        self._last_tokens     = []
        self._last_ast        = []

        # Phase 5 — Ecosystem
        self._pkg_manager    = PackageManager()
        self._plugin_manager = PluginManager()

        self.analysis_timer = QTimer()
        self.analysis_timer.setSingleShot(True)
        self.analysis_timer.setInterval(400)
        self.analysis_timer.timeout.connect(self._run_analysis)

        self.setWindowTitle("MyLang IDE")
        self.resize(1480, 900)
        self.setMinimumSize(1000, 640)

        self._build_ui()
        self._build_menu()
        self._build_toolbar()
        self._build_debug_toolbar()
        self._build_ecosystem_toolbar()
        self._build_statusbar()
        self._apply_theme(DEFAULT_THEME)

        # Load plugins after UI is ready
        self._plugin_manager.load_all(self)

        if initial_file and os.path.isfile(initial_file):
            self._open_file(initial_file)
        else:
            self._new_file()

    # =======================================================================
    # UI CONSTRUCTION
    # =======================================================================

    def _build_ui(self):

        self.v_split = QSplitter(Qt.Vertical)
        self.setCentralWidget(self.v_split)

        # ── Editor ────────────────────────────────────────────────────────
        self.editor = CodeEditor(self.theme_name)
        self.editor.modificationChanged.connect(self._on_modified)
        self.editor.cursorPositionChanged.connect(self._update_statusbar)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.autocomplete_requested.connect(self._show_autocomplete)
        self.editor.hint_requested.connect(self._handle_hint_or_action)
        self.editor.hint_cleared.connect(self._clear_hint)

        self.highlighter = MyLangHighlighter(self.editor.document(), self.theme_name)
        self.v_split.addWidget(self.editor)

        # ── Function hint bar (inserted between toolbar and editor) ───────
        self.hint_bar = FunctionHintBar()

        # ── Autocomplete popup ────────────────────────────────────────────
        self.autocomplete = AutoCompletePopup()
        self.autocomplete.item_selected.connect(self._apply_completion)

        # ── Output console + Terminal — tabbed in the bottom pane ─────────
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setTabPosition(QTabWidget.South)

        # Output console tab
        console_wrap   = QWidget()
        console_layout = QVBoxLayout(console_wrap)
        console_layout.setContentsMargins(0, 0, 0, 0)
        console_layout.setSpacing(0)

        self.console_header = QWidget()
        self.console_header.setFixedHeight(30)
        ch_layout = QHBoxLayout(self.console_header)
        ch_layout.setContentsMargins(10, 0, 10, 0)
        self.console_header_label = QLabel("OUTPUT")
        ch_layout.addWidget(self.console_header_label)
        ch_layout.addStretch()
        console_layout.addWidget(self.console_header)

        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setFont(QFont("Courier New", 12))
        console_layout.addWidget(self.console)

        self.bottom_tabs.addTab(console_wrap, "Output")

        # Terminal tab
        self.terminal = TerminalWidget(self.theme_name)
        self.bottom_tabs.addTab(self.terminal, ">_ Terminal")

        self.v_split.addWidget(self.bottom_tabs)
        self.v_split.setSizes([600, 240])

        # ── PROJECT DOCK (left) — Files + Symbols tabs ────────────────────
        self.file_dock = QDockWidget("PROJECT")
        self.file_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.file_dock.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )

        self.project_tabs = QTabWidget()

        # Files tab
        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabel("Files")
        self.file_tree.setColumnCount(1)
        self.file_tree.itemDoubleClicked.connect(self._tree_open_file)
        self.project_tabs.addTab(self.file_tree, "Files")

        # Symbols tab
        self.symbol_tree = QTreeWidget()
        self.symbol_tree.setColumnCount(2)
        self.symbol_tree.setHeaderLabels(["Symbol", "Detail"])
        self.symbol_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.symbol_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.symbol_tree.itemDoubleClicked.connect(self._symbol_jump)
        self.project_tabs.addTab(self.symbol_tree, "Symbols")

        self.file_dock.setWidget(self.project_tabs)
        self.file_dock.setMinimumWidth(210)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.file_dock)
        self._refresh_file_tree()

        # ── LANGUAGE SERVICES DOCK (right) ───────────────────────────────
        self.lang_dock = QDockWidget("LANGUAGE SERVICES")
        self.lang_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        self.lang_dock.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )
        self.lang_tabs = QTabWidget()

        self.token_tree = QTreeWidget()
        self.token_tree.setColumnCount(3)
        self.token_tree.setHeaderLabels(["Line", "Type", "Value"])
        self.token_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.token_tree.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.token_tree.header().setSectionResizeMode(2, QHeaderView.Stretch)
        self.token_tree.setAlternatingRowColors(True)
        self.lang_tabs.addTab(self.token_tree, "Tokens")

        self.ast_tree = QTreeWidget()
        self.ast_tree.setColumnCount(2)
        self.ast_tree.setHeaderLabels(["Node", "Value"])
        self.ast_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.ast_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.ast_tree.setAlternatingRowColors(True)
        self.lang_tabs.addTab(self.ast_tree, "AST")

        self.lang_dock.setWidget(self.lang_tabs)
        self.lang_dock.setMinimumWidth(280)
        self.addDockWidget(Qt.RightDockWidgetArea, self.lang_dock)
        self.lang_dock.hide()

        # ── DEBUG DOCK (right, tabbed) ────────────────────────────────────
        self.debug_dock = QDockWidget("DEBUGGER")
        self.debug_dock.setAllowedAreas(
            Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea
        )
        self.debug_dock.setFeatures(
            QDockWidget.DockWidgetClosable | QDockWidget.DockWidgetMovable | QDockWidget.DockWidgetFloatable
        )
        self.debug_tabs = QTabWidget()

        self.var_tree = QTreeWidget()
        self.var_tree.setColumnCount(2)
        self.var_tree.setHeaderLabels(["Variable", "Value"])
        self.var_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.var_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.var_tree.setAlternatingRowColors(True)
        self.debug_tabs.addTab(self.var_tree, "Variables")

        self.stack_tree = QTreeWidget()
        self.stack_tree.setColumnCount(2)
        self.stack_tree.setHeaderLabels(["Frame", "Location"])
        self.stack_tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.stack_tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.stack_tree.setAlternatingRowColors(True)
        self.debug_tabs.addTab(self.stack_tree, "Call Stack")

        self.exc_view = QTextEdit()
        self.exc_view.setReadOnly(True)
        self.exc_view.setFont(QFont("Courier New", 12))
        self.debug_tabs.addTab(self.exc_view, "Exceptions")

        self.debug_dock.setWidget(self.debug_tabs)
        self.debug_dock.setMinimumWidth(300)
        self.debug_dock.setMinimumHeight(180)
        self.addDockWidget(Qt.RightDockWidgetArea, self.debug_dock)
        self.tabifyDockWidget(self.lang_dock, self.debug_dock)
        self.debug_dock.hide()

    # -----------------------------------------------------------------------

    def _build_menu(self):
        mb = self.menuBar()

        # File
        fm = mb.addMenu("&File")
        fm.addAction(self._action("New",      self._new_file,         QKeySequence.New))
        fm.addAction(self._action("Open…",    self._open_file_dialog, QKeySequence.Open))
        fm.addSeparator()
        fm.addAction(self._action("Save",     self._save_file,        QKeySequence.Save))
        fm.addAction(self._action("Save As…", self._save_file_as,     QKeySequence("Ctrl+Shift+S")))
        fm.addSeparator()
        fm.addAction(self._action("Exit",     self.close,             QKeySequence.Quit))

        # Run
        rm = mb.addMenu("&Run")
        self.act_run   = self._action("▶  Run",       self._run_code,    QKeySequence("F5"))
        self.act_debug = self._action("🐞  Debug",     self._debug_code,  QKeySequence("F7"))
        self.act_stop  = self._action("⏹  Stop",      self._stop_run,    QKeySequence("F6"))
        self.act_cont  = self._action("⏩  Continue",  self._dbg_continue,QKeySequence("F5"))
        self.act_step  = self._action("⤵  Step Over", self._dbg_step,    QKeySequence("F10"))
        self.act_stop.setEnabled(False)
        self.act_cont.setEnabled(False)
        self.act_step.setEnabled(False)
        for a in (self.act_run, self.act_debug, self.act_stop, self.act_cont, self.act_step):
            rm.addAction(a)

        # Language
        lm = mb.addMenu("&Language")
        lm.addAction(self._action("Analyse Now",         self._run_analysis,    QKeySequence("Ctrl+Shift+P")))
        lm.addAction(self._action("Jump to Line…",       self._jump_to_line,    QKeySequence("Ctrl+G")))
        lm.addSeparator()
        lm.addAction(self._action("Toggle Token Viewer", self._toggle_lang_dock,QKeySequence("Ctrl+T")))
        lm.addAction(self._action("Show Tokens Tab",     lambda: self._show_lang_tab(0), QKeySequence("Ctrl+Shift+T")))
        lm.addAction(self._action("Show AST Tab",        lambda: self._show_lang_tab(1), QKeySequence("Ctrl+Shift+A")))

        # Tools  (Phase 4)
        tm = mb.addMenu("&Tools")
        tm.addAction(self._action("Format Document",     self._format_document,   QKeySequence("Shift+Alt+F")))
        tm.addAction(self._action("Find References…",   self._find_references,   QKeySequence("Shift+F12")))
        tm.addAction(self._action("Go to Definition",    self._go_to_definition,  QKeySequence("F12")))
        tm.addSeparator()
        tm.addAction(self._action("Autocomplete  (Ctrl+Space)", self._force_autocomplete, QKeySequence("Ctrl+Space")))
        self.act_ac_toggle = self._action(
            "Toggle Autocomplete  [on]",
            self._toggle_autocomplete
        )
        tm.addAction(self.act_ac_toggle)
        tm.addSeparator()
        tm.addAction(self._action("Show Symbol Table",   self._show_symbol_tab,   QKeySequence("Ctrl+Shift+S")))

        # Debug
        dm = mb.addMenu("&Debug")
        dm.addAction(self._action("Toggle Debugger Panel", self._toggle_debug_dock, QKeySequence("Ctrl+D")))
        dm.addAction(self._action("Clear All Breakpoints", self._clear_breakpoints, QKeySequence("Ctrl+Shift+B")))
        dm.addSeparator()
        dm.addAction(self._action("Show Variables",  lambda: self._show_debug_tab(0), QKeySequence("Ctrl+Shift+V")))
        dm.addAction(self._action("Show Call Stack", lambda: self._show_debug_tab(1), QKeySequence("Ctrl+Shift+C")))
        dm.addAction(self._action("Show Exceptions", lambda: self._show_debug_tab(2), QKeySequence("Ctrl+Shift+E")))

        # View
        vm = mb.addMenu("&View")
        vm.addAction(self._action(
            "Toggle File Explorer",
            lambda: self.file_dock.setVisible(not self.file_dock.isVisible()),
            QKeySequence("Ctrl+\\")
        ))
        vm.addAction(self._action(
            "Toggle Ecosystem Toolbar",
            lambda: self.eco_toolbar.setVisible(not self.eco_toolbar.isVisible()),
            QKeySequence("Ctrl+Shift+W")
        ))
        vm.addSeparator()
        vm.addAction(self._action("Clear Console", self._clear_console, QKeySequence("Ctrl+K")))

        # Ecosystem  (Phase 5)
        em = mb.addMenu("&Ecosystem")
        em.addAction(self._action("Package Manager…",        self._open_pkg_manager,     QKeySequence("Ctrl+Shift+M")))
        em.addAction(self._action("Plugin Manager…",         self._open_plugin_manager,  QKeySequence("Ctrl+Shift+L")))
        em.addSeparator()
        em.addAction(self._action("Terminal  (Ctrl+`)",      self._toggle_terminal,      QKeySequence("Ctrl+`")))
        em.addSeparator()
        em.addAction(self._action("New from Template…",      self._new_from_template,    QKeySequence("Ctrl+Shift+N")))
        em.addSeparator()
        em.addAction(self._action("Export / Build…",         self._open_export,          QKeySequence("Ctrl+Shift+X")))

    # -----------------------------------------------------------------------

    def _build_toolbar(self):
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setObjectName("main_toolbar")
        self.addToolBar(tb)

        # ── File ──────────────────────────────────────────────────────────
        self._tb_btn(tb, "⬜  New",    self._new_file,         "New  (Ctrl+N)")
        self._tb_btn(tb, "📂  Open",   self._open_file_dialog, "Open  (Ctrl+O)")
        self._tb_btn(tb, "💾  Save",   self._save_file,        "Save  (Ctrl+S)")
        tb.addSeparator()

        # ── Run / Debug ───────────────────────────────────────────────────
        self.btn_run   = self._tb_btn(tb, "▶   Run",   self._run_code,   "Run  (F5)")
        self.btn_debug = self._tb_btn(tb, "🐞  Debug", self._debug_code, "Debug  (F7)")
        self.btn_stop  = self._tb_btn(tb, "⏹   Stop",  self._stop_run,   "Stop  (F6)")
        self.btn_stop.setEnabled(False)
        tb.addSeparator()

        # ── Editor tools ──────────────────────────────────────────────────
        self._tb_btn(tb, "🗑   Clear",  self._clear_console,   "Clear console  (Ctrl+K)")
        self._tb_btn(tb, "⚡  Analyse", self._run_analysis,    "Analyse  (Ctrl+Shift+P)")
        self._tb_btn(tb, "↓  Jump",     self._jump_to_line,    "Jump to line  (Ctrl+G)")
        self._tb_btn(tb, "{}  Tokens",  self._toggle_lang_dock,"Token/AST panel  (Ctrl+T)")
        tb.addSeparator()

        # ── Theme selector — right-aligned ────────────────────────────────
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)

        theme_label = QLabel("  Theme  ")
        theme_label.setStyleSheet("font-size: 12px;")
        tb.addWidget(theme_label)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEMES.keys()))
        self.theme_combo.setCurrentText(DEFAULT_THEME)
        self.theme_combo.currentTextChanged.connect(self._apply_theme)
        tb.addWidget(self.theme_combo)

    def _build_debug_toolbar(self):
        self.dbg_toolbar = QToolBar("Debug Toolbar")
        self.dbg_toolbar.setMovable(False)
        self.dbg_toolbar.setObjectName("debug_toolbar")
        self.addToolBar(self.dbg_toolbar)

        self.dbg_toolbar.addWidget(QLabel("  DEBUG  "))
        self.dbg_toolbar.addSeparator()
        self.btn_cont = self._tb_btn(self.dbg_toolbar, "⏩  Continue", self._dbg_continue, "Continue  (F5)")
        self.btn_cont.setObjectName("dbg_cont")
        self.btn_step = self._tb_btn(self.dbg_toolbar, "⤵  Step Over", self._dbg_step, "Step Over  (F10)")
        self.btn_step.setObjectName("dbg_step")
        self.dbg_toolbar.addSeparator()
        b = self._tb_btn(self.dbg_toolbar, "✕  Clear Breakpoints", self._clear_breakpoints, "Clear all breakpoints")
        b.setObjectName("dbg_clear")
        b2 = self._tb_btn(self.dbg_toolbar, "☰  Debug Panel", self._toggle_debug_dock, "Toggle debug panel  (Ctrl+D)")
        b2.setObjectName("dbg_clear")
        self.btn_cont.setEnabled(False)
        self.btn_step.setEnabled(False)
        self.dbg_toolbar.hide()

    def _build_ecosystem_toolbar(self):
        """Phase 5 — always-visible ecosystem toolbar row."""
        self.eco_toolbar = QToolBar("Ecosystem Toolbar")
        self.eco_toolbar.setMovable(False)
        self.eco_toolbar.setObjectName("eco_toolbar")
        self.addToolBar(self.eco_toolbar)

        eco_label = QLabel("  ECOSYSTEM  ")
        eco_label.setStyleSheet(
            "font-weight: bold; font-size: 11px; "
            "letter-spacing: 1px; padding: 0 4px;"
        )
        self.eco_toolbar.addWidget(eco_label)
        self.eco_toolbar.addSeparator()

        self._tb_btn(self.eco_toolbar, "📦  Packages",
                     self._open_pkg_manager,   "Package manager  (Ctrl+Shift+M)")
        self._tb_btn(self.eco_toolbar, "🔌  Plugins",
                     self._open_plugin_manager, "Plugin manager  (Ctrl+Shift+L)")
        self.eco_toolbar.addSeparator()
        self._tb_btn(self.eco_toolbar, ">_  Terminal",
                     self._toggle_terminal,    "Toggle terminal  (Ctrl+`)")
        self.eco_toolbar.addSeparator()
        self._tb_btn(self.eco_toolbar, "⧉  Template",
                     self._new_from_template,  "New from template  (Ctrl+Shift+N)")
        self.eco_toolbar.addSeparator()
        self._tb_btn(self.eco_toolbar, "↗  Export",
                     self._open_export,        "Export / Build  (Ctrl+Shift+X)")

        # Hidden by default — toggle via View > Ecosystem Toolbar
        self.eco_toolbar.hide()

    # =======================================================================
    # PHASE 5 — ECOSYSTEM METHODS
    # =======================================================================

    # ── Package Manager ───────────────────────────────────────────────────

    def _open_pkg_manager(self):
        # Make the packages dir available to the interpreter automatically
        dlg = PackageManagerDialog(self, self._pkg_manager)
        dlg.exec()
        # Ensure packages dir is on every future interpreter's search path
        # (already handled in _run_code / _debug_code via script_dir; the
        # package dir is added as a second entry in the ASTInterpreter call)

    # ── Plugin Manager ────────────────────────────────────────────────────

    def _open_plugin_manager(self):
        dlg = PluginManagerDialog(self, self._plugin_manager)
        dlg.exec()

    # ── Terminal ──────────────────────────────────────────────────────────

    def _toggle_terminal(self):
        terminal_tab_index = 1   # "Output" is 0, ">_ Terminal" is 1
        current = self.bottom_tabs.currentIndex()
        if current == terminal_tab_index:
            # Already on terminal — switch back to output
            self.bottom_tabs.setCurrentIndex(0)
        else:
            self.bottom_tabs.setCurrentIndex(terminal_tab_index)
            self.terminal.input_line.setFocus()
            # Sync cwd to current file's directory
            if self.current_file:
                self.terminal.set_cwd(
                    os.path.dirname(self.current_file)
                )

    # ── Project Templates ─────────────────────────────────────────────────

    def _new_from_template(self):
        if not self._confirm_discard():
            return

        dlg = NewFromTemplateDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return

        tmpl  = dlg.result_template()
        dest  = dlg.result_dir()

        if not tmpl or not dest:
            return

        kind, ref = tmpl
        dest_path = pathlib.Path(dest)

        try:
            if kind == "builtin":
                info  = BUILTIN_TEMPLATES[ref]
                files = info["files"]
                # Write all template files
                written = []
                for fname, content in files.items():
                    out = dest_path / fname
                    out.write_text(content, encoding="utf-8")
                    written.append(str(out))
                # Open the first file
                first_file = dest_path / next(iter(files))
                self._open_file(str(first_file))
                self._console_info(
                    f"Template '{ref}' created:\n"
                    + "\n".join(f"  {w}" for w in written)
                    + "\n"
                )

            elif kind == "user":
                src = pathlib.Path(ref)
                if src.suffix == ".my":
                    dest_file = dest_path / src.name
                    shutil.copy2(src, dest_file)
                    self._open_file(str(dest_file))
                elif src.suffix == ".json":
                    # JSON template: {files: {name: content}}
                    data  = json.loads(src.read_text())
                    files = data.get("files", {})
                    for fname, content in files.items():
                        (dest_path / fname).write_text(content)
                    if files:
                        self._open_file(str(dest_path / next(iter(files))))

        except Exception as e:
            QMessageBox.critical(self, "Template Error", str(e))

    # ── Export / Build ────────────────────────────────────────────────────

    def _open_export(self):
        dlg = ExportDialog(
            self,
            self.current_file or "",
            self._symbol_table,
            self.editor.toPlainText(),
            self._last_tokens,
            self._last_ast,
        )
        dlg.exec()

    # =======================================================================
    # PHASE 5 — RUNTIME: package search path injection
    # =======================================================================

    def _make_interpreter(self, script_dir: str) -> "ASTInterpreter":
        """
        Create an ASTInterpreter with both the script dir and the
        global packages dir on the module search path.
        """
        search = [script_dir, str(PKG_DIR)]
        return ASTInterpreter(
            module_search_paths=search,
            file_root=script_dir,
        )

    def _build_statusbar(self):
        sb = self.statusBar()
        self.status_file   = QLabel("  Untitled")
        self.status_errors = QLabel("  ✓ Ready")
        self.status_debug  = QLabel("")
        self.status_pos    = QLabel("Ln 1, Col 1")
        self.status_lang   = QLabel(f"MyLang v{VERSION}  ")
        sb.addWidget(self.status_file,   1)
        sb.addPermanentWidget(self.status_errors)
        sb.addPermanentWidget(self.status_debug)
        sb.addPermanentWidget(self.status_pos)
        sb.addPermanentWidget(self.status_lang)

    # =======================================================================
    # THEMING
    # =======================================================================

    def _apply_theme(self, name):
        self.theme_name = name
        QApplication.instance().setStyleSheet(THEMES[name])
        c = THEME_COLORS[name]

        self.editor.apply_theme(name)
        self.editor.gutter.update()
        self.editor._highlight_current_line()
        self.highlighter.apply_theme(name)

        self.hint_bar.setStyleSheet(
            f"background:{c['panel_header']}; color:{c['panel_header_fg']};"
            f"border-bottom:1px solid {c['border']}; font-size:12px;"
        )
        self.console_header.setStyleSheet(
            f"background:{c['panel_header']}; border-bottom:1px solid {c['border']};"
        )
        self.console_header_label.setStyleSheet(
            f"color:{c['panel_header_fg']}; font-size:11px; font-weight:bold; letter-spacing:1px;"
        )

        self._console_color_out  = c["console_fg"]
        self._console_color_err  = c["bp_color"]
        self._console_color_info = c["panel_header_fg"]
        self._status_ok_color    = c["panel_header_fg"]
        self._status_err_color   = c["bp_color"]
        self._dbg_paused_color   = c["exec_color"]

        if self.theme_combo.currentText() != name:
            self.theme_combo.blockSignals(True)
            self.theme_combo.setCurrentText(name)
            self.theme_combo.blockSignals(False)

        # Propagate to terminal
        if hasattr(self, "terminal"):
            self.terminal.apply_theme(name)

    # =======================================================================
    # HELPERS
    # =======================================================================

    def _action(self, label, slot, shortcut=None, tip=""):
        a = QAction(label, self)
        a.triggered.connect(slot)
        if shortcut: a.setShortcut(shortcut)
        if tip: a.setToolTip(tip); a.setStatusTip(tip)
        return a

    def _tb_btn(self, toolbar, label, slot, tip=""):
        btn = QToolButton()
        btn.setText(label); btn.setToolTip(tip)
        btn.clicked.connect(slot)
        toolbar.addWidget(btn)
        return btn

    # =======================================================================
    # FILE TREE + SYMBOL TREE
    # =======================================================================

    def _refresh_file_tree(self, root_dir=None):
        self.file_tree.clear()
        root_dir = root_dir or (
            os.path.dirname(self.current_file) if self.current_file else IDE_DIR
        )
        root_item = QTreeWidgetItem([os.path.basename(root_dir)])
        root_item.setData(0, Qt.UserRole, root_dir)
        self.file_tree.addTopLevelItem(root_item)
        try:
            entries = sorted(os.listdir(root_dir))
        except OSError:
            return
        for entry in entries:
            full = os.path.join(root_dir, entry)
            if os.path.isdir(full) and not entry.startswith("."):
                di = QTreeWidgetItem([f"📁 {entry}"])
                di.setData(0, Qt.UserRole, full)
                root_item.addChild(di)
                try:
                    for sub in sorted(os.listdir(full)):
                        if sub.endswith(".my"):
                            sf = os.path.join(full, sub)
                            ci = QTreeWidgetItem([f"📄 {sub}"])
                            ci.setData(0, Qt.UserRole, sf)
                            di.addChild(ci)
                except OSError:
                    pass
            elif entry.endswith(".my"):
                fi = QTreeWidgetItem([f"📄 {entry}"])
                fi.setData(0, Qt.UserRole, full)
                root_item.addChild(fi)
        self.file_tree.expandAll()

    def _tree_open_file(self, item, column):
        path = item.data(0, Qt.UserRole)
        if path and os.path.isfile(path) and self._confirm_discard():
            self._open_file(path)

    def _refresh_symbol_tree(self, sym: SymbolTable):
        """Rebuild the Symbols tab from the latest SymbolTable."""
        self.symbol_tree.clear()
        c = THEME_COLORS[self.theme_name]

        # Functions section
        if sym.functions:
            fn_root = QTreeWidgetItem(["⚙ Functions", f"{len(sym.functions)}"])
            fn_root.setForeground(0, QColor(c["accent"]))
            self.symbol_tree.addTopLevelItem(fn_root)
            for name, info in sorted(sym.functions.items()):
                params = ", ".join(info["params"])
                item   = QTreeWidgetItem([f"  {name}",  f"Ln {info['line']}  ({params})"])
                item.setData(0, Qt.UserRole, info["line"])
                item.setForeground(0, QColor(c["panel_header_fg"]))
                fn_root.addChild(item)
            fn_root.setExpanded(True)

        # Variables section
        if sym.variables:
            var_root = QTreeWidgetItem(["⬡ Variables", f"{len(sym.variables)}"])
            var_root.setForeground(0, QColor(c["accent"]))
            self.symbol_tree.addTopLevelItem(var_root)
            for name, info in sorted(sym.variables.items()):
                item = QTreeWidgetItem([f"  {name}", f"Ln {info['line']}  {info['value_repr']}"])
                item.setData(0, Qt.UserRole, info["line"])
                item.setForeground(0, QColor(c["fg_dim"]))
                var_root.addChild(item)
            var_root.setExpanded(True)

        # Imports section
        if sym.imports:
            imp_root = QTreeWidgetItem(["↳ Imports", f"{len(sym.imports)}"])
            imp_root.setForeground(0, QColor(c["accent"]))
            self.symbol_tree.addTopLevelItem(imp_root)
            for imp in sym.imports:
                item = QTreeWidgetItem([f"  {imp['path']}", f"Ln {imp['line']}"])
                item.setData(0, Qt.UserRole, imp["line"])
                item.setForeground(0, QColor(c["fg_dim"]))
                imp_root.addChild(item)
            imp_root.setExpanded(True)

    def _symbol_jump(self, item, column):
        """Double-click in symbol tree → jump to definition line."""
        line = item.data(0, Qt.UserRole)
        if isinstance(line, int) and line > 0:
            self.editor.jump_to_line(line)

    def _show_symbol_tab(self):
        self.file_dock.show()
        self.project_tabs.setCurrentIndex(1)

    # =======================================================================
    # FILE OPERATIONS
    # =======================================================================

    def _new_file(self):
        if not self._confirm_discard(): return
        self.editor.setPlainText(
            "# Welcome to MyLang IDE\n"
            "# Write your program below and press F5 to run.\n\n"
        )
        self.editor.document().setModified(False)
        self.current_file = None; self.is_modified = False
        self._update_title(); self._clear_lang_panels()

    def _open_file_dialog(self):
        if not self._confirm_discard(): return
        path, _ = QFileDialog.getOpenFileName(
            self, "Open MyLang File",
            os.path.dirname(self.current_file) if self.current_file else IDE_DIR,
            "MyLang Files (*.my);;All Files (*.*)",
        )
        if path: self._open_file(path)

    def _open_file(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        except OSError as e:
            QMessageBox.critical(self, "Open Error", str(e)); return
        self.editor.setPlainText(content)
        self.editor.document().setModified(False)
        self.current_file = os.path.abspath(path)
        self.is_modified  = False
        self._update_title(); self._refresh_file_tree(); self._run_analysis()

    def _save_file(self):
        if self.current_file: self._write_file(self.current_file)
        else: self._save_file_as()

    def _save_file_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save MyLang File",
            self.current_file or os.path.join(IDE_DIR, "untitled.my"),
            "MyLang Files (*.my);;All Files (*.*)",
        )
        if path:
            self._write_file(path)
            self.current_file = os.path.abspath(path)
            self._update_title(); self._refresh_file_tree()

    def _write_file(self, path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.editor.toPlainText())
        except OSError as e:
            QMessageBox.critical(self, "Save Error", str(e)); return
        self.editor.document().setModified(False)
        self.is_modified = False
        self._update_title()
        self._console_info(f"Saved → {path}\n")

    def _confirm_discard(self):
        if not self.is_modified: return True
        btn = QMessageBox.question(
            self, "Unsaved Changes",
            "You have unsaved changes. Save before continuing?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
        )
        if btn == QMessageBox.Cancel: return False
        if btn == QMessageBox.Save:   self._save_file()
        return True

    # =======================================================================
    # LIVE ANALYSIS
    # =======================================================================

    def _on_text_changed(self):
        self.analysis_timer.start()

    def _run_analysis(self):
        self.analysis_timer.stop()
        code = self.editor.toPlainText()
        if not code.strip():
            self._clear_lang_panels()
            self._set_status_ok()
            return
        if self.analysis_worker and self.analysis_worker.isRunning():
            self.analysis_worker.quit()
        self.analysis_worker = AnalysisWorker(code)
        self.analysis_worker.signals.result.connect(self._on_analysis_done)
        self.analysis_worker.start()

    def _on_analysis_done(self, tokens, ast_nodes, err_msg, err_line, sym):
        self._symbol_table = sym
        self._last_tokens  = tokens
        self._last_ast     = ast_nodes
        self._populate_token_tree(tokens)
        self._populate_ast_tree(ast_nodes)
        self._refresh_symbol_tree(sym)

        if err_msg:
            self.highlighter.set_error_lines({err_line - 1} if err_line > 0 else set())
            self._set_status_error(err_msg, err_line)
        else:
            self.highlighter.clear_errors()
            self._set_status_ok()

    # =======================================================================
    # AUTOCOMPLETE
    # =======================================================================

    def _show_autocomplete(self, prefix: str, global_pos: QPoint):
        if not self._autocomplete_on: return
        completions = self._symbol_table.all_completions()
        has_results = self.autocomplete.populate(prefix, completions)
        if has_results:
            self.autocomplete.move(global_pos)
            self.autocomplete.show()
            self.autocomplete.setCurrentRow(0)
        else:
            self.autocomplete.hide()

    def _force_autocomplete(self):
        prefix = self.editor._word_before_cursor()
        cursor_rect = self.editor.cursorRect()
        global_pos  = self.editor.viewport().mapToGlobal(cursor_rect.bottomLeft())
        self._show_autocomplete(prefix or "", global_pos)

    def _apply_completion(self, text: str):
        """Replace the word under the cursor with the selected completion."""
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()

    def _toggle_autocomplete(self):
        self._autocomplete_on = not self._autocomplete_on
        state = "on" if self._autocomplete_on else "off"
        self.act_ac_toggle.setText(f"Toggle Autocomplete  [{state}]")

    # =======================================================================
    # FUNCTION HINTS
    # =======================================================================

    def _handle_hint_or_action(self, name: str, arg_index: int):
        """
        Receives both real hint requests and synthetic right-click actions.
        Synthetic actions are prefixed with __refs__ or __def__.
        """
        if name.startswith("__refs__"):
            self._find_references(name[8:])
            return
        if name.startswith("__def__"):
            self._go_to_definition(name[7:])
            return

        # Normal function hint
        sym  = self._symbol_table
        sig  = sym.signature(name)
        doc  = sym.hint(name)

        if name in sym.functions:
            params = sym.functions[name]["params"]
        elif name in BUILTINS:
            # Extract params from the signature string
            sig_str = BUILTINS[name][0]
            m = re.search(r'\((.+)\)', sig_str)
            params = [p.strip() for p in m.group(1).split(',')] if m and m.group(1).strip() else []
        else:
            params = []

        self.hint_bar.show_hint(sig, doc, arg_index, params)

    def _clear_hint(self):
        self.hint_bar.clear_hint()

    # =======================================================================
    # MODULE NAVIGATION  (token/AST viewers)
    # =======================================================================

    def _populate_token_tree(self, tokens):
        self.token_tree.clear()
        for tok in tokens:
            line  = str(tok.line) if tok.line is not None else "—"
            ttype = str(tok.type)
            value = str(tok.value) if tok.value is not None else ""
            item  = QTreeWidgetItem([line, ttype, value])
            item.setForeground(1, QColor(self._token_type_color(ttype)))
            self.token_tree.addTopLevelItem(item)

    def _token_type_color(self, ttype):
        c = THEME_COLORS[self.theme_name]
        if ttype in {"IF","ELSE","END","WHILE","FOR","FOREACH","FUNCTION","RETURN","IMPORT"}:
            return c["accent"]
        if ttype == "PRINT": return c["panel_header_fg"]
        if ttype in ("ASSIGN","CALL"): return c.get("fg", "#cdd6f4")
        return c.get("fg_dim", "#585b70")

    def _populate_ast_tree(self, ast_nodes):
        self.ast_tree.clear()
        for node in ast_nodes:
            item = self._build_ast_item(node)
            if item: self.ast_tree.addTopLevelItem(item)
        self.ast_tree.expandToDepth(1)

    def _build_ast_item(self, node):
        if node is None: return QTreeWidgetItem(["None", ""])
        nt   = type(node).__name__
        item = QTreeWidgetItem([nt, ""])
        item.setForeground(0, QColor(self._ast_node_color(nt)))
        for attr in [a for a in vars(node) if not a.startswith("_") and a != "line"]:
            child = self._build_attr_item(attr, getattr(node, attr, None))
            if child: item.addChild(child)
        return item

    def _build_attr_item(self, attr, val):
        if isinstance(val, list):
            item = QTreeWidgetItem([attr, f"[{len(val)} items]"])
            for i, cn in enumerate(val):
                if hasattr(cn, "__class__") and cn.__class__.__module__ == "ast_nodes":
                    item.addChild(self._build_ast_item(cn))
                else:
                    item.addChild(QTreeWidgetItem([str(i), repr(cn)]))
            return item
        if hasattr(val, "__class__") and val.__class__.__module__ == "ast_nodes":
            w = QTreeWidgetItem([attr, ""])
            w.addChild(self._build_ast_item(val))
            return w
        return QTreeWidgetItem([attr, repr(val)])

    def _ast_node_color(self, nt):
        c = THEME_COLORS[self.theme_name]
        if nt in {"IfNode","WhileNode","ForNode","ForEachNode","FunctionNode","ReturnNode","ImportNode"}:
            return c["accent"]
        if nt in {"BinaryOperationNode","LogicalOperationNode","CompareNode","UnaryOperationNode"}:
            return c["panel_header_fg"]
        if nt == "CallNode": return c.get("fg", "#cdd6f4")
        return c.get("fg_dim", "#585b70")

    # =======================================================================
    # FIND REFERENCES
    # =======================================================================

    def _find_references(self, name: str = ""):
        if not name:
            name = self.editor.word_at_cursor()
        if not name:
            QMessageBox.information(self, "Find References", "Place cursor on an identifier first.")
            return
        source  = self.editor.toPlainText()
        results = self._symbol_table.find_references(name, source)
        if not results:
            QMessageBox.information(self, "Find References", f'No references found for "{name}".')
            return
        dlg = FindReferencesDialog(self, name, results)
        dlg.exec()

    # =======================================================================
    # GO TO DEFINITION
    # =======================================================================

    def _go_to_definition(self, name: str = ""):
        if not name:
            name = self.editor.word_at_cursor()
        if not name:
            return
        line = self._symbol_table.definition_line(name)
        if line > 0:
            self.editor.jump_to_line(line)
        else:
            if name in BUILTINS:
                QMessageBox.information(self, "Go to Definition",
                    f'"{name}" is a built-in function.\n\n{BUILTINS[name][0]}\n{BUILTINS[name][1]}')
            else:
                QMessageBox.information(self, "Go to Definition",
                    f'Definition of "{name}" not found in this file.')

    # =======================================================================
    # CODE FORMATTER
    # =======================================================================

    def _format_document(self):
        source    = self.editor.toPlainText()
        formatted = self._formatter.format(source)

        if formatted == source:
            self._console_info("Format: no changes needed.\n")
            return

        # Preserve cursor position (best-effort)
        cursor  = self.editor.textCursor()
        old_line= cursor.blockNumber()

        self.editor.setPlainText(formatted)

        # Try to restore cursor line
        new_doc = self.editor.document()
        block   = new_doc.findBlockByLineNumber(min(old_line, new_doc.blockCount() - 1))
        if block.isValid():
            self.editor.setTextCursor(QTextCursor(block))

        self._console_info("Format: document formatted.\n")

    # =======================================================================
    # LANG PANEL HELPERS
    # =======================================================================

    def _toggle_lang_dock(self):
        self.lang_dock.setVisible(not self.lang_dock.isVisible())

    def _show_lang_tab(self, index):
        self.lang_dock.show(); self.lang_tabs.setCurrentIndex(index)

    def _clear_lang_panels(self):
        self.token_tree.clear(); self.ast_tree.clear()
        self.symbol_tree.clear(); self.highlighter.clear_errors()

    # =======================================================================
    # DEBUG PANEL HELPERS
    # =======================================================================

    def _toggle_debug_dock(self):
        self.debug_dock.setVisible(not self.debug_dock.isVisible())

    def _show_debug_tab(self, index):
        self.debug_dock.show(); self.debug_dock.raise_()
        self.debug_tabs.setCurrentIndex(index)

    def _populate_variable_inspector(self, variables):
        self.var_tree.clear()
        c = THEME_COLORS[self.theme_name]
        if not variables:
            self.var_tree.addTopLevelItem(QTreeWidgetItem(["(no variables)", ""]))
            return
        for name, value_repr in sorted(variables.items()):
            item = QTreeWidgetItem([name, value_repr])
            item.setForeground(0, QColor(c["accent"]))
            item.setForeground(1, QColor(c["panel_header_fg"]))
            self.var_tree.addTopLevelItem(item)

    def _populate_call_stack(self, call_stack):
        self.stack_tree.clear()
        c = THEME_COLORS[self.theme_name]
        base = QTreeWidgetItem(["<script>", "main scope"])
        base.setForeground(0, QColor(c["fg_dim"]))
        self.stack_tree.addTopLevelItem(base)
        for frame in call_stack:
            item = QTreeWidgetItem([f"⤑ {frame.get('name','?')}()", f"called at Ln {frame.get('line','?')}"])
            item.setForeground(0, QColor(c["accent"]))
            for pname, pval in frame.get("params", {}).items():
                child = QTreeWidgetItem([f"  {pname}", repr(pval)])
                child.setForeground(0, QColor(c["fg_dim"]))
                item.addChild(child)
            self.stack_tree.addTopLevelItem(item)
            item.setExpanded(True)

    def _show_exception(self, exc_type, message, line):
        c = THEME_COLORS[self.theme_name]
        self.exc_view.clear()

        def ac(text, color):
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cur = self.exc_view.textCursor()
            cur.movePosition(QTextCursor.End)
            cur.insertText(text, fmt)

        div = "─" * 60 + "\n"
        ac(div, c["border"])
        ac(f"  {exc_type}\n", c["bp_color"])
        ac(div, c["border"])
        if line > 0:
            ac(f"  Line:     {line}\n", c["fg_dim"])
            lines = self.editor.toPlainText().splitlines()
            if 0 < line <= len(lines):
                ac(f"  Source:   {lines[line-1].strip()}\n", c["panel_header_fg"])
        ac(f"\n  {message}\n", c["console_fg"])
        ac(div, c["border"])
        self._show_debug_tab(2)

    # =======================================================================
    # JUMP TO LINE
    # =======================================================================

    def _jump_to_line(self):
        dlg = JumpToLineDialog(self, self.editor.document().blockCount(),
                               self.editor.textCursor().blockNumber() + 1)
        if dlg.exec() == QDialog.Accepted:
            self.editor.jump_to_line(dlg.line_number())

    def _clear_breakpoints(self):
        self.editor.clear_all_breakpoints()

    # =======================================================================
    # NORMAL RUN
    # =======================================================================

    def _run_code(self):
        if self.worker and self.worker.isRunning(): return
        if self.current_file and self.is_modified: self._save_file()
        code = self.editor.toPlainText().strip()
        if not code: self._console_info("Nothing to run.\n"); return
        self._clear_console()
        fname = os.path.basename(self.current_file) if self.current_file else "unsaved"
        self._console_info(f"─── MyLang v{VERSION}  —  {fname} ───\n\n")
        script_dir = os.path.dirname(self.current_file) if self.current_file else IDE_DIR
        self.worker = RunWorker(code, script_dir, str(PKG_DIR))
        self.worker.signals.output.connect(self._on_worker_output)
        self.worker.signals.finished.connect(self._on_worker_done)
        self.worker.start()
        self._set_running(True, debug=False)

    # =======================================================================
    # DEBUG RUN
    # =======================================================================

    def _debug_code(self):
        if self.worker and self.worker.isRunning(): return
        if self.current_file and self.is_modified: self._save_file()
        code = self.editor.toPlainText().strip()
        if not code: self._console_info("Nothing to debug.\n"); return

        self._clear_console()
        fname = os.path.basename(self.current_file) if self.current_file else "unsaved"
        self._console_info(f"─── DEBUG  MyLang v{VERSION}  —  {fname} ───\n\n")
        if self.editor.breakpoints:
            self._console_info(f"Breakpoints at lines: {sorted(self.editor.breakpoints)}\n\n")
        else:
            self._console_info("No breakpoints — starting in step mode.\n\n")

        self.debug_dock.show(); self.debug_dock.raise_()
        self._show_debug_tab(0)
        self.var_tree.clear(); self.stack_tree.clear()
        self.exc_view.clear(); self.editor.clear_exec_line()

        debug_signals = DebugSignals()
        debug_signals.paused.connect(self._on_debug_paused)
        debug_signals.exception.connect(self._on_debug_exception)

        self.debug_controller = DebugController(self.editor.breakpoints, debug_signals)
        if not self.editor.breakpoints:
            self.debug_controller._step_mode = True

        script_dir = os.path.dirname(self.current_file) if self.current_file else IDE_DIR
        self.worker = DebugWorker(code, script_dir, self.debug_controller, str(PKG_DIR))
        self.worker.signals.output.connect(self._on_worker_output)
        self.worker.signals.finished.connect(self._on_debug_done)
        self.worker.start()
        self._set_running(True, debug=True)

    def _on_debug_paused(self, line, variables, call_stack):
        self.editor.set_exec_line(line)
        self._populate_variable_inspector(variables)
        self._populate_call_stack(call_stack)
        c = THEME_COLORS[self.theme_name]
        self.status_debug.setStyleSheet(f"color:{c['exec_color']}; font-weight:bold;")
        self.status_debug.setText(f"  ⬤ Paused  Ln {line}")
        self.btn_cont.setEnabled(True); self.btn_step.setEnabled(True)
        self.act_cont.setEnabled(True); self.act_step.setEnabled(True)

    def _on_debug_exception(self, exc_type, message, line):
        self._show_exception(exc_type, message, line)
        if line > 0:
            self.editor.set_exec_line(line)
            self.highlighter.set_error_lines({line - 1})

    def _on_debug_done(self):
        self.editor.clear_exec_line(); self.status_debug.setText("")
        self._set_running(False, debug=True)
        self._console_info("\n─── Debug session ended ───\n")

    def _dbg_continue(self):
        if self.debug_controller:
            self.editor.clear_exec_line(); self.status_debug.setText("  ⏩ Running…")
            self.btn_cont.setEnabled(False); self.btn_step.setEnabled(False)
            self.act_cont.setEnabled(False); self.act_step.setEnabled(False)
            self.debug_controller.resume()

    def _dbg_step(self):
        if self.debug_controller:
            self.editor.clear_exec_line(); self.status_debug.setText("  ⤵ Stepping…")
            self.btn_cont.setEnabled(False); self.btn_step.setEnabled(False)
            self.act_cont.setEnabled(False); self.act_step.setEnabled(False)
            self.debug_controller.step()

    def _stop_run(self):
        if self.debug_controller:
            self.debug_controller.stop(); self.debug_controller = None
        self._set_running(False, debug=self._debug_mode)
        self._console_info("\n─── Stopped ───\n")
        self.editor.clear_exec_line(); self.status_debug.setText("")

    def _set_running(self, running, debug=False):
        self._debug_mode = running and debug
        self.btn_run.setEnabled(not running); self.btn_debug.setEnabled(not running)
        self.btn_stop.setEnabled(running)
        self.act_run.setEnabled(not running); self.act_debug.setEnabled(not running)
        self.act_stop.setEnabled(running)
        if debug: self.dbg_toolbar.setVisible(running)
        else:     self.dbg_toolbar.setVisible(False)
        self.status_lang.setText(
            "  ⏵ Running…  " if (running and not debug)
            else ("  🐞 Debugging…  " if running else f"  MyLang v{VERSION}  ")
        )
        if not running:
            self.btn_cont.setEnabled(False); self.btn_step.setEnabled(False)
            self.act_cont.setEnabled(False); self.act_step.setEnabled(False)

    def _on_worker_output(self, text, tag):
        if tag == "err": self._console_error(text)
        else:            self._console_out(text)

    def _on_worker_done(self):
        self._set_running(False)
        self._console_info("\n─── Done ───\n")

    # =======================================================================
    # CONSOLE HELPERS
    # =======================================================================

    def _console_append(self, text, color):
        self.console.moveCursor(QTextCursor.End)
        fmt = QTextCharFormat(); fmt.setForeground(QColor(color))
        self.console.textCursor().insertText(text, fmt)
        self.console.moveCursor(QTextCursor.End)

    def _console_out(self, text):
        self._console_append(text, getattr(self, "_console_color_out",  "#cdd6f4"))
    def _console_error(self, text):
        self._console_append(text, getattr(self, "_console_color_err",  "#f38ba8"))
    def _console_info(self, text):
        self._console_append(text, getattr(self, "_console_color_info", "#89b4fa"))
    def _clear_console(self):
        self.console.clear()

    # =======================================================================
    # STATUS BAR
    # =======================================================================

    def _set_status_ok(self):
        clr = getattr(self, "_status_ok_color", "#89b4fa")
        self.status_errors.setStyleSheet(f"color:{clr};")
        self.status_errors.setText("  ✓ No errors")

    def _set_status_error(self, msg, line):
        clr = getattr(self, "_status_err_color", "#f38ba8")
        self.status_errors.setStyleSheet(f"color:{clr};")
        prefix = f"Ln {line}: " if line > 0 else ""
        self.status_errors.setText(f"  ✗ {prefix}{msg.split(chr(10))[0][:60]}")

    def _update_statusbar(self):
        cur = self.editor.textCursor()
        self.status_pos.setText(f"Ln {cur.blockNumber()+1}, Col {cur.columnNumber()+1}")

    def _update_title(self):
        name = os.path.basename(self.current_file) if self.current_file else "Untitled"
        dot  = " •" if self.is_modified else ""
        self.setWindowTitle(f"MyLang IDE  —  {name}{dot}")
        self.status_file.setText(f"  {self.current_file or 'Untitled'}{dot}")

    def _on_modified(self, modified):
        if modified and not self.is_modified:
            self.is_modified = True; self._update_title()
        elif not modified:
            self.is_modified = False; self._update_title()

    # =======================================================================
    # WINDOW CLOSE
    # =======================================================================

    def closeEvent(self, event):
        self.analysis_timer.stop()
        if self.debug_controller: self.debug_controller.stop()
        if self._confirm_discard(): event.accept()
        else:                       event.ignore()


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def main():
    initial_file = None
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if os.path.isfile(arg):
            initial_file = os.path.abspath(arg)
        else:
            c = os.path.join(IDE_DIR, arg)
            if os.path.isfile(c):
                initial_file = os.path.abspath(c)

    app = QApplication(sys.argv)
    app.setApplicationName("MyLang IDE")
    window = MyLangIDE(initial_file=initial_file)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
