"""No-code calculators: a JSON spec with inputs, formulas, outputs, checks and
an optional chart, evaluated with a restricted expression evaluator (maths
only, no attribute access, no calls except the whitelisted functions). This is
how colleagues share live tools without deploying code.

Spec shape:
{
  "inputs":   [{"name": "L", "label": "Span", "unit": "m", "default": 6, "min": 1, "max": 20, "param": "beam_span"}],
  "formulas": [{"name": "M", "expr": "w*L**2/8"}, {"name": "V", "expr": "w*L/2"}],
  "outputs":  [{"name": "M", "label": "Max moment", "unit": "kNm", "decimals": 1}],
  "checks":   [{"label": "M ≤ 100 kNm", "expr": "M <= 100"}],
  "chart":    {"x": "x", "range": [0, "L", 40], "series": [{"label": "M(x)", "expr": "w*x*(L-x)/2"}], "xlabel": "x (m)", "ylabel": "kNm"}
}
"""

import ast
import math

from .engines import Input, _svg_chart

SAFE_FUNCS = {k: getattr(math, k) for k in ("sqrt", "sin", "cos", "tan", "asin", "acos", "atan", "atan2", "exp", "log", "log10", "fabs", "floor", "ceil", "hypot", "radians", "degrees")}
SAFE_FUNCS.update({"abs": abs, "min": min, "max": max, "round": round, "pi": math.pi, "e": math.e})
ALLOWED = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant, ast.Name, ast.Load, ast.Call, ast.Compare, ast.BoolOp, ast.IfExp, ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.USub, ast.UAdd, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq, ast.And, ast.Or, ast.Not)


class SpecError(ValueError):
    pass


def safe_eval(expr: str, names: dict):
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise SpecError(f"Syntax error in '{expr}': {e}") from e
    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED):
            raise SpecError(f"Not allowed in formulas: {type(node).__name__} in '{expr}'")
        if isinstance(node, ast.Call) and (not isinstance(node.func, ast.Name) or node.func.id not in SAFE_FUNCS):
            raise SpecError(f"Only maths functions may be called in '{expr}'")
        if isinstance(node, ast.Name) and node.id not in names and node.id not in SAFE_FUNCS:
            raise SpecError(f"Unknown name '{node.id}' in '{expr}'")
    env = dict(SAFE_FUNCS)
    env.update(names)
    return eval(compile(tree, "<spec>", "eval"), {"__builtins__": {}}, env)


def validate_spec(spec: dict):
    if not isinstance(spec, dict):
        raise SpecError("Spec must be a JSON object.")
    inputs = spec.get("inputs") or []
    if not inputs:
        raise SpecError("At least one input is required.")
    names = {}
    for i in inputs:
        if not i.get("name") or not i["name"].isidentifier():
            raise SpecError(f"Bad input name: {i.get('name')!r}")
        names[i["name"]] = float(i.get("default", 0))
    for f in spec.get("formulas") or []:
        if not f.get("name") or not f["name"].isidentifier():
            raise SpecError(f"Bad formula name: {f.get('name')!r}")
        names[f["name"]] = safe_eval(f["expr"], names)
    for c in spec.get("checks") or []:
        safe_eval(c["expr"], names)
    chart = spec.get("chart")
    if chart:
        xname = chart.get("x", "x")
        names2 = dict(names)
        names2[xname] = 1.0
        for s_ in chart.get("series") or []:
            safe_eval(s_["expr"], names2)
    return True


class SpecEngine:
    """Adapts a spec to the same interface as the built-in engines."""

    def __init__(self, tool):
        self.tool = tool
        self.spec = tool.spec
        self.key, self.name, self.category, self.summary, self.description = tool.key, tool.name, tool.category, tool.summary, tool.description
        self.inputs = [Input(i["name"], i.get("label", i["name"]), i.get("unit", ""), float(i.get("default", 0)), i.get("help", ""), step=float(i.get("step", 0.1)), param=i.get("param", ""), min=i.get("min"), max=i.get("max")) for i in self.spec.get("inputs", [])]

    def run(self, values):
        names = {i.name: float(values.get(i.name, i.default)) for i in self.inputs}
        for f in self.spec.get("formulas") or []:
            names[f["name"]] = safe_eval(f["expr"], names)
        results = []
        for o in self.spec.get("outputs") or []:
            v = names.get(o["name"])
            d = int(o.get("decimals", 2))
            results.append((o.get("label", o["name"]), f"{v:,.{d}f}" if isinstance(v, (int, float)) else str(v), o.get("unit", "")))
        checks = [(c.get("label", c["expr"]), bool(safe_eval(c["expr"], names))) for c in self.spec.get("checks") or []]
        chart = ""
        ch = self.spec.get("chart")
        if ch and ch.get("series"):
            xname = ch.get("x", "x")
            lo, hi, n = ch.get("range", [0, 1, 40])
            lo = float(safe_eval(str(lo), names)) if isinstance(lo, str) else float(lo)
            hi = float(safe_eval(str(hi), names)) if isinstance(hi, str) else float(hi)
            n = max(2, min(int(n), 400))
            series = []
            colors = ["#1b3a5c", "#e3a725", "#3a9d6a", "#8e6cb8"]
            for idx, s_ in enumerate(ch["series"]):
                pts = []
                for k in range(n + 1):
                    x = lo + (hi - lo) * k / n
                    env = dict(names)
                    env[xname] = x
                    try:
                        pts.append((x, float(safe_eval(s_["expr"], env))))
                    except (ZeroDivisionError, ValueError, OverflowError):
                        continue
                series.append((s_.get("label", s_["expr"]), pts, colors[idx % len(colors)]))
            chart = _svg_chart(series, ch.get("xlabel", xname), ch.get("ylabel", ""), title=ch.get("title", ""))
        headline = self.spec.get("headline")
        if headline:
            try:
                headline = headline.format(**{k: (round(v, 3) if isinstance(v, float) else v) for k, v in names.items()})
            except (KeyError, ValueError):
                pass
        return {"results": results, "checks": checks, "chart": chart, "headline": headline or ""}


EXAMPLE_SPEC = {
    "inputs": [{"name": "L", "label": "Span", "unit": "m", "default": 6, "min": 1, "max": 20, "param": "beam_span"}, {"name": "w", "label": "Uniform load", "unit": "kN/m", "default": 25, "min": 0, "max": 200}],
    "formulas": [{"name": "M", "expr": "w*L**2/8"}, {"name": "V", "expr": "w*L/2"}],
    "outputs": [{"name": "M", "label": "Maximum moment", "unit": "kNm", "decimals": 1}, {"name": "V", "label": "Maximum shear", "unit": "kN", "decimals": 1}],
    "checks": [{"label": "M ≤ 120 kNm", "expr": "M <= 120"}],
    "chart": {"x": "x", "range": [0, "L", 40], "series": [{"label": "M(x)", "expr": "w*x*(L-x)/2"}], "xlabel": "x (m)", "ylabel": "kNm", "title": "Bending moment"},
    "headline": "M = {M} kNm",
}
