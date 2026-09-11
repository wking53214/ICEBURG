"""Guards against the failure mode this project spent its life fighting:
documentation and dead code that outlive the decision that retired them."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
LIVE = [p for p in ROOT.rglob("*.py")
        if p.parent.name not in ("Tests",)
        and p.name not in ("QueueStress.py", "TwilioSyntheticLogGenerator.py")]


def _imports(path):
    """Imported module names. AST, not grep: a docstring explaining what was
    retired is exactly what these files SHOULD contain."""
    names = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def _string_constants(path):
    """String literals in executable positions -- docstrings excluded, since
    the prose that records a retired decision must survive."""
    tree = ast.parse(path.read_text())
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


def test_no_live_module_imports_the_superseded_aggregator():
    """QueueStress is retained for lineage only. Correction 1 retired it."""
    for p in LIVE:
        assert "QueueStress" not in _imports(p), p.name


def test_no_live_module_routes_on_a_queue_node_name():
    """Correction 1: there is no {intent}_queue node to name. The old
    stringly rule built one with an f-string."""
    for p in LIVE:
        for s in _string_constants(p):
            assert not s.endswith("_queue"), (p.name, s)


def test_staffing_engine_is_absent():
    """Deleted 2026-07-02, not demoted and not stubbed. Staffing math needs
    AHT and shrinkage -- data that does not exist before the ACD door."""
    assert not list(ROOT.rglob("staffing_rl.py"))
    assert not list(ROOT.rglob("test_staffing_rl.py"))


def test_the_twilio_generator_is_still_declared_a_stub():
    """It is preserved unimplemented on purpose. If someone implements it,
    this test should be deleted in the same commit -- not before."""
    src = (ROOT / "Domain" / "TwilioSyntheticLogGenerator.py").read_text()
    assert "SPECIFICATION STUB" in src
    assert "pass" in src
