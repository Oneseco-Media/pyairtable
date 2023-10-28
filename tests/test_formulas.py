import datetime
from decimal import Decimal
from fractions import Fraction

import pytest
from mock import call

from pyairtable import formulas as F
from pyairtable import orm
from pyairtable.formulas import AND, EQ, GT, GTE, LT, LTE, NE, NOT, OR
from pyairtable.testing import fake_meta


def test_equivalence():
    assert F.Formula("a") == F.Formula("a")
    assert F.Formula("a") != F.Formula("b")
    assert F.Formula("a") != "b"


def test_operators():
    lft = F.Formula("a")
    rgt = F.Formula("b")
    assert str(lft) == "a"
    assert str(lft & rgt) == "AND(a, b)"
    assert str(lft | rgt) == "OR(a, b)"
    assert str(~(lft & rgt)) == "NOT(AND(a, b))"
    assert repr(lft & rgt) == "AND(Formula('a'), Formula('b'))"
    assert repr(lft | rgt) == "OR(Formula('a'), Formula('b'))"
    assert repr(~F.Formula("a")) == "NOT(Formula('a'))"
    assert lft.flatten() is lft
    assert repr(lft ^ rgt) == "XOR(Formula('a'), Formula('b'))"
    assert str(lft ^ rgt) == "XOR(a, b)"


@pytest.mark.parametrize(
    "cmp,op",
    [
        (EQ, "="),
        (NE, "!="),
        (GT, ">"),
        (GTE, ">="),
        (LT, "<"),
        (LTE, "<="),
    ],
)
def test_comparisons(cmp, op):
    assert repr(cmp(1, 1)) == f"{cmp.__name__}(1, 1)"
    assert str(cmp(1, 1)) == f"1{op}1"
    assert str(cmp(F.Formula("Foo"), "Foo")) == f"Foo{op}'Foo'"


@pytest.mark.parametrize(
    "target",
    [
        F.Formula("X"),  # Formula
        F.Field("X"),  # Field
        F.EQ(1, 1),  # Comparison
        F.TODAY(),  # FunctionCall
    ],
)
@pytest.mark.parametrize(
    "shortcut,cmp",
    [
        ("eq", EQ),
        ("ne", NE),
        ("gt", GT),
        ("gte", GTE),
        ("lt", LT),
        ("lte", LTE),
    ],
)
def test_comparison_shortcuts(target, shortcut, cmp):
    """
    Test that methods like .eq() are exposed on all subclasses of Formula.
    """
    formula = getattr(target, shortcut)("Y")  # Field("X").eq("Y")
    assert formula == cmp(target, "Y")  # EQ(Field("X"), "Y")


def test_comparison_equivalence():
    assert EQ(1, 1) == EQ(1, 1)
    assert EQ(1, 2) != EQ(2, 1)
    assert EQ(1, 1) != NE(1, 1)
    assert EQ(1, 1) != F.Formula("1=1")


def test_comparison_is_abstract():
    with pytest.raises(NotImplementedError):
        F.Comparison("lft", "rgt")


@pytest.mark.parametrize("op", ("AND", "OR"))
def test_compound(op):
    cmp = F.Compound(op, [EQ("foo", 1), EQ("bar", 2)])
    assert repr(cmp) == f"{op}(EQ('foo', 1), EQ('bar', 2))"


@pytest.mark.parametrize("op", ("AND", "OR"))
def test_compound_with_iterable(op):
    cmp = F.Compound(op, (EQ(f"f{n}", n) for n in range(3)))
    assert repr(cmp) == f"{op}(EQ('f0', 0), EQ('f1', 1), EQ('f2', 2))"


def test_compound_equivalence():
    assert F.Compound("AND", [1]) == F.Compound("AND", [1])
    assert F.Compound("AND", [1]) != F.Compound("AND", [2])
    assert F.Compound("AND", [1]) != F.Compound("OR", [1])
    assert F.Compound("AND", [1]) != [1]


@pytest.mark.parametrize("cmp", [AND, OR])
@pytest.mark.parametrize(
    "call_args",
    [
        # mix *components and and **fields
        call(EQ("foo", 1), bar=2),
        # multiple *components
        call(EQ("foo", 1), EQ(F.Field("bar"), 2)),
        # one item in *components that is also an iterable
        call([EQ("foo", 1), EQ(F.Field("bar"), 2)]),
        call((EQ("foo", 1), EQ(F.Field("bar"), 2))),
        lambda: call(iter([EQ("foo", 1), EQ(F.Field("bar"), 2)])),
        # test that we accept `str` and convert to formulas
        call(["'foo'=1", "{bar}=2"]),
    ],
)
def test_compound_constructors(cmp, call_args):
    if type(call_args) != type(call):
        call_args = call_args()
    compound = cmp(*call_args.args, **call_args.kwargs)
    expected = cmp(EQ("foo", 1), EQ(F.Field("bar"), 2))
    # compare final output expression, since the actual values will not be equal
    assert str(compound) == str(expected)


@pytest.mark.parametrize("cmp", ["AND", "OR", "NOT"])
def test_compound_without_parameters(cmp):
    with pytest.raises(
        ValueError,
        match=r"Compound\(\) requires at least one component",
    ):
        F.Compound(cmp, [])


def test_compound_flatten():
    a = EQ("a", "a")
    b = EQ("b", "b")
    c = EQ("c", "c")
    d = EQ("d", "d")
    e = EQ("e", "e")
    c = (a & b) & (c & (d | e))
    assert repr(c) == repr(
        AND(
            AND(EQ("a", "a"), EQ("b", "b")),
            AND(EQ("c", "c"), OR(EQ("d", "d"), EQ("e", "e"))),
        )
    )
    assert repr(c.flatten()) == repr(
        AND(
            EQ("a", "a"),
            EQ("b", "b"),
            EQ("c", "c"),
            OR(EQ("d", "d"), EQ("e", "e")),
        )
    )
    assert repr((~c).flatten()) == repr(
        NOT(
            AND(
                EQ("a", "a"),
                EQ("b", "b"),
                EQ("c", "c"),
                OR(EQ("d", "d"), EQ("e", "e")),
            )
        )
    )
    assert str((~c).flatten()) == (
        "NOT(AND('a'='a', 'b'='b', 'c'='c', OR('d'='d', 'e'='e')))"
    )


def test_compound_flatten_circular_dependency():
    circular = NOT(F.Formula("x"))
    circular.components = [circular]
    with pytest.raises(F.CircularDependency):
        circular.flatten()


@pytest.mark.parametrize(
    "compound,expected",
    [
        (EQ(1, 1).eq(True), "(1=1)=TRUE()"),
        (EQ(False, EQ(1, 2)), "FALSE()=(1=2)"),
    ],
)
def test_compound_with_compound(compound, expected):
    assert str(compound) == expected


def test_not():
    assert str(NOT(EQ("foo", 1))) == "NOT('foo'=1)"
    assert str(NOT(foo=1)) == "NOT({foo}=1)"

    with pytest.raises(TypeError):
        NOT(EQ("foo", 1), EQ("bar", 2))

    with pytest.raises(ValueError, match="requires exactly one condition; got 2"):
        NOT(EQ("foo", 1), bar=2)

    with pytest.raises(ValueError, match="requires exactly one condition; got 2"):
        NOT(foo=1, bar=2)

    with pytest.raises(ValueError, match="requires exactly one condition; got 0"):
        NOT()


@pytest.mark.parametrize(
    "input,expected",
    [
        (EQ(F.Formula("a"), "b"), "a='b'"),
        (True, "TRUE()"),
        (False, "FALSE()"),
        (3, "3"),
        (3.5, "3.5"),
        (Decimal("3.14159265"), "3.14159265"),
        (Fraction("4/19"), "4/19"),
        ("asdf", "'asdf'"),
        ("Jane's", "'Jane\\'s'"),
        ([1, 2, 3], TypeError),
        ((1, 2, 3), TypeError),
        ({1, 2, 3}, TypeError),
        ({1: 2, 3: 4}, TypeError),
        (
            datetime.date(2023, 12, 1),
            "DATETIME_PARSE('2023-12-01')",
        ),
        (
            datetime.datetime(2023, 12, 1, 12, 34, 56),
            "DATETIME_PARSE('2023-12-01T12:34:56.000Z')",
        ),
    ],
)
def test_to_formula(input, expected):
    if isinstance(expected, type) and issubclass(expected, Exception):
        with pytest.raises(expected):
            F.to_formula_str(input)
    else:
        assert F.to_formula_str(input) == expected


@pytest.mark.parametrize(
    "sig,expected",
    [
        (call({}), "None"),
        (call({"Field": "value"}), "{Field}='value'"),
        (call({"A": ("=", 123), "B": ("!=", 123)}), "AND({A}=123, {B}!=123)"),
        (call({"A": 123, "B": 123}, match_any=True), "OR({A}=123, {B}=123)"),
        (call({"Field": ("<", 123)}), "{Field}<123"),
        (call({"Field": ("<=", 123)}), "{Field}<=123"),
        (call({"Field": (">", 123)}), "{Field}>123"),
        (call({"Field": (">=", 123)}), "{Field}>=123"),
    ],
)
def test_match(sig, expected):
    assert str(F.match(*sig.args, **sig.kwargs)) == expected


def test_function_call():
    fc = F.FunctionCall("IF", 1, True, False)
    assert repr(fc) == "IF(1, True, False)"
    assert str(fc) == "IF(1, TRUE(), FALSE())"


def test_field_name():
    assert F.field_name("First Name") == "{First Name}"
    assert F.field_name("Guest's Name") == "{Guest\\'s Name}"


def test_quoted():
    assert F.quoted("John") == "'John'"
    assert F.quoted("Guest's Name") == "'Guest\\'s Name'"


@pytest.mark.parametrize(
    "methodname,op",
    [
        ("eq", "="),
        ("ne", "!="),
        ("gt", ">"),
        ("gte", ">="),
        ("lt", "<"),
        ("lte", "<="),
    ],
)
def test_orm_field(methodname, op):
    class FakeModel(orm.Model):
        Meta = fake_meta()
        name = orm.fields.TextField("Name")
        age = orm.fields.IntegerField("Age")

    formula = getattr(FakeModel.name, methodname)("Value")
    formula &= GTE(FakeModel.age, 21)
    assert F.to_formula_str(formula) == f"AND({{Name}}{op}'Value', {{Age}}>=21)"
