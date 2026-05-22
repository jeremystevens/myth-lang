"""
json_serializer.py — MYTH Lang JSON Serializer  (Phase 9)
==========================================================
Converts native MYTH Lang runtime values into JSON text.

MYTH → JSON mappings
─────────────────────
  dict          → JSON object
  list          → JSON array
  str           → JSON string  (with proper escaping)
  int           → JSON number
  float         → JSON number
  True          → true
  False         → false
  None          → null
  MyLangObject  → JSON object  (properties dict serialized)

Public API
──────────
  to_json(value, pretty: bool = False) -> str
      Serialize a MYTH value to a JSON string.
      pretty=True adds 2-space indentation and newlines.
      Raises SerializationError on unsupported types or cycles.

  SerializationError
      Subclass of Exception.  Attributes:
        message : str
"""

from ast_interpreter import MyLangObject, MyLangNamespace


# ---------------------------------------------------------------------------
# ERROR
# ---------------------------------------------------------------------------

class SerializationError(Exception):
    """
    Raised when a value cannot be serialized to JSON.

    Attributes
    ----------
    message : str
    """

    def __init__(self, message: str):
        self.message = message
        super().__init__(f"SerializationError: {message}")

    def format(self) -> str:
        return (
            f"\n────────────────────────────────────────\n"
            f"  Serialization Error\n"
            f"\n"
            f"  {self.message}\n"
            f"────────────────────────────────────────\n"
        )


# ---------------------------------------------------------------------------
# INTERNAL SERIALIZER
# ---------------------------------------------------------------------------

_ESCAPE_MAP = {
    '"':  '\\"',
    "\\": "\\\\",
    "\b": "\\b",
    "\f": "\\f",
    "\n": "\\n",
    "\r": "\\r",
    "\t": "\\t",
}


def _escape_string(s: str) -> str:
    """Escape a Python string for JSON output."""
    result = []
    for ch in s:
        if ch in _ESCAPE_MAP:
            result.append(_ESCAPE_MAP[ch])
        elif ord(ch) < 0x20:
            # Control characters → \uXXXX
            result.append(f"\\u{ord(ch):04x}")
        else:
            result.append(ch)
    return "".join(result)


class _Serializer:
    """
    Internal serializer that tracks seen object ids to detect
    circular references.
    """

    def __init__(self, pretty: bool = False, indent: int = 2):
        self.pretty = pretty
        self.indent = indent
        self._seen  : set = set()

    def serialize(self, value, depth: int = 0) -> str:
        """Recursively serialize a value."""

        # ── None → null ───────────────────────────────────────────────
        if value is None:
            return "null"

        # ── bool must come before int (bool is a subclass of int) ─────
        if isinstance(value, bool):
            return "true" if value else "false"

        # ── int / float ───────────────────────────────────────────────
        if isinstance(value, int):
            return str(value)

        if isinstance(value, float):
            # Represent whole floats without decimal for cleanliness
            if value == int(value) and not (value == float("inf")):
                return str(int(value))
            return repr(value)

        # ── str ───────────────────────────────────────────────────────
        if isinstance(value, str):
            return f'"{_escape_string(value)}"'

        # ── list ──────────────────────────────────────────────────────
        if isinstance(value, list):
            obj_id = id(value)
            if obj_id in self._seen:
                raise SerializationError(
                    "Circular reference detected in list"
                )
            self._seen.add(obj_id)
            try:
                result = self._serialize_list(value, depth)
            finally:
                self._seen.discard(obj_id)
            return result

        # ── dict ──────────────────────────────────────────────────────
        if isinstance(value, dict):
            obj_id = id(value)
            if obj_id in self._seen:
                raise SerializationError(
                    "Circular reference detected in dictionary"
                )
            self._seen.add(obj_id)
            try:
                result = self._serialize_dict(value, depth)
            finally:
                self._seen.discard(obj_id)
            return result

        # ── MyLangObject → serialize as its properties dict ───────────
        if isinstance(value, MyLangObject):
            obj_id = id(value)
            if obj_id in self._seen:
                raise SerializationError(
                    f"Circular reference detected in object "
                    f"of class '{value.class_def.name}'"
                )
            self._seen.add(obj_id)
            try:
                # Build a dict with class name + all properties
                data = {"__class__": value.class_def.name}
                data.update(value.properties)
                result = self._serialize_dict(data, depth)
            finally:
                self._seen.discard(obj_id)
            return result

        # ── MyLangNamespace — not serializable ────────────────────────
        if isinstance(value, MyLangNamespace):
            raise SerializationError(
                f"Cannot serialize module namespace '{value.name}'. "
                f"Namespaces are not JSON-serializable."
            )

        raise SerializationError(
            f"Cannot serialize value of type "
            f"'{type(value).__name__}': {value!r}"
        )

    # ── List serialization ────────────────────────────────────────────────

    def _serialize_list(self, lst: list, depth: int) -> str:
        if not lst:
            return "[]"

        if self.pretty:
            pad_inner = " " * (self.indent * (depth + 1))
            pad_close = " " * (self.indent * depth)
            items = [
                f"{pad_inner}{self.serialize(v, depth + 1)}"
                for v in lst
            ]
            return "[\n" + ",\n".join(items) + f"\n{pad_close}]"
        else:
            items = [self.serialize(v, depth + 1) for v in lst]
            return "[" + ", ".join(items) + "]"

    # ── Dict serialization ────────────────────────────────────────────────

    def _serialize_dict(self, d: dict, depth: int) -> str:
        if not d:
            return "{}"

        pairs = []
        for key, val in d.items():
            if not isinstance(key, str):
                raise SerializationError(
                    f"Dictionary keys must be strings for JSON "
                    f"serialization, got {type(key).__name__}: {key!r}"
                )
            serialized_key = f'"{_escape_string(key)}"'
            serialized_val = self.serialize(val, depth + 1)
            pairs.append((serialized_key, serialized_val))

        if self.pretty:
            pad_inner = " " * (self.indent * (depth + 1))
            pad_close = " " * (self.indent * depth)
            entries = [
                f"{pad_inner}{k}: {v}"
                for k, v in pairs
            ]
            return "{\n" + ",\n".join(entries) + f"\n{pad_close}}}"
        else:
            entries = [f"{k}: {v}" for k, v in pairs]
            return "{" + ", ".join(entries) + "}"


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def to_json(value, pretty: bool = False) -> str:
    """
    Serialize a MYTH runtime value to a JSON string.

    Parameters
    ----------
    value  : any   — the MYTH value to serialize
    pretty : bool  — if True, output is indented with 2 spaces

    Returns
    -------
    str  — valid JSON text

    Raises
    ------
    SerializationError  — if value contains unsupported types or
                          circular references
    """
    serializer = _Serializer(pretty=bool(pretty))
    return serializer.serialize(value)
