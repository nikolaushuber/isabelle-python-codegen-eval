"""
HAND-WRITTEN STAND-IN, not backend output. Mirrors Splay_Map.splay_code / Splay_Tree.splay_max_code
so the harness can be smoke-tested before the real generated module exists.
Use with:  SPLAY_GEN_PATH=../mock_generated pytest
"""


class Leaf:
    __slots__ = ()


class Node:
    __slots__ = ("l", "a", "r")

    def __init__(self, l, a, r):
        self.l, self.a, self.r = l, a, r


class Some:
    __slots__ = ("a",)

    def __init__(self, a):
        self.a = a


LEAF = Leaf()
m_empty = LEAF


def _leaf(t):
    return isinstance(t, Leaf)


def _splay(x, t):
    if _leaf(t):
        return t
    al, a, ar = t.l, t.a, t.r
    if x == a[0]:
        return t
    if x < a[0]:
        if _leaf(al):
            return t
        bl, b, br = al.l, al.a, al.r
        if x == b[0]:
            return Node(bl, b, Node(br, a, ar))
        if x < b[0]:
            if _leaf(bl):
                return Node(bl, b, Node(br, a, ar))
            s = _splay(x, bl)
            return Node(s.l, s.a, Node(s.r, b, Node(br, a, ar)))
        if _leaf(br):
            return Node(bl, b, Node(br, a, ar))
        s = _splay(x, br)
        return Node(Node(bl, b, s.l), s.a, Node(s.r, a, ar))
    if _leaf(ar):
        return t
    bl, b, br = ar.l, ar.a, ar.r
    if x == b[0]:
        return Node(Node(al, a, bl), b, br)
    if x < b[0]:
        if _leaf(bl):
            return Node(Node(al, a, bl), b, br)
        s = _splay(x, bl)
        return Node(Node(al, a, s.l), s.a, Node(s.r, b, br))
    if _leaf(br):
        return Node(Node(al, a, bl), b, br)
    s = _splay(x, br)
    return Node(Node(Node(al, a, bl), b, s.l), s.a, s.r)


def _splay_max(t):
    if _leaf(t):
        return t
    la, a, ra = t.l, t.a, t.r
    if _leaf(ra):
        return t
    lb, b, rb = ra.l, ra.a, ra.r
    if _leaf(rb):
        return Node(Node(la, a, lb), b, rb)
    s = _splay_max(rb)
    return Node(Node(Node(la, a, lb), b, s.l), s.a, s.r)


def m_update(x, y, t):
    if _leaf(t):
        return Node(LEAF, (x, y), LEAF)
    s = _splay(x, t)
    l, a, r = s.l, s.a, s.r
    if x == a[0]:
        return Node(l, (x, y), r)
    if x < a[0]:
        return Node(l, (x, y), Node(LEAF, a, r))
    return Node(Node(l, a, LEAF), (x, y), r)


def m_lookup(t, x):
    s = _splay(x, t)
    if _leaf(s):
        return None
    return Some(s.a[1]) if x == s.a[0] else None


def m_delete(x, t):
    if _leaf(t):
        return LEAF
    s = _splay(x, t)
    l, a, r = s.l, s.a, s.r
    if x != a[0]:
        return Node(l, a, r)
    if _leaf(l):
        return r
    m = _splay_max(l)
    return Node(m.l, m.a, r)


def m_items(t):
    if _leaf(t):
        return []
    return m_items(t.l) + [t.a] + m_items(t.r)
