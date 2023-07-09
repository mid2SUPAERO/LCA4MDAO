from pyxdsm.XDSM import XDSM, OPT, SOLVER, FUNC, IFUNC, METAMODEL

x = XDSM(use_sfmath=True)

# x.add_system("input", OPT, r"\text{Optimizer}")
# x.add_system("mda", SOLVER, r"\text{MDA}")
x.add_system("D1", FUNC, (r"\text{Discipline 1}", r"y_1 = z_{1}^{2}+z_2+x_1-0.2y_2"))
# x.add_system("D2", FUNC, r"\text{Discipline 2}\ \y_2=\sqrt{y_{1}}+z_1+z_2")
x.add_system("D2", FUNC, (r"\text{Discipline 2}", r"y_2=\sqrt{y_{1}}+z_1+z_2"))
x.add_system("Obj", IFUNC, (r"\text{Objective}", r"f=x^{2}+z_1+y_1+e^{-y_2}"))
x.add_system("C1", IFUNC, (r"\text{Constraint 1}", r"g_1=3.16-y_1"))
x.add_system("C2", IFUNC, (r"\text{Constraint 2}", r"g_2=y_2-24.0"))

x.connect("D1", "D2", r"y_1")
x.connect("D1", "Obj", r"y_1")
x.connect("D1", "C1", r"y_1")
x.connect("D2", "D1", r"y_2")
x.connect("D2", "Obj", r"y_2")
x.connect("D2", "C2", r"y_2")
# x.connect("T", "E", r"trajectory")

x.add_input("D1", r"x,z_1,z_2")
x.add_input("Obj", r"x,z_1")
x.add_input("D2", r"z_1,z_2")

x.add_output("Obj", r"f", side="right")
x.add_output("C1", r"g_1", side="right")
x.add_output("C2", r"g_2", side="right")
# x.add_output("T", "trajectory", side="right")
# x.add_output("T", r"n_{dyn} max", side="right")
# x.add_output("T", r"heat max", side="right")
# x.add_output("T", "apogee", side="right")
# x.add_output("T", "perigee", side="right")
x.write("Sellar_normal", build=True)

x.add_system("Env", METAMODEL, r"\text{LCA}")
x.connect("D1", "Env", r"y_1")
x.connect("D2", "Env", r"y_2")

x.add_output("Env", r"GWP", side="right")
x.write("Sellar_env", build=True)
