theory Smith_Harness
  imports
    Smith_Normal_Form.SNF_Algorithm_Euclidean_Domain
    Jordan_Normal_Form.Matrix_IArray_Impl
    "HOL-Library.Code_Target_Int"
    "Python.Python_Setup"
begin

text \<open>
  Verified reference for differential testing of Python libraries (here: SymPy's Smith normal
  form). Source: AFP entry Smith_Normal_Form, executable algorithm over Euclidean domains on
  Jordan_Normal_Form matrices. @{const Smith_ED_mxn} returns @{text "(P, S, Q)"} with
  @{text "S = P * A * Q"}, @{text P} and @{text Q} invertible and @{text S} in Smith normal form
  (diagonal, each diagonal entry dividing the next). Over @{typ int} the diagonal is unique only
  up to sign.

  @{theory Jordan_Normal_Form.Matrix_IArray_Impl} switches matrices from functions to arrays.
  Without it, every matrix product nests closures and recomputes earlier products on each entry
  access, so a 3 x 3 matrix takes minutes (in Isabelle's own SML evaluation too) instead of
  milliseconds.
\<close>

definition snf :: "nat \<Rightarrow> int list list \<Rightarrow> int list list \<times> int list list \<times> int list list" where
  "snf n xss = (case Smith_ED_mxn (mat_of_rows_list n xss) of
     (P, S, Q) \<Rightarrow> (mat_to_list P, mat_to_list S, mat_to_list Q))"

value "snf 2 [[1, 2], [3, 4]]"

export_code snf
  in Python module_name Smith_Ref
  file "./generated"

end
