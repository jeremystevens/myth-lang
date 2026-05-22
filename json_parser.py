"""
json_parser.py — MYTH Lang JSON Parser  (Phase 9)
==================================================
A complete recursive descent JSON parser that converts JSON text
into native MYTH Lang runtime structures.

JSON → MYTH mappings
─────────────────────
  JSON object   → dict
  JSON array    → list
  JSON string   → str
  JSON number   → int  (floats rounded to int; stored as float if fractional)
  JSON true     → True  (MYTH boolean)
  JSON false    → False (MYTH boolean)
  JSON null     → None

Public API
──────────
  parse_json(text: str) -> any
      Parse a JSON string and return the MYTH-native value.
      Raises JSONParseError on malformed input.

  JSONParseError
      Subclass of Exception.  Attributes:
        message  : str
        line     : int   (1-based)
        column   : int   (1-based)

Internals
─────────
  JSONLexer   — produces a list of Token objects from raw text
  JSONParser  — recursive descent parser over the token list
"""

# ---------------------------------------------------------------------------
# ERROR
# ---------------------------------------------------------------------------

class JSONParseError(Exception):
    """
    Raised when the JSON text is malformed.

    Attributes
    ----------
    message : str
    line    : int  — 1-based line number of the error
    column  : int  — 1-based column number of the error
    """

    def __init__(self, message: str, line: int = 0, column: int = 0):
        self.message = message
        self.line    = line
        self.column  = column
        loc = f" (line {line}, col {column})" if line else ""
        super().__init__(f"JSONParseError: {message}{loc}")

    def format(self) -> str:
        loc = f"line {self.line}, col {self.column}" if self.line else "unknown location"
        return (
            f"\n────────────────────────────────────────\n"
            f"  JSON Parse Error\n"
            f"  {loc}\n"
            f"\n"
            f"  {self.message}\n"
            f"────────────────────────────────────────\n"
        )


# ---------------------------------------------------------------------------
# TOKEN
# ---------------------------------------------------------------------------

class _Token:
    __slots__ = ("kind", "value", "line", "col")

    def __init__(self, kind: str, value, line: int, col: int):
        self.kind  = kind
        self.value = value
        self.line  = line
        self.col   = col

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, L{self.line})"


# ---------------------------------------------------------------------------
# LEXER
# ---------------------------------------------------------------------------

class _JSONLexer:
    """
    Converts raw JSON text into a flat list of _Token objects.

    Token kinds
    ───────────
      LBRACE  {         RBRACE  }
      LBRACKET [        RBRACKET ]
      COLON   :         COMMA   ,
      STRING  str       NUMBER  int|float
      BOOL    bool      NULL    None
      EOF
    """

    def __init__(self, text: str):
        self._text = text
        self._pos  = 0
        self._line = 1
        self._col  = 1

    def tokenize(self) -> list:
        tokens = []
        while self._pos < len(self._text):
            tok = self._next_token()
            if tok is not None:
                tokens.append(tok)
        tokens.append(_Token("EOF", None, self._line, self._col))
        return tokens

    def _next_token(self) -> "_Token | None":
        self._skip_whitespace()
        if self._pos >= len(self._text):
            return None

        ch   = self._text[self._pos]
        line = self._line
        col  = self._col

        # Single-character tokens
        singles = {
            "{": "LBRACE", "}": "RBRACE",
            "[": "LBRACKET", "]": "RBRACKET",
            ":": "COLON", ",": "COMMA",
        }
        if ch in singles:
            self._advance()
            return _Token(singles[ch], ch, line, col)

        # String
        if ch == '"':
            return self._read_string(line, col)

        # Number
        if ch == "-" or ch.isdigit():
            return self._read_number(line, col)

        # true / false / null
        if self._text[self._pos:self._pos+4] == "true":
            self._advance(4)
            return _Token("BOOL", True, line, col)
        if self._text[self._pos:self._pos+5] == "false":
            self._advance(5)
            return _Token("BOOL", False, line, col)
        if self._text[self._pos:self._pos+4] == "null":
            self._advance(4)
            return _Token("NULL", None, line, col)

        raise JSONParseError(
            f"Unexpected character: {ch!r}",
            line, col
        )

    def _skip_whitespace(self):
        while self._pos < len(self._text):
            ch = self._text[self._pos]
            if ch == "\n":
                self._line += 1
                self._col   = 1
                self._pos  += 1
            elif ch in " \t\r":
                self._col  += 1
                self._pos  += 1
            else:
                break

    def _advance(self, n: int = 1):
        for _ in range(n):
            if self._pos < len(self._text):
                if self._text[self._pos] == "\n":
                    self._line += 1
                    self._col   = 1
                else:
                    self._col += 1
                self._pos += 1

    def _read_string(self, line: int, col: int) -> "_Token":
        self._advance()   # opening "
        chars = []
        while self._pos < len(self._text):
            ch = self._text[self._pos]
            if ch == "\\":
                self._advance()
                if self._pos >= len(self._text):
                    raise JSONParseError("Unterminated escape sequence", self._line, self._col)
                esc = self._text[self._pos]
                escapes = {
                    '"': '"', "\\": "\\", "/": "/",
                    "b": "\b", "f": "\f", "n": "\n",
                    "r": "\r", "t": "\t",
                }
                if esc == "u":
                    # \uXXXX unicode escape
                    self._advance()
                    hex_str = self._text[self._pos:self._pos+4]
                    if len(hex_str) < 4:
                        raise JSONParseError("Invalid \\u escape", self._line, self._col)
                    try:
                        chars.append(chr(int(hex_str, 16)))
                    except ValueError:
                        raise JSONParseError(f"Invalid unicode escape: \\u{hex_str}", self._line, self._col)
                    self._advance(3)
                elif esc in escapes:
                    chars.append(escapes[esc])
                else:
                    raise JSONParseError(f"Invalid escape: \\{esc}", self._line, self._col)
            elif ch == '"':
                self._advance()   # closing "
                return _Token("STRING", "".join(chars), line, col)
            else:
                chars.append(ch)
            self._advance()

        raise JSONParseError("Unterminated string", line, col)

    def _read_number(self, line: int, col: int) -> "_Token":
        start = self._pos
        if self._pos < len(self._text) and self._text[self._pos] == "-":
            self._advance()
        while self._pos < len(self._text) and self._text[self._pos].isdigit():
            self._advance()
        is_float = False
        if self._pos < len(self._text) and self._text[self._pos] == ".":
            is_float = True
            self._advance()
            while self._pos < len(self._text) and self._text[self._pos].isdigit():
                self._advance()
        if self._pos < len(self._text) and self._text[self._pos] in "eE":
            is_float = True
            self._advance()
            if self._pos < len(self._text) and self._text[self._pos] in "+-":
                self._advance()
            while self._pos < len(self._text) and self._text[self._pos].isdigit():
                self._advance()
        raw = self._text[start:self._pos]
        try:
            value = float(raw) if is_float else int(raw)
        except ValueError:
            raise JSONParseError(f"Invalid number: {raw}", line, col)
        return _Token("NUMBER", value, line, col)


# ---------------------------------------------------------------------------
# PARSER
# ---------------------------------------------------------------------------

class _JSONParser:
    """
    Recursive descent parser over a token list produced by _JSONLexer.
    Returns native Python/MYTH values.
    """

    def __init__(self, tokens: list):
        self._tokens = tokens
        self._pos    = 0

    def parse(self):
        value = self._parse_value()
        if self._peek().kind != "EOF":
            tok = self._peek()
            raise JSONParseError(
                f"Unexpected token after value: {tok.value!r}",
                tok.line, tok.col
            )
        return value

    # ── Value dispatch ────────────────────────────────────────────────────

    def _parse_value(self):
        tok = self._peek()

        if tok.kind == "LBRACE":
            return self._parse_object()
        if tok.kind == "LBRACKET":
            return self._parse_array()
        if tok.kind == "STRING":
            self._advance()
            return tok.value
        if tok.kind == "NUMBER":
            self._advance()
            # Whole floats → int in MYTH; fractional → float
            if isinstance(tok.value, float) and tok.value == int(tok.value):
                return int(tok.value)
            return tok.value
        if tok.kind == "BOOL":
            self._advance()
            return tok.value
        if tok.kind == "NULL":
            self._advance()
            return None

        raise JSONParseError(
            f"Unexpected token: {tok.value!r}",
            tok.line, tok.col
        )

    # ── Object ────────────────────────────────────────────────────────────

    def _parse_object(self) -> dict:
        self._expect("LBRACE")
        result = {}

        if self._peek().kind == "RBRACE":
            self._advance()
            return result

        while True:
            # key
            key_tok = self._peek()
            if key_tok.kind != "STRING":
                raise JSONParseError(
                    f"Object key must be a string, got {key_tok.value!r}",
                    key_tok.line, key_tok.col
                )
            self._advance()
            key = key_tok.value

            # colon
            self._expect("COLON")

            # value
            value = self._parse_value()
            result[key] = value

            nxt = self._peek()
            if nxt.kind == "RBRACE":
                self._advance()
                break
            if nxt.kind == "COMMA":
                self._advance()
                # Trailing comma check
                if self._peek().kind == "RBRACE":
                    raise JSONParseError(
                        "Trailing comma in object",
                        nxt.line, nxt.col
                    )
                continue
            raise JSONParseError(
                f"Expected ',' or '}}', got {nxt.value!r}",
                nxt.line, nxt.col
            )

        return result

    # ── Array ─────────────────────────────────────────────────────────────

    def _parse_array(self) -> list:
        self._expect("LBRACKET")
        result = []

        if self._peek().kind == "RBRACKET":
            self._advance()
            return result

        while True:
            result.append(self._parse_value())

            nxt = self._peek()
            if nxt.kind == "RBRACKET":
                self._advance()
                break
            if nxt.kind == "COMMA":
                self._advance()
                # Trailing comma check
                if self._peek().kind == "RBRACKET":
                    raise JSONParseError(
                        "Trailing comma in array",
                        nxt.line, nxt.col
                    )
                continue
            raise JSONParseError(
                f"Expected ',' or ']', got {nxt.value!r}",
                nxt.line, nxt.col
            )

        return result

    # ── Helpers ───────────────────────────────────────────────────────────

    def _peek(self) -> "_Token":
        return self._tokens[self._pos]

    def _advance(self) -> "_Token":
        tok = self._tokens[self._pos]
        if tok.kind != "EOF":
            self._pos += 1
        return tok

    def _expect(self, kind: str) -> "_Token":
        tok = self._peek()
        if tok.kind != kind:
            raise JSONParseError(
                f"Expected {kind!r}, got {tok.kind!r} ({tok.value!r})",
                tok.line, tok.col
            )
        self._advance()
        return tok


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def parse_json(text: str):
    """
    Parse a JSON string and return the equivalent MYTH runtime value.

    JSON → MYTH mappings:
      object  → dict
      array   → list
      string  → str
      number  → int (whole) or float (fractional)
      true    → True
      false   → False
      null    → None

    Raises JSONParseError on malformed input.
    """
    if not isinstance(text, str):
        raise JSONParseError(f"parse_json() expects a string, got {type(text).__name__}")

    text = text.strip()
    if not text:
        raise JSONParseError("parse_json() received empty string")

    tokens = _JSONLexer(text).tokenize()
    return _JSONParser(tokens).parse()
