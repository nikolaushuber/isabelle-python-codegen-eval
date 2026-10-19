theory Binomial_Heap_Harness
  imports
    "HOL-Data_Structures.Binomial_Heap"
    "HOL-Library.Code_Target_Int"
    "Python.Python_Setup"
begin

text \<open>
  Golden reference for differential testing of the Python code generator backend.
  Source: HOL-Data_Structures theory Binomial_Heap (min-heap as a forest of binomial trees,
  ordered by strictly increasing @{typ nat} rank), elements instantiated to @{typ int}.
  Monomorphic wrappers keep the generated interface simple.
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

definition h_empty :: "int forest" where
  "h_empty = []"

definition h_insert :: "int \<Rightarrow> int forest \<Rightarrow> int forest" where
  "h_insert = Binomial_Heap.insert"

definition h_merge :: "int forest \<Rightarrow> int forest \<Rightarrow> int forest" where
  "h_merge = Binomial_Heap.merge"

text \<open>Total versions of @{const get_min} and @{const del_min}, for comparison with @{text "heapq"}.\<close>
definition h_get_min :: "int forest \<Rightarrow> int option" where
  "h_get_min ts = (if ts = [] then None else Some (get_min ts))"

definition h_del_min :: "int forest \<Rightarrow> int forest" where
  "h_del_min ts = (if ts = [] then [] else del_min ts)"

text \<open>The original partial operations, to see how the backend handles missing equations.\<close>
definition h_get_min_partial :: "int forest \<Rightarrow> int" where
  "h_get_min_partial = get_min"

definition h_del_min_partial :: "int forest \<Rightarrow> int forest" where
  "h_del_min_partial = del_min"

text \<open>Elements in preorder; recursion depth is bounded by the largest rank, i.e. O(log n).\<close>
fun tree_elems :: "'a tree \<Rightarrow> 'a list" where
  "tree_elems (Node _ x ts) = x # concat (map tree_elems ts)"

definition h_elems :: "int forest \<Rightarrow> int list" where
  "h_elems ts = concat (map tree_elems ts)"

lemma mset_forest_elems:
  "(\<And>t. t \<in> set ts \<Longrightarrow> mset (tree_elems t) = mset_tree t) \<Longrightarrow>
   mset (concat (map tree_elems ts)) = mset_forest ts"
  by (induction ts) auto

lemma mset_tree_elems: "mset (tree_elems t) = mset_tree t"
  by (induction t rule: tree_elems.induct) (simp add: mset_forest_elems)

lemma mset_h_elems: "mset (h_elems ts) = mset_forest ts"
  by (simp add: h_elems_def mset_forest_elems mset_tree_elems)

definition h_ranks :: "int forest \<Rightarrow> nat list" where
  "h_ranks ts = map rank ts"

definition h_invar :: "int forest \<Rightarrow> bool" where
  "h_invar = invar"

text \<open>Smoke checks evaluated by Isabelle's own code generator (SML), independent of the Python backend.\<close>

lemma "h_get_min (h_insert 2 (h_insert 1 (h_insert 3 h_empty))) = Some 1"
  by eval

lemma "h_get_min (h_del_min (h_insert 2 (h_insert 1 (h_insert 3 h_empty)))) = Some 2"
  by eval

lemma "h_invar (h_merge (h_insert 5 (h_insert 4 h_empty)) (h_insert 1 (h_insert 9 h_empty)))"
  by eval

lemma "h_ranks (h_insert 7 (h_insert 6 (h_insert 5 (h_insert 4 (h_insert 3 h_empty))))) = [0, 2]"
  by eval

lemma "h_get_min h_empty = None"
  by eval

export_code h_empty h_insert h_merge h_get_min h_del_min h_get_min_partial h_del_min_partial
    h_elems h_ranks h_invar
  in Python module_name Binomial_Heap_Ref
  file "./generated"

end
