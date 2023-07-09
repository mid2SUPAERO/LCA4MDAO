from pyxdsm.XDSM import XDSM, OPT, SOLVER, FUNC, IFUNC, METAMODEL, IGROUP, GROUP

x = XDSM(use_sfmath=True)

x.add_system("input", OPT, r"\text{Optimizer}")
x.add_system("mda", SOLVER, r"\text{MDA}")
x.add_system("Discipline", GROUP, (r"\text{Technical}", r"\text{Disciplines}"))

x.add_system("Obj", IFUNC, (r"\text{Technical}", r"\text{Objective}"))
x.add_system("Cons", IGROUP, (r"\text{Technical}", r"\text{Constraints}"))

x.add_system("Env", METAMODEL, r"\text{LCA}")

x.add_system("EObj", IFUNC, (r"\text{Environmental}", r"\text{Objective}"))
x.add_system("ECons", IGROUP, (r"\text{Environmental}", r"\text{Constraints}"))

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
x.connect("Obj", "input", r"f_t")
x.connect("Cons", "input", r"\bar{c_t}")

x.connect("input", "Env", r"\bar{x}")
x.connect("mda", "Env", r"\bar{y}")
x.connect("Discipline", "Env", r"\bar{z}")
# x.connect("input", "EObj", r"\bar{x}")
# x.connect("mda", "EObj", r"\bar{y}")
# x.connect("input", "ECons", r"\bar{x}")
# x.connect("mda", "ECons", r"\bar{y}")
# x.connect("Discipline", "EObj", r"\bar{z}")
# x.connect("Discipline", "ECons", r"\bar{z}")

x.connect("Env", "EObj", r"\bar{y_e}")
x.connect("Env", "ECons", r"\bar{y_e}")

x.add_output("Obj", r"f_t", side="right")
x.add_output("Cons", r"\bar{c_t}", side="right")

x.add_output("EObj", r"f_e", side="right")
x.add_output("ECons", r"\bar{c_e}", side="right")

x.write("Generic_normal", build=True)


# x.connect("Discipline", "Env", r"y_1")
# x.connect("D2", "Env", r"y_2")
#
# x.write("Generic_env", build=True)
