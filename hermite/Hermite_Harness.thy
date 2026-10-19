theory Hermite_Harness
  imports
    Hermite.Hermite_IArrays
    "HOL-Library.Code_Target_Int"
    "Python.Python_IArray"
begin

text \<open>
  Verified reference for differential testing of Python libraries (here: SymPy's Hermite normal
  form). Source: AFP entry Hermite, executable version over immutable arrays. The result is the
  row-style Hermite normal form @{text "H = P * A"} with @{text P} invertible over @{typ int}:
  upper echelon form, positive pivots, entries above each pivot reduced into @{text "[0, pivot)"}.
\<close>

definition hnf_rows :: "int list list \<Rightarrow> int list list" where
  "hnf_rows xss = map IArray.list_of (IArray.list_of
     (Hermite_of_iarrays (IArray (map IArray xss)) ass_function_euclidean res_function_euclidean
        euclid_ext2))"

definition echelon_rows :: "int list list \<Rightarrow> int list list" where
  "echelon_rows xss = map IArray.list_of (IArray.list_of
     (echelon_form_of_iarrays (IArray (map IArray xss)) euclid_ext2))"

text \<open>Example from the AFP entry, evaluated by Isabelle's own code generator (SML).\<close>
value "hnf_rows [[37,8,6],[5,4,-8],[3,24,-7]]"

export_code hnf_rows echelon_rows
  in Python module_name Hermite_Ref
  file "./generated"

end
