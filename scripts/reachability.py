"""Print modules under belem_converse/ and api/ that no entry point imports."""
import ast
from pathlib import Path

ENTRY = ["api.main", "belem_converse.tools.build_catalog",
         "belem_converse.tools.validate_osm", "belem_converse.tools.bench_llm"]


def mod_path(name):
    p = Path(*name.split("."))
    return p.with_suffix(".py") if p.with_suffix(".py").exists() else p / "__init__.py"


def imports(name):
    path = mod_path(name)
    if not path.exists():
        return
    pkg = name if path.name == "__init__.py" else name.rpartition(".")[0]
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = pkg.split(".")[: len(pkg.split(".")) - node.level + 1]
                base = ".".join(parts + ([node.module] if node.module else []))
            yield base
            for a in node.names:  # `from pkg import submodule`
                yield f"{base}.{a.name}"


seen, todo = set(), list(ENTRY)
while todo:
    m = todo.pop()
    if m in seen or not mod_path(m).exists():
        continue
    seen.add(m)
    # importing a.b.c also runs a/__init__ and a.b/__init__
    todo += [".".join(m.split(".")[:i]) for i in range(1, len(m.split(".")))]
    todo += list(imports(m))

for f in sorted(Path(".").glob("*/**/*.py")):
    if f.parts[0] in ("belem_converse", "api") and f.name != "__init__.py":
        mod = ".".join(f.with_suffix("").parts)
        if mod not in seen:
            print("unreachable:", mod)
