theory RBT_Map_Harness
  imports
    "HOL-Data_Structures.RBT_Map"
    "HOL-Library.Code_Target_Int"
    "Python.Python_Setup"
begin

text \<open>
  Golden reference for differential testing of the Python code generator backend.
  Source: HOL-Data_Structures theory RBT_Map (maps as red-black trees), keys and values
  instantiated to @{typ int}. Monomorphic wrappers keep the generated interface simple.
\<close>

text \<open>
  Native encoding of @{typ "int option"} for this harness only: @{const None} becomes Python
  @{text None} and @{term "Some x"} becomes @{text x}. Sound here because the exported code only
  constructs options and never matches on them, and @{typ int} has no @{text None} value.
\<close>
code_printing
    type_constructor option \<rightharpoonup> (Python) "_ option"
  | constant None \<rightharpoonup> (Python) "None"
  | constant Some \<rightharpoonup> (Python) "_"

definition r_empty :: "(int \<times> int) rbt" where
  "r_empty = RBT_Set.empty"

definition r_update :: "int \<Rightarrow> int \<Rightarrow> (int \<times> int) rbt \<Rightarrow> (int \<times> int) rbt" where
  "r_update = RBT_Map.update"

definition r_lookup :: "(int \<times> int) rbt \<Rightarrow> int \<Rightarrow> int option" where
  "r_lookup = Lookup2.lookup"

definition r_delete :: "int \<Rightarrow> (int \<times> int) rbt \<Rightarrow> (int \<times> int) rbt" where
  "r_delete = RBT_Map.delete"

definition r_items :: "(int \<times> int) rbt \<Rightarrow> (int \<times> int) list" where
  "r_items = Tree2.inorder"

text \<open>Red-black invariants plus strictly sorted keys.\<close>
definition r_invar :: "(int \<times> int) rbt \<Rightarrow> bool" where
  "r_invar t = (rbt t \<and> sorted_wrt (<) (map fst (Tree2.inorder t)))"

definition r_height :: "(int \<times> int) rbt \<Rightarrow> nat" where
  "r_height t = height t"

text \<open>Smoke checks evaluated by Isabelle's own code generator (SML), independent of the Python backend.\<close>

lemma "r_items (r_update 2 20 (r_update 1 10 (r_update 3 30 r_empty))) = [(1,10),(2,20),(3,30)]"
  by eval

lemma "r_lookup (r_update 1 5 (r_update 1 10 r_empty)) 1 = Some 5"
  by eval

lemma "r_items (r_delete 2 (r_update 3 30 (r_update 2 20 (r_update 1 10 r_empty)))) = [(1,10),(3,30)]"
  by eval

lemma "r_lookup r_empty 7 = None"
  by eval

lemma "r_invar (r_delete 3 (r_update 4 4 (r_update 3 3 (r_update 2 2 (r_update 1 1 r_empty)))))"
  by eval

export_code r_empty r_update r_lookup r_delete r_items r_invar r_height
  in Python module_name RBT_Map_Ref
  file "./generated"

end
