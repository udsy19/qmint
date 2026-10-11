"""Lane M helper: what an in-process adversary can reach from an object it was handed.

Follows instance attributes and containers only (never types, modules or functions), i.e. the
object graph a caller can walk with ``vars()``/attribute access without importing anything.
"""

from __future__ import annotations

import types
from typing import Any

_SKIP = (type, types.ModuleType, types.FunctionType, types.BuiltinFunctionType, types.MethodType)


def reachable(root: Any, limit: int = 200_000) -> list[Any]:
    seen: set[int] = set()
    out: list[Any] = []
    stack = [root]
    while stack and len(out) < limit:
        o = stack.pop()
        if id(o) in seen or isinstance(o, _SKIP):
            continue
        seen.add(id(o))
        out.append(o)
        if isinstance(o, dict):
            stack.extend(o.keys())
            stack.extend(o.values())
        elif isinstance(o, (list, tuple, set, frozenset)):
            stack.extend(o)
        else:
            d = getattr(o, "__dict__", None)
            if isinstance(d, dict):
                stack.extend(d.values())
            for slot in getattr(type(o), "__slots__", ()):
                if hasattr(o, slot):
                    stack.append(getattr(o, slot))
    return out


def reachable_types(root: Any) -> set[str]:
    return {type(o).__name__ for o in reachable(root)}
