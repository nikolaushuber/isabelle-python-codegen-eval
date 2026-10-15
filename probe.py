"""Print what the generated module returns, to check the decoders in golden_adapter.py."""
import golden_adapter as ga

g = ga.gen
print("module:", g.__name__, getattr(g, "__file__", ""))
for name in ["m_empty", "m_update", "m_lookup", "m_delete", "m_items"]:
    v = getattr(g, name, None)
    print(f"{name:10s} present={v is not None} type={type(v).__name__} arity={ga._arity(v) if callable(v) else '-'}")

t = ga.GoldenSplay.empty()
print("empty raw      :", repr(t.raw))
t = t.update(2, 20).update(1, 10).update(3, 30)
print("raw after 3 upd:", repr(t.raw))
print("raw lookup hit :", repr(ga._apply(g.m_lookup, t.raw, 2)))
print("raw lookup miss:", repr(ga._apply(g.m_lookup, t.raw, 9)))
print("raw items      :", repr(ga._apply(g.m_items, t.raw)))
print("decoded items  :", t.items())
print("decoded lookups:", t.lookup(2), t.lookup(9))
print("after delete 2 :", t.delete(2).items(), "| original still:", t.items())
