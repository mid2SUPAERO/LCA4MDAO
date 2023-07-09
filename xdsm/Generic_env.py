from pyxdsm.XDSM import XDSM, OPT, SOLVER, FUNC, IFUNC, METAMODEL, IGROUP, GROUP

x = XDSM(use_sfmath=True)

x.add_system("input", OPT, r"\text{Optimizer}")
x.add_system("mda", SOLVER, r"\text{MDA}")
x.add_system("Discipline", GROUP, (r"\text{Technical}", r"\text{Disciplines}"))

x.add_system("Env", FUNC, r"\text{LCA}")

x.add_system("Obj", IGROUP, r"\text{Objectives}")
x.add_system("Cons", IGROUP, r"\text{Constraints}")

# x.add_system("EObj", IFUNC, (r"\text{Environmental}", r"\text{Objective}"))
# x.add_system("ECons", IGROUP, (r"\text{Environmental}", r"\text{Constraints}"))

x.add_input("input", r"\bar{x^{*}}")
x.add_input("mda",  r"\bar{y^{*}}")

# x.connect("input", "mda", r"x^{*}")
x.connect("input", "Discipline", r"\bar{x}")
x.connect("mda", "Discipline", r"\bar{y}")
x.connect("input", "Obj", r"\bar{x}")
x.connect("mda", "Obj", r"\bar{y}")
x.connect("input", "Cons", r"\bar{x}")
x.connect("mda", "Cons", r"\bar{y}")
x.connect("Discipline", "Obj", r"\bar{z}")
x.connect("Discipline", "Cons", r"\bar{z}")
x.connect("Discipline", "mda", r"\bar{y^{*}}")
x.connect("Obj", "input", r"f_t,f_e")
x.connect("Cons", "input", r"\bar{c_t},\bar{c_e}")

x.connect("input", "Env", r"\bar{x}")
x.connect("mda", "Env", r"\bar{y}")
x.connect("Discipline", "Env", r"\bar{z}")
# x.connect("input", "EObj", r"\bar{x}")
# x.connect("mda", "EObj", r"\bar{y}")
# x.connect("input", "ECons", r"\bar{x}")
# x.connect("mda", "ECons", r"\bar{y}")
# x.connect("Discipline", "EObj", r"\bar{z}")
# x.connect("Discipline", "ECons", r"\bar{z}")

x.connect("Env", "Obj", r"\bar{y_e}")
x.connect("Env", "Cons", r"\bar{y_e}")

x.add_output("Obj", r"f_t,f_e", side="right")
x.add_output("Cons", r"\bar{c_t},\bar{c_e}", side="right")

# x.add_output("EObj", r"f_e", side="right")
# x.add_output("ECons", r"\bar{c_e}", side="right")
#
# x.connect("EObj", "input", r"f_e")
# x.connect("ECons", "input", r"\bar{c_e}")

x.write("Generic_env", build=True)
