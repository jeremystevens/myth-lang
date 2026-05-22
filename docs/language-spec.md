# MyLang Language Specification

**Version:** 0.8.0  
**Runtime:** AST-based interpreter  
**File extension:** `.my`

---

## Table of Contents

1. [Overview](#overview)
2. [Lexical Structure](#lexical-structure)
3. [Data Types](#data-types)
4. [Variables](#variables)
5. [Operators](#operators)
6. [Control Flow](#control-flow)
7. [Functions](#functions)
8. [Collections](#collections)
9. [Module System](#module-system)
10. [File I/O](#file-io)
11. [Built-in Functions](#built-in-functions)
12. [Error System](#error-system)
13. [Known Limitations](#known-limitations)

---

## Overview

MyLang is a dynamically typed, interpreted scripting language with a clean line-based syntax inspired by QBASIC. Programs are processed through a four-stage pipeline:

```
Source (.my)  →  Lexer (tokens)  →  Parser (AST)  →  Interpreter (output)
```

Every statement occupies its own line. There is no statement terminator (no semicolons). Blocks are closed with `end`.

---

## Lexical Structure

### Comments

Lines beginning with `#` are comments and are ignored entirely by the lexer.

```
# This is a comment
x = 10  # inline comments are not supported — the whole line must be a comment
```

### Token Types

The lexer produces the following token types:

| Token | Triggered by |
|:---|:---|
| `PRINT` | Lines beginning with `print ` |
| `ASSIGN` | Lines containing `=` (that are not other keywords) |
| `IF` | Lines beginning with `if ` |
| `ELSE` | The literal line `else` |
| `END` | The literal line `end` |
| `WHILE` | Lines beginning with `while ` |
| `FOR` | Lines beginning with `for ` |
| `FOREACH` | Lines beginning with `foreach ` |
| `FUNCTION` | Lines beginning with `function ` |
| `RETURN` | Lines beginning with `return ` |
| `CALL` | Lines matching `name(args)` not otherwise matched |
| `IMPORT` | Lines beginning with `import ` |

### String Escape Sequences

The following escape sequences are processed inside double-quoted string literals:

| Sequence | Result |
|:---|:---|
| `\n` | Newline character |
| `\t` | Tab character |
| `\\` | Literal backslash |

```
write_file("log.txt", "Line one\nLine two\n")
```

---

## Data Types

MyLang is dynamically typed. The following types exist at runtime:

| Type | Example | `type_of()` returns |
|:---|:---|:---|
| Integer | `42`, `-7`, `0` | `"INTEGER"` |
| String | `"hello"` | `"STRING"` |
| Boolean | `true`, `false` | `"BOOLEAN"` |
| List | `[1, 2, 3]` | `"LIST"` |
| Dictionary | `{"key": value}` | `"DICTIONARY"` |

> **Note:** Float/decimal numbers are not yet supported. Division that produces a float is automatically truncated. `>=` and `<=` comparison operators are not yet supported.

---

## Variables

Assignment uses `=`. Variable names are identifiers (letters, digits, underscores — must start with a letter or underscore).

```
name  = "Alice"
score = 100
alive = true
data  = [1, 2, 3]
```

Variables are scoped to the current execution context. Functions receive a copy of the caller's variable scope and restore it on return — they do not share mutable state with the caller.

### Index Assignment

List and dictionary elements can be updated by index:

```
scores = [10, 20, 30]
scores[1] = 99
print scores   # [10, 99, 30]

player = {"hp": 100}
player["hp"] = 75
print player   # {'hp': 75}
```

---

## Operators

### Arithmetic

| Operator | Operation | Example |
|:---:|:---|:---|
| `+` | Addition / string concat | `x + y`, `"hi" + name` |
| `-` | Subtraction | `x - y` |
| `*` | Multiplication | `x * y` |
| `/` | Division (integer result) | `x / y` |
| `%` | Modulo | `x % y` |

### Comparison

| Operator | Operation |
|:---:|:---|
| `==` | Equal to |
| `>` | Greater than |
| `<` | Less than |

> `>=` and `<=` are not yet implemented.

### Logical

| Operator | Operation |
|:---:|:---|
| `and` | Logical AND |
| `or` | Logical OR |
| `not` | Logical NOT (unary) |

### Operator Precedence (low → high)

```
or  →  and  →  not  →  ==, >, <  →  +, -  →  *, /, %
```

### Negative Number Literals

Negative integer literals are supported directly:

```
x = -42
y = abs(-99)
z = clamp(-5, 0, 100)
```

---

## Control Flow

### If / Else

```
if condition
    # true branch
end

if condition
    # true branch
else
    # false branch
end
```

> `elif` is not yet supported. Nest `if / else / end` blocks for multiple branches.

### While Loop

```
while condition
    # body
end
```

### For Loop

Iterates an integer range from `start` to `end` inclusive:

```
for i = 1 to 10
    print i
end
```

### Foreach Loop

Iterates every element of a list:

```
names = ["Alice", "Bob", "Charlie"]

foreach name in names
    print name
end
```

> `break` and `continue` are not yet supported.

---

## Functions

### Definition

```
function name param1 param2
    # body
    return value
end
```

- Parameters are positional
- Return value is optional — functions without `return` return `None`
- Functions are stored in a shared global function registry — they are visible everywhere after definition, regardless of where in the file they appear

### Calling

```
result = add(10, 20)
```

Function calls can appear in expressions, assignments, `print` statements, and as standalone statements.

### Doc Comments

A `#` comment on the line immediately before a `function` keyword is treated as its documentation comment by the IDE's symbol system:

```
# Greet a player by name and return their new level
function greet name level
    print "Hello, " + name
    return level + 1
end
```

---

## Collections

### Lists

```
scores = [1, 2, 3, 4, 5]
mixed  = [1, "hello", true]
empty  = []
```

Access by 0-based index:

```
print scores[0]   # 1
print scores[4]   # 5
```

Index assignment:

```
scores[2] = 99
```

### Dictionaries

```
player = {
    "name": "Knight",
    "hp":   100,
    "mana": 50
}
```

Access by string key:

```
print player["hp"]   # 100
```

Key assignment:

```
player["hp"] = 75
```

---

## Module System

### Importing

```
import modulename
import path/to/module
```

- The `.my` extension is added automatically if omitted
- Modules are searched in the script's directory first, then any additional search paths (e.g. `~/.mylang/packages/`)
- A module is executed exactly once per interpreter session — repeated imports are silently no-ops (import caching)
- Functions defined in a module become globally available to the importing script
- Top-level variable assignments in a module do not pollute the importer's variable scope
- Circular imports are safe — the cache prevents infinite recursion

### Example

```
# utils.my
function double n
    return n + n
end

# main.my
import utils

print double(21)   # 42
```

---

## File I/O

All file paths are relative to the directory of the running `.my` script. Paths that attempt to escape the script directory (e.g. `../../etc/passwd`) are blocked at runtime with a descriptive error.

See **Built-in Functions → File I/O** for the complete API.

---

## Built-in Functions

All built-in functions are available globally — no import required.

### String (11 functions)

| Function | Signature | Description |
|:---|:---|:---|
| `upper` | `upper(s)` | Convert to uppercase |
| `lower` | `lower(s)` | Convert to lowercase |
| `length` | `length(s)` | Length of string, list, or dict |
| `trim` | `trim(s)` | Strip leading/trailing whitespace |
| `replace` | `replace(s, old, new)` | Replace all occurrences of `old` with `new` |
| `split` | `split(s, delim)` | Split string into a list on delimiter |
| `contains` | `contains(s, sub)` | True if `sub` is in `s` |
| `starts_with` | `starts_with(s, pre)` | True if `s` starts with `pre` |
| `ends_with` | `ends_with(s, suf)` | True if `s` ends with `suf` |
| `repeat_str` | `repeat_str(s, n)` | Repeat string `n` times |
| `reverse` | `reverse(s)` | Reverse a string (use `reverse_list()` for lists) |

### Math (9 functions)

| Function | Signature | Description |
|:---|:---|:---|
| `abs` | `abs(n)` | Absolute value |
| `max` | `max(a, b)` | Larger of two numbers |
| `min` | `min(a, b)` | Smaller of two numbers |
| `pow` | `pow(base, exp)` | Raise to a power (integer result) |
| `sqrt` | `sqrt(n)` | Integer square root |
| `floor` | `floor(n)` | Round down to integer |
| `ceil` | `ceil(n)` | Round up to integer |
| `clamp` | `clamp(val, lo, hi)` | Constrain value to range `[lo, hi]` |
| `random` | `random(a, b)` | Random integer between `a` and `b` inclusive |

### List (10 functions)

| Function | Signature | Description |
|:---|:---|:---|
| `append` | `append(list, item)` | Add item to end of list, return list |
| `remove` | `remove(list, item)` | Remove first occurrence, return list |
| `first` | `first(list)` | Return first element |
| `last` | `last(list)` | Return last element |
| `sort` | `sort(list)` | Return sorted copy of list |
| `reverse_list` | `reverse_list(list)` | Return reversed copy of list |
| `slice` | `slice(list, start, end)` | Return sub-list from `start` (inclusive) to `end` (exclusive) |
| `contains_item` | `contains_item(list, val)` | True if `val` is in list |
| `index_of` | `index_of(list, val)` | Index of `val`, or `-1` if not found |
| `flatten` | `flatten(list)` | Collapse one level of nesting |

### Dictionary (6 functions)

| Function | Signature | Description |
|:---|:---|:---|
| `keys` | `keys(dict)` | Return list of all keys |
| `values` | `values(dict)` | Return list of all values |
| `exists` | `exists(dict, key)` | True if `key` exists in dict |
| `get` | `get(dict, key, default)` | Return value or `default` if key missing |
| `delete` | `delete(dict, key)` | Remove key, return updated dict |
| `merge` | `merge(a, b)` | Combine two dicts — `b` wins on key conflict |

### Type Conversion (4 functions)

| Function | Signature | Description |
|:---|:---|:---|
| `to_int` | `to_int(v)` | Convert string or bool to integer |
| `to_str` | `to_str(v)` | Convert any value to string |
| `to_bool` | `to_bool(v)` | Convert `0/1/"true"/"false"/"yes"/"no"` to boolean |
| `type_of` | `type_of(v)` | Return `"INTEGER"`, `"STRING"`, `"LIST"`, `"DICTIONARY"`, or `"BOOLEAN"` |

### I/O (1 function)

| Function | Signature | Description |
|:---|:---|:---|
| `input` | `input()` or `input(prompt)` | Read a line from stdin. Optional prompt is printed first. Returns a string. |

### File I/O (5 functions)

| Function | Signature | Description |
|:---|:---|:---|
| `read_file` | `read_file(path)` | Read entire file, return as string. Error if file not found. |
| `write_file` | `write_file(path, content)` | Write string to file. Creates or overwrites. Creates intermediate directories. Returns bytes written. |
| `append_file` | `append_file(path, content)` | Append string to file. Creates if missing. Returns bytes written. |
| `file_exists` | `file_exists(path)` | True if file exists. Never raises — safe on any string. |
| `delete_file` | `delete_file(path)` | Delete the file. Error if not found. |

---

## Error System

As of v0.8.0, MyLang produces structured, multi-line tracebacks for both syntax and runtime errors.

### Runtime Errors

A runtime error shows the full call stack from outermost to innermost function, the source code line at each frame, the local variables in scope at each frame, and the error type and message.

```
────────────────────────────────────────────────────────────
  MyLang Traceback (most recent call last)
────────────────────────────────────────────────────────────

  ┌────────────────────────────────────────────────────────┐
  │    In function  level_one()                            │
  │    line 14                                             │
  │    ▶  return level_two(n * 2)                         │
  │  Variables:                                            │
  │      n = 5                                             │
  └────────────────────────────────────────────────────────┘

────────────────────────────────────────────────────────────
  Line 7: RuntimeError: Undefined function: bad_fn
────────────────────────────────────────────────────────────
```

### Syntax Errors

Syntax errors show the offending line with a `^` caret pointing to the error position:

```
────────────────────────────────────────────────────────────
  MyLang SyntaxError
────────────────────────────────────────────────────────────

  Line 12: Unknown syntax: call greet Alice

    call greet Alice
    ^

────────────────────────────────────────────────────────────
```

### Module Import Errors

Errors inside imported modules show the full import chain that led to the file:

```
  Import chain:
    import 'utils'  at line 3
    import 'helpers'  at line 1
```

---

## Known Limitations

The following features are planned but not yet implemented:

| Feature | Status |
|:---|:---|
| `>=` and `<=` comparisons | Planned |
| `elif` chains | Planned |
| `break` / `continue` in loops | Planned |
| Float / decimal numbers | Planned |
| String indexing | Planned |
| Error handling (`try / catch`) | Planned |
| `repeat N` loop | Removed — use `for i = 1 to N` |
| Inline comments | Not supported |


---

## Classes and Objects

*Added in v0.9.0*

### Class Definition

```
class ClassName
    init param1 param2
        this.param1 = param1
        this.param2 = param2
    end

    method method_name arg1
        this.x = this.x + arg1
    end

    method no_args()
        return this.x
    end
end
```

- `class` opens the definition, `end` closes it
- `init` defines the constructor — its parameters are the arguments passed when creating an instance
- `method` defines an instance method — zero-parameter methods can write `method name()` with the `()` stripped automatically
- `this` is bound to the current instance inside every `init` and `method` body
- Properties are created by assigning to `this.name` — there is no declaration syntax

### Instantiation

```
p = Player("Jeremy", 100)
```

Calling a class name like a function creates a new instance, runs the `init` body with `this` bound to that instance, and returns the object.

### Property Access

```
print p.name
print p.hp
```

### Property Assignment (from outside)

```
p.hp = 50
```

### Method Calls

```
p.take_damage(30)
status = p.get_status()
```

Standalone method calls (`p.take_damage(30)` as a statement) and method calls in expressions (`result = p.get_status()`) both work.

### `this` Reference

Inside `init` and `method` bodies, `this` refers to the current instance. Properties are read and written through `this`:

```
method heal amount
    this.hp = this.hp + amount
end
```

### `type_of()` with Objects

```
print type_of(p)   # → "Player"
```

`type_of()` returns the class name for object instances.

### Objects in Collections

Objects can be stored in lists and dictionaries like any other value:

```
party = [Player("Alice", 80), Player("Bob", 100)]
first_player = first(party)
print first_player.name
```

### Full Example

```
class Player
    init name hp
        this.name = name
        this.hp   = hp
        this.alive = true
    end

    method take_damage amount
        this.hp = this.hp - amount
        if this.hp < 1 then
            this.alive = false
        end
    end

    method heal amount
        this.hp = this.hp + amount
    end

    method get_status()
        return this.name + " HP:" + to_str(this.hp)
    end

    method is_alive()
        return this.alive
    end
end

p = Player("Jeremy", 100)

print p.name          # Jeremy
print p.hp            # 100
p.take_damage(30)
print p.hp            # 70
print p.get_status()  # Jeremy HP:70
print p.is_alive()    # True
print type_of(p)      # Player
```

---

## Boolean Literals

*Clarified in v0.9.0*

`true` and `false` are language keywords that produce boolean values:

```
alive = true
dead  = false

if alive then
    print "Still going"
end
```

They can be used in any expression context, stored in variables, and returned from functions.

---

## Updated Known Limitations

| Feature | Status |
|:---|:---|
| `>=` and `<=` comparisons | Planned |
| `elif` chains | Planned |
| `break` / `continue` in loops | Planned |
| Float / decimal numbers | Planned |
| String indexing | Planned |
| Error handling (`try / catch`) | Planned |
| Class inheritance | Planned |
| `!=` inequality operator | Planned |
| Inline comments | Not supported |
