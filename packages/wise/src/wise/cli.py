"""Entry point for the `wise` command. Replaces upstream scripts/wise."""
from __future__ import annotations

import re
import sys

from wise import actions


def _discover_tasks() -> dict[str, object]:
    return {
        m[len("wise_") :]: getattr(actions, m)
        for m in dir(actions)
        if re.fullmatch(r"wise_[\w_]+", m)
    }


def _usage(tasks: dict[str, object]) -> str:
    pad = max(len(t) for t in tasks) + 4
    lines = [
        f"  {t:<{pad}}{getattr(mod, 'USAGE', '').splitlines()[0]}"
        for t, mod in tasks.items()
    ]
    return "Usage: wise TASK [OPTIONS]\n\nAvailable tasks:\n" + "\n".join(lines)


def main() -> int:
    tasks = _discover_tasks()
    if len(sys.argv) < 2 or sys.argv[1] in {"-h", "--help"}:
        print(_usage(tasks))
        return 0 if len(sys.argv) >= 2 else 1
    name = sys.argv[1]
    if name not in tasks:
        print(f"Error: No task named {name!r}\n\n{_usage(tasks)}", file=sys.stderr)
        return 1
    sys.argv = sys.argv[1:]
    return tasks[name].main() or 0


if __name__ == "__main__":
    raise SystemExit(main())
