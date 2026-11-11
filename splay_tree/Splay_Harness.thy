theory Splay_Harness
  imports
    "Splay_Tree.Splay_Map"
    "HOL-Library.Code_Target_Int"
    "Python.Python_Setup"
begin

text \<open>
  Exported from AFP entry Splay_Tree, theory Splay_Map (maps as splay trees, keys and values
  instantiated to @{typ int}). Monomorphic wrappers avoid type-class dictionaries and the
  Python keyword clash on @{text del} in the generated interface.
\<close>

text \<open>
  The functions @{const Splay_Tree.splay}, @{const Splay_Tree.splay_max} and
  @{const Splay_Map.splay} are defined by @{command function} with side conditions,
  so the executable equations are the @{text splay_code} lemmas.
\<close>
declare Splay_Tree.splay_max_code [code]
declare Splay_Map.splay_code [code]

text \<open>
  @{typ "int option"} as Python @{text None} or the plain value. Sound here: the exported code
  never matches on options, and @{typ int} has no @{text None}.
\<close>
code_printing
    type_constructor option \<rightharpoonup> (Python) "_ option"
  | constant None \<rightharpoonup> (Python) "None"
  | constant Some \<rightharpoonup> (Python) "_"

definition m_empty :: "(int \<times> int) tree" where
  "m_empty = \<langle>\<rangle>"

definition m_update :: "int \<Rightarrow> int \<Rightarrow> (int \<times> int) tree \<Rightarrow> (int \<times> int) tree" where
  "m_update = Splay_Map.update"

definition m_lookup :: "(int \<times> int) tree \<Rightarrow> int \<Rightarrow> int option" where
  "m_lookup = Splay_Map.lookup"

definition m_delete :: "int \<Rightarrow> (int \<times> int) tree \<Rightarrow> (int \<times> int) tree" where
  "m_delete = Splay_Map.delete"

definition m_items :: "(int \<times> int) tree \<Rightarrow> (int \<times> int) list" where
  "m_items = Tree.inorder"

text \<open>Smoke checks, evaluated in SML.\<close>

lemma "m_items (m_update 2 20 (m_update 1 10 (m_update 3 30 m_empty))) = [(1,10),(2,20),(3,30)]"
  by eval

lemma "m_lookup (m_update 1 5 (m_update 1 10 m_empty)) 1 = Some 5"
  by eval

lemma "m_items (m_delete 2 (m_update 3 30 (m_update 2 20 (m_update 1 10 m_empty)))) = [(1,10),(3,30)]"
  by eval

lemma "m_lookup m_empty 7 = None"
  by eval

export_code m_empty m_update m_lookup m_delete m_items
  in Python module_name Splay_Ref
  file "./generated"

end
