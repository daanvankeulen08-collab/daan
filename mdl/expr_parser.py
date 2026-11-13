"""A closed, non-eval symbolic expression parser.

Security note: this module never calls ``eval``/``exec``/``sympify``.  It
tokenises a deliberately tiny grammar and constructs SymPy objects directly:

    expr  := term (('+' | '-') term)*
    term  := unary ('*' unary)*
    unary := ('+' | '-') unary | power
    power := atom ('**' unary)?
    atom  := INTEGER | NAME | '(' expr ')'

Only non-negative integer exponents are accepted, so every result stays a
polynomial with exact integer arithmetic.
"""

from __future__ import annotations

import re

import sympy

from .errors import ToolValidationError

MAX_INPUT_CHARS = 200
MAX_TOKENS = 200
MAX_SYMBOL_LEN = 16
MAX_SYMBOLS = 10
MAX_EXPONENT = 32
MAX_DEPTH = 48
MAX_INPUT_INT_DIGITS = 12
MAX_RESULT_INT_DIGITS = 200

_NAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")
_INT_RE = re.compile(r"[0-9]+")


class ExpressionError(ToolValidationError):
    """The expression is outside the allowed grammar or limits."""


# A token is (kind, value) with kind in {"int", "name", "op", "eof"}.
Token = tuple[str, str]


def _tokenize(text: str) -> list[Token]:
    if not isinstance(text, str):
        raise ExpressionError("expression must be a string")
    if len(text) > MAX_INPUT_CHARS:
        raise ExpressionError(
            f"expression exceeds {MAX_INPUT_CHARS} characters"
        )
    if not text.strip():
        raise ExpressionError("expression is empty")

    tokens: list[Token] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch.isspace():
            i += 1
            continue
        if ch.isdigit():
            match = _INT_RE.match(text, i)
            assert match is not None
            digits = match.group(0)
            if len(digits) > MAX_INPUT_INT_DIGITS:
                raise ExpressionError("integer literal is too long")
            tokens.append(("int", digits))
            i = match.end()
            continue
        if ch.isalpha():
            match = _NAME_RE.match(text, i)
            if match is None:
                raise ExpressionError(f"illegal character {ch!r} at position {i}")
            name = match.group(0)
            if len(name) > MAX_SYMBOL_LEN:
                raise ExpressionError("variable name is too long")
            tokens.append(("name", name))
            i = match.end()
            continue
        if text.startswith("**", i):
            tokens.append(("op", "**"))
            i += 2
            continue
        if ch in "+-*()":
            tokens.append(("op", ch))
            i += 1
            continue
        raise ExpressionError(f"illegal character {ch!r} at position {i}")

    if len(tokens) > MAX_TOKENS:
        raise ExpressionError(f"expression exceeds {MAX_TOKENS} tokens")
    tokens.append(("eof", ""))
    return tokens


def _exponent_value(node: sympy.Expr) -> int:
    if not isinstance(node, sympy.Integer):
        raise ExpressionError(
            "exponent must be a non-negative integer literal"
        )
    value = int(node)
    if value < 0:
        raise ExpressionError("negative exponents are not allowed")
    if value > MAX_EXPONENT:
        raise ExpressionError(f"exponent exceeds the limit of {MAX_EXPONENT}")
    return value


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.depth = 0
        self.symbols: set[str] = set()

    # -- token helpers ---------------------------------------------------
    def _peek(self) -> Token:
        return self.tokens[self.pos]

    def _advance(self) -> Token:
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def _peek_op(self, *values: str) -> bool:
        token = self._peek()
        return token[0] == "op" and token[1] in values

    def _expect_op(self, value: str) -> None:
        token = self._peek()
        if value == "eof":
            if token[0] != "eof":
                raise ExpressionError("unexpected trailing input")
            self.pos += 1
            return
        if token[0] != "op" or token[1] != value:
            raise ExpressionError(f"expected {value!r}")
        self.pos += 1

    # -- grammar ---------------------------------------------------------
    def parse(self) -> sympy.Expr:
        expr = self._expr()
        self._expect_op("eof")
        validate_expression(expr)
        return expr

    def _expr(self) -> sympy.Expr:
        self.depth += 1
        if self.depth > MAX_DEPTH:
            raise ExpressionError("expression nesting is too deep")
        node = self._term()
        while self._peek_op("+", "-"):
            op = self._advance()[1]
            rhs = self._term()
            node = node + rhs if op == "+" else node - rhs
        self.depth -= 1
        return node

    def _term(self) -> sympy.Expr:
        node = self._unary()
        while self._peek_op("*"):
            self._advance()
            node = node * self._unary()
        return node

    def _unary(self) -> sympy.Expr:
        if self._peek_op("+", "-"):
            op = self._advance()[1]
            value = self._unary()
            return value if op == "+" else -value
        return self._power()

    def _power(self) -> sympy.Expr:
        base = self._atom()
        if self._peek_op("**"):
            self._advance()
            exponent = _exponent_value(self._unary())
            return base**exponent
        return base

    def _atom(self) -> sympy.Expr:
        token = self._peek()
        if token[0] == "int":
            self._advance()
            return sympy.Integer(int(token[1]))
        if token[0] == "name":
            self._advance()
            name = token[1]
            self.symbols.add(name)
            if len(self.symbols) > MAX_SYMBOLS:
                raise ExpressionError(f"more than {MAX_SYMBOLS} variables")
            return sympy.Symbol(name)
        if token[0] == "op" and token[1] == "(":
            self._advance()
            node = self._expr()
            self._expect_op(")")
            return node
        raise ExpressionError("expected a number, variable or '('")


def _validate_node(node: sympy.Expr, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise ExpressionError("expression structure is too deep")
    if isinstance(node, sympy.Integer):
        if len(str(abs(int(node)))) > MAX_RESULT_INT_DIGITS:
            raise ExpressionError("integer coefficient is too large")
        return
    if isinstance(node, sympy.Symbol):
        if len(node.name) > MAX_SYMBOL_LEN:
            raise ExpressionError("variable name is too long")
        return
    if isinstance(node, sympy.Add) or isinstance(node, sympy.Mul):
        for arg in node.args:
            _validate_node(arg, depth + 1)
        return
    if isinstance(node, sympy.Pow):
        if not isinstance(node.exp, sympy.Integer):
            raise ExpressionError("only integer exponents are allowed")
        exponent = int(node.exp)
        if exponent < 0 or exponent > MAX_EXPONENT:
            raise ExpressionError("exponent outside the allowed range")
        _validate_node(node.base, depth + 1)
        return
    raise ExpressionError(
        f"unsupported expression node: {type(node).__name__}"
    )


def validate_expression(expr: sympy.Expr) -> None:
    """Reject anything that is not a polynomial over integer atoms."""

    if not isinstance(expr, sympy.Expr):
        raise ExpressionError("not a SymPy expression")
    _validate_node(expr)


def parse_expression(text: str) -> sympy.Expr:
    """Parse *text* into a SymPy expression without using eval."""

    return _Parser(_tokenize(text)).parse()
