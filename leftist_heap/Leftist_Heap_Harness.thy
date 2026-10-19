theory Leftist_Heap_Harness
  imports
    "HOL-Data_Structures.Leftist_Heap"
    "HOL-Library.Code_Target_Int"
    "Python.Python_Setup"
begin

text \<open>
  Golden reference for differential testing of the Python code generator backend.
  Source: HOL-Data_Structures theory Leftist_Heap (min-heap with @{typ nat} ranks), elements
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

definition h_empty :: "int lheap" where
  "h_empty = Leftist_Heap.empty"

definition h_insert :: "int \<Rightarrow> int lheap \<Rightarrow> int lheap" where
  "h_insert = Leftist_Heap.insert"

definition h_merge :: "int lheap \<Rightarrow> int lheap \<Rightarrow> int lheap" where
  "h_merge = Leftist_Heap.merge"

definition h_del_min :: "int lheap \<Rightarrow> int lheap" where
  "h_del_min = Leftist_Heap.del_min"

text \<open>Total minimum, for comparison with @{text "heapq"}.\<close>
definition h_get_min :: "int lheap \<Rightarrow> int option" where
  "h_get_min t = (case t of Leaf \<Rightarrow> None | Node _ (a, _) _ \<Rightarrow> Some a)"

text \<open>The original partial @{const get_min}, to see how the backend handles a missing equation.\<close>
definition h_get_min_partial :: "int lheap \<Rightarrow> int" where
  "h_get_min_partial = Leftist_Heap.get_min"

definition h_elems :: "int lheap \<Rightarrow> int list" where
  "h_elems t = inorder t"

definition h_invar :: "int lheap \<Rightarrow> bool" where
  "h_invar t = (heap t \<and> ltree t)"

text \<open>Smoke checks evaluated by Isabelle's own code generator (SML), independent of the Python backend.\<close>

lemma "h_get_min (h_insert 2 (h_insert 1 (h_insert 3 h_empty))) = Some 1"
  by eval

lemma "h_get_min (h_del_min (h_insert 2 (h_insert 1 (h_insert 3 h_empty)))) = Some 2"
  by eval

lemma "h_invar (h_merge (h_insert 5 (h_insert 4 h_empty)) (h_insert 1 (h_insert 9 h_empty)))"
  by eval

lemma "h_get_min h_empty = None"
  by eval

export_code h_empty h_insert h_merge h_del_min h_get_min h_get_min_partial h_elems h_invar
  in Python module_name Leftist_Heap_Ref
  file "./generated"

end
