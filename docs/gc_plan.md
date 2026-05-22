# MyLang Garbage Collection Plan

**Phase:** 7 — Advanced Runtime Features  
**Status:** Design / Planning

---

## Current Memory Model

MyLang currently relies entirely on Python's garbage collector.
Every MyLang value is a Python object — integers, strings, lists,
dicts, `MyLangObject` instances, and `MyLangNamespace` objects.
Python's reference-counting GC handles deallocation automatically.

This works correctly but has two weaknesses:

1. **Scope leaks** — when a function returns, the interpreter
   restores `old_variables` but the `MyLangObject` instances that
   were in scope remain alive in Python's heap until Python's GC
   collects them.  In long-running scripts with many object
   allocations this can cause unnecessary memory pressure.

2. **No visibility** — MyLang programs have no way to observe or
   influence memory usage.  A future `gc_stats()` built-in would
   expose allocation counts for debugging.

---

## Planned GC Strategy: Scope-Aware Reference Tracking

### Core idea

Attach a **generation counter** to every `MyLangObject`.  Each time
a new function scope is entered the interpreter increments the
generation.  When the scope exits, all objects whose generation
matches the current level and that have no references from outer
scopes are eligible for immediate deallocation.

This is a form of **stack-discipline GC** — the common case in
scripting languages where most objects die at the end of the scope
that created them.

### Implementation sketch

```python
class MyLangObject:
    def __init__(self, class_def, generation: int):
        self.class_def  = class_def
        self.properties = {}
        self.generation = generation   # scope level at creation
        self.ref_count  = 1           # explicit reference count
```

```python
class ASTInterpreter:
    def __init__(self, ...):
        ...
        self._scope_generation = 0     # increments on each function call
        self._live_objects     = []    # all MyLangObject instances

    def call_function(self, name, args, line):
        self._scope_generation += 1
        ...
        # on return:
        self._scope_generation -= 1
        self._collect(self._scope_generation + 1)

    def _collect(self, generation: int):
        """Free all objects created at `generation` with ref_count == 0."""
        self._live_objects = [
            obj for obj in self._live_objects
            if not (obj.generation == generation and obj.ref_count == 0)
        ]
```

### Object graph traversal

For objects that hold references to other objects via properties, a
simple **mark-and-sweep** pass over `_live_objects` is run when
`_collect()` is called:

1. **Mark** — walk the current variable scopes and mark every
   reachable `MyLangObject`.
2. **Sweep** — free any `MyLangObject` in `_live_objects` that was
   not marked.

This handles cycles (e.g. two objects referencing each other) that
pure reference counting cannot.

---

## `gc_stats()` Built-in (planned)

A future built-in function will expose GC metrics:

```python
stats = gc_stats()
print stats["allocated"]    # total MyLangObjects created
print stats["collected"]    # total freed by GC
print stats["live"]         # currently live objects
print stats["generation"]   # current scope depth
```

---

## Priority

Low — Python's GC is sufficient for all current use cases.
This becomes important when:

- Programs create thousands of objects in tight loops
- A bytecode VM is implemented (Phase 7 exploration)
- MyLang is used for long-running server-style scripts

---

## Timeline

| Milestone | Condition |
|:---|:---|
| Reference counting on MyLangObject | When VM is made the default executor |
| Mark-and-sweep for cycles | When object graphs become complex |
| `gc_stats()` built-in | When profiling tools are needed |
| Generational GC | If performance benchmarks justify it |
