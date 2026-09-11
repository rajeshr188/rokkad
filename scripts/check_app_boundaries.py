"""Static import guard over Git-tracked source, never virtualenvs or archives."""
import ast
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOTS = {"accounts", "apps", "django_project", "helpers", "pages", "scripts"}
RETIRED = (
    "django_tenants", "apps.tenant_apps.dea", "apps.tenant_apps.accounting",
    "apps.tenant_apps.standalone_accounting", "apps.tenant_apps.girvi",
    "apps.tenant_apps.contact", "apps.tenant_apps.product", "apps.tenant_apps.notify",
)
BILLING_INTERNALS = (
    "apps.subscriptions.models", "apps.subscriptions.billing",
    "apps.subscriptions.razorpay_service", "apps.subscriptions.checkout",
    "apps.subscriptions.recovery", "apps.subscriptions.reviews",
)
BUSINESS_APPS = {"party", "loans", "rates", "notify_v2"}


def imports(source, path):
    tree = ast.parse(source, filename=str(path))
    package = path.with_suffix("").parts[:-1]
    dynamic_names = {"__import__", "importlib.import_module"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
                if alias.name == "importlib":
                    dynamic_names.add(f"{alias.asname or alias.name}.import_module")
        elif isinstance(node, ast.ImportFrom):
            prefix = ".".join(package[:len(package) - node.level + 1]) if node.level else ""
            module = ".".join(part for part in (prefix, node.module) if part)
            yield node.lineno, module
            for alias in node.names:
                yield node.lineno, f"{module}.{alias.name}"
                if module == "importlib" and alias.name == "import_module":
                    dynamic_names.add(alias.asname or alias.name)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and ast.unparse(node.func) in dynamic_names and node.args:
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                yield node.lineno, argument.value


def violations(source, path):
    business = len(path.parts) > 2 and path.parts[:2] == ("apps", "tenant_apps") and path.parts[2] in BUSINESS_APPS
    forbidden = RETIRED + (BILLING_INTERNALS if business else ())
    return sorted(set((line, module) for line, module in imports(source, path)
                      if any(module == name or module.startswith(name + ".") for name in forbidden)))


def main():
    tracked = subprocess.check_output(["git", "ls-files", "-z", "--", "*.py"], cwd=ROOT).decode("utf-8").split("\0")
    errors, checked = [], 0
    for name in tracked:
        path = Path(name)
        if not name or (path.parts[0] not in SOURCE_ROOTS and name != "manage.py") or "migrations" in path.parts:
            continue
        absolute = ROOT / path
        if not absolute.exists():  # Pending tracked deletions are not runtime source.
            continue
        checked += 1
        try:
            errors.extend(f"{name}:{line}: forbidden import {module}" for line, module in violations(absolute.read_text(encoding="utf-8-sig"), path))
        except SyntaxError as exc:
            errors.append(f"{name}:{exc.lineno}: cannot parse Python: {exc.msg}")
    if errors:
        print("\n".join(errors))
        return 1
    print(f"Supported-app import boundaries passed for {checked} tracked Python files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
