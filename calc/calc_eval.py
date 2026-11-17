"""A small evaluator of EPICS calc expression strings, with EPICS semantics, for proving slot expressions offline.

The Python mirrors of the older lanes (monp_transform.evaluate, quality_slots.bounds) are hand-written, so they cannot
catch a precedence or syntax mistake in the strings that are actually installed. This module evaluates the STRINGS.

Supported: numbers (1E-9, .568), letters A-P, + - * / % ^ **, unary minus, comparisons (< <= > >= == != =), && ||,
?:, parentheses, and the functions EXP LN LOG ABS FLOOR CEIL SQR MAX MIN. Everything is a C double.

Semantics that matter (EPICS calc, and the repo's known trap, calc/HANDOFF.md):
  - unary minus binds TIGHTER than ^: -2^2 is (-2)^2 = 4, and EXP(-(x)^p) is EXP((-x)^p), which is NaN for x > 0, fractional p.
  - ^ and ** are the same operator, left-associative; % is the C remainder on values truncated to integers.
  - division by zero gives +-inf (0/0 gives NaN), LN(0) gives -inf, a negative base to a fractional power gives NaN, an
    overflow gives inf: nothing raises. Comparisons with NaN are false; NaN counts as true in ?:, && and ||.
  - MAX and MIN return NaN when any argument is NaN (calcPerform.c); 0^negative is +inf (C pow).
  - && || comparisons yield 1.0 or 0.0.

eval_transform() evaluates a transform record: letters A..P in order, a letter that is used before it is computed holds
its previous value (state), a letter with no expression is an input.
"""
import math
import re

LETTERS = "ABCDEFGHIJKLMNOP"
NAN = float("nan")
INF = float("inf")

_TOKEN = re.compile(r"""\s*(?:
    (?P<num>(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)
  | (?P<func>[A-Z]{2,}(?=\())
  | (?P<var>[A-P])
  | (?P<op>\*\*|<=|>=|==|!=|&&|\|\||[-+*/%^<>=?:(),])
)""", re.X)


def _tokens(s):
    pos, out = 0, []
    s = s.strip()
    while pos < len(s):
        m = _TOKEN.match(s, pos)
        if not m or m.end() == pos:
            raise ValueError(f"cannot parse {s!r} at {pos}: {s[pos:pos + 10]!r}")
        pos = m.end()
        kind = m.lastgroup
        out.append((kind, m.group(kind)))
    return out


def _div(a, b):
    if b == 0:
        if a != a or a == 0:
            return NAN
        return math.copysign(INF, a) * math.copysign(1.0, b)
    return a / b


def _pow(a, b):
    if a == 0 and b < 0:
        return INF               # C pow(0, negative) is +inf (math.pow raises)
    try:
        r = math.pow(a, b)
    except ValueError:
        return NAN
    except OverflowError:
        return INF if (a > 0 or float(b).is_integer() and int(b) % 2 == 0) else -INF
    return r


def _mod(a, b):
    if a != a or b != b or math.isinf(a) or math.isinf(b):
        return NAN
    ia, ib = int(a), int(b)
    if ib == 0:
        return NAN
    return float(int(math.fmod(ia, ib)))


def _exp(x):
    try:
        return math.exp(x)
    except OverflowError:
        return INF


def _ln(x):
    if x != x or x < 0:
        return NAN
    if x == 0:
        return -INF
    return math.log(x)


def _log10(x):
    return _ln(x) / math.log(10) if x > 0 else _ln(x)


def _floor(x):
    return x if (x != x or math.isinf(x)) else float(math.floor(x))


def _ceil(x):
    return x if (x != x or math.isinf(x)) else float(math.ceil(x))


def _sqr(x):
    return NAN if x != x or x < 0 else math.sqrt(x)


def _max(*a):
    if any(x != x for x in a):       # EPICS calcPerform.c: a NaN argument gives NaN
        return NAN
    return max(a)


def _min(*a):
    if any(x != x for x in a):
        return NAN
    return min(a)


FUNCS = {"EXP": (_exp, 1, 1), "LN": (_ln, 1, 1), "LOG": (_log10, 1, 1), "ABS": (lambda x: abs(x), 1, 1),
         "FLOOR": (_floor, 1, 1), "CEIL": (_ceil, 1, 1), "SQR": (_sqr, 1, 1), "MAX": (_max, 1, 4), "MIN": (_min, 1, 4)}


def _true(x):
    return x != 0          # NaN != 0 is True, as in C


class _Parser:
    """Recursive descent; each parse method returns a closure env -> float. Lowest to highest precedence:
    ?:  ||  &&  comparisons  + -  * / %  ^  unary minus  primary.  Unary minus is ABOVE ^ (the EPICS trap)."""

    def __init__(self, text):
        self.text = text
        self.t = _tokens(text)
        self.i = 0
        self.vars = set()

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self, val=None):
        k, v = self.peek()
        if k is None or (val is not None and v != val):
            raise ValueError(f"expected {val!r} in {self.text!r}, got {v!r}")
        self.i += 1
        return v

    def parse(self):
        f = self.cond()
        if self.i != len(self.t):
            raise ValueError(f"trailing {self.t[self.i][1]!r} in {self.text!r}")
        return f

    def cond(self):
        c = self.lor()
        if self.peek()[1] == "?":
            self.take("?")
            a = self.cond()
            self.take(":")
            b = self.cond()
            return lambda e, c=c, a=a, b=b: a(e) if _true(c(e)) else b(e)
        return c

    def lor(self):
        f = self.land()
        while self.peek()[1] == "||":
            self.take()
            g = self.land()
            f = (lambda e, f=f, g=g: 1.0 if (_true(f(e)) or _true(g(e))) else 0.0)
        return f

    def land(self):
        f = self.cmp()
        while self.peek()[1] == "&&":
            self.take()
            g = self.cmp()
            f = (lambda e, f=f, g=g: 1.0 if (_true(f(e)) and _true(g(e))) else 0.0)
        return f

    _CMP = {"<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
            "==": lambda a, b: a == b, "=": lambda a, b: a == b, "!=": lambda a, b: a != b}

    def cmp(self):
        f = self.add()
        while self.peek()[1] in self._CMP:
            op = self._CMP[self.take()]
            g = self.add()
            f = (lambda e, f=f, g=g, op=op: 1.0 if op(f(e), g(e)) else 0.0)
        return f

    def add(self):
        f = self.mul()
        while self.peek()[1] in ("+", "-"):
            plus = self.take() == "+"
            g = self.mul()
            f = (lambda e, f=f, g=g: f(e) + g(e)) if plus else (lambda e, f=f, g=g: f(e) - g(e))
        return f

    def mul(self):
        f = self.pow()
        while self.peek()[1] in ("*", "/", "%"):
            op = self.take()
            g = self.pow()
            if op == "*":
                f = (lambda e, f=f, g=g: f(e) * g(e))
            elif op == "/":
                f = (lambda e, f=f, g=g: _div(f(e), g(e)))
            else:
                f = (lambda e, f=f, g=g: _mod(f(e), g(e)))
        return f

    def pow(self):
        f = self.unary()
        while self.peek()[1] in ("^", "**"):
            self.take()
            g = self.unary()
            f = (lambda e, f=f, g=g: _pow(f(e), g(e)))
        return f

    def unary(self):
        if self.peek()[1] == "-":
            self.take()
            g = self.unary()
            return lambda e, g=g: -g(e)
        if self.peek()[1] == "+":
            self.take()
            return self.unary()
        return self.primary()

    def primary(self):
        k, v = self.peek()
        if k == "num":
            self.take()
            x = float(v)
            return lambda e, x=x: x
        if k == "var":
            self.take()
            self.vars.add(v)
            return lambda e, v=v: e[v]
        if k == "func":
            self.take()
            fn, lo, hi = FUNCS[v] if v in FUNCS else (None, 0, 0)
            if fn is None:
                raise ValueError(f"unknown function {v} in {self.text!r}")
            self.take("(")
            args = [self.cond()]
            while self.peek()[1] == ",":
                self.take()
                args.append(self.cond())
            self.take(")")
            if not lo <= len(args) <= hi:
                raise ValueError(f"{v} takes {lo}-{hi} arguments in {self.text!r}")
            return lambda e, fn=fn, args=args: fn(*(a(e) for a in args))
        if v == "(":
            self.take()
            f = self.cond()
            self.take(")")
            return f
        raise ValueError(f"unexpected {v!r} in {self.text!r}")


_cache = {}


def compile_expr(text):
    """Return (function env -> float, set of letters used). Raises ValueError on a syntax error."""
    if text not in _cache:
        p = _Parser(text)
        _cache[text] = (p.parse(), frozenset(p.vars))
    return _cache[text]


def letters_used(text):
    return set(compile_expr(text)[1])


def evaluate(text, env):
    """Evaluate one expression; env maps letters A-P to floats (missing letters are 0)."""
    f, _ = compile_expr(text)
    e = {x: 0.0 for x in LETTERS}
    e.update({k: float(v) for k, v in env.items()})
    return float(f(e))


def eval_transform(expr_by_letter, inputs=None, state=None):
    """Evaluate a transform record. expr_by_letter: {"I": "expression", ...} (CLCx; letters without one are inputs);
    inputs: letters set by links or hand-set values, re-read every scan; state: the previous values of every letter
    (default 0). Returns the new value of every letter A-P.

    A letter holds its previous value until its own expression runs, so an expression that uses a LATER letter sees that
    letter's value from the previous scan (and so does a letter that uses itself, as in H+1)."""
    v = {x: 0.0 for x in LETTERS}
    v.update({k: float(x) for k, x in (state or {}).items()})
    v.update({k: float(x) for k, x in (inputs or {}).items()})
    for x in LETTERS:
        e = (expr_by_letter.get(f"CLC{x}") if f"CLC{x}" in expr_by_letter else expr_by_letter.get(x)) or ""
        if e:
            v[x] = evaluate(e, v)
    return v
