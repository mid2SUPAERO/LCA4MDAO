import openmdao.api as om
import numpy as np
import pandas as pd
from pymoo.termination.default import DefaultSingleObjectiveTermination, DefaultMultiObjectiveTermination
from pymoo.termination.ftol import MultiObjectiveSpaceTermination

from optimizer.pymoo_optimizer import PymooDriver
from sellar import SellarDis1, SellarDis2
from lca import GWP
from database import setup_ecoinvent, build_data


class SellarMDALCA(om.Group):
    """
    Group containing the Sellar MDA.
    """

    def setup(self):
        cycle = self.add_subsystem('cycle', om.Group(), promotes=['*'])
        cycle.add_subsystem('d1', SellarDis1(), promotes_inputs=['x', 'z', 'y2'],
                            promotes_outputs=['y1'])
        cycle.add_subsystem('d2', SellarDis2(), promotes_inputs=['z', 'y1'],
                            promotes_outputs=['y2'])

        cycle.set_input_defaults('x', 1.0)
        cycle.set_input_defaults('z', np.array([5.0, 2.0]))

        # Nonlinear Block Gauss Seidel is a gradient free solver
        cycle.nonlinear_solver = om.NonlinearBlockGS()

        self.add_subsystem('obj_cmp', om.ExecComp('obj = x**2 + z[1] + y1 + exp(-y2)',
                                                  z=np.array([0.0, 0.0]), x=0.0),
                           promotes=['x', 'z', 'y1', 'y2', 'obj'])

        self.add_subsystem('con_cmp1', om.ExecComp('con1 = 3.16 - y1'), promotes=['con1', 'y1'])
        self.add_subsystem('con_cmp2', om.ExecComp('con2 = y2 - 24.0'), promotes=['con2', 'y2'])
        self.add_subsystem('lca', GWP(), promotes=['y1', 'y2', 'GWP'])


def compute(objective1='obj', objective2='GWP', constraint=None):
    prob = om.Problem()
    prob.model = SellarMDALCA()

    prob.driver = om.ScipyOptimizeDriver()
    prob.driver.options['optimizer'] = 'COBYLA'
    # prob.driver.options['maxiter'] = 100
    prob.driver.options['tol'] = 1e-8

    prob.model.add_design_var('x', lower=0, upper=10)
    prob.model.add_design_var('z', lower=0, upper=10)
    prob.model.add_objective(objective1)
    prob.model.add_constraint('con1', upper=0)
    prob.model.add_constraint('con2', upper=0)
    if constraint is not None:
        prob.model.add_constraint(objective2, upper=constraint)

    # Ask OpenMDAO to finite-difference across the model to compute the gradients for the optimizer
    prob.model.approx_totals()

    prob.setup()
    prob.set_solver_print(level=0)

    prob.run_driver()
    objective1_value = prob.get_val(objective1)[0]
    objective2_value = prob.get_val(objective2)[0]
    print(prob.get_val('x'), prob.get_val('z'))

    return objective1_value, objective2_value


def multi_objective():
    prob = om.Problem()
    prob.model = SellarMDALCA()

    prob.driver = PymooDriver()
    prob.driver.options['algorithm'] = 'NSGA2'
    prob.driver.options['termination'] = DefaultMultiObjectiveTermination(
        xtol=1e-8,
        cvtol=1e-6,
        ftol=1e-2,
        period=20,
        n_max_gen=200,
        n_max_evals=100000
    )

    prob.driver.options['verbose'] = True
    prob.driver.options['algorithm_options'] = {'pop_size': 50}

    prob.model.add_design_var('x', lower=0, upper=10)
    prob.model.add_design_var('z', lower=0, upper=10)
    prob.model.add_objective('GWP')
    prob.model.add_objective('obj')
    prob.model.add_constraint('con1', upper=0)
    prob.model.add_constraint('con2', upper=0)

    # Ask OpenMDAO to finite-difference across the model to compute the gradients for the optimizer
    prob.model.approx_totals()

    prob.setup()
    prob.set_solver_print(level=0)
    prob.run_driver()
    res = prob.driver.result
    print(res.pop.get("X"), res.opt.get("X"), res.X)
    print(res.pop.get("F"), res.opt.get("F"), res.F)

    # convert array into dataframe
    DF = pd.DataFrame(res.F)

    # save the dataframe as a csv file
    DF.to_csv("results/SellarWoodSteelPymoo.csv")


if __name__ == '__main__':
    setup_ecoinvent()
    build_data()
    # multi_objective()
    print(compute())
    print(compute(objective1='GWP', objective2='obj'))


def old_main():
    # setup_ecoinvent()
    # build_data()
    points = 50
    results = np.zeros((points, 2))
    results[0] = np.array(compute(objective1='GWP', objective2='obj'))
    results[points - 1] = np.array(compute(objective1='obj', objective2='GWP'))[::-1]
    constraints = np.linspace(results[0, 1], results[-1, 1], points)[1:-1]
    for k in range(1, points - 1):
        results[k] = np.array(compute(objective1='GWP', objective2='obj', constraint=constraints[k - 1]))
    # convert array into dataframe
    DF = pd.DataFrame(results)

    # save the dataframe as a csv file
    DF.to_csv("results/SellarWoodSteel.csv")
    print(results)


def old():
    prob = om.Problem()
    prob.model = SellarMDALCA()

    prob.driver = om.ScipyOptimizeDriver()
    prob.driver.options['optimizer'] = 'SLSQP'
    # prob.driver.options['maxiter'] = 100
    prob.driver.options['tol'] = 1e-8

    prob.model.add_design_var('x', lower=0, upper=10)
    prob.model.add_design_var('z', lower=0, upper=10)
    prob.model.add_objective('obj')
    prob.model.add_constraint('con1', upper=0)
    prob.model.add_constraint('con2', upper=0)

    # Ask OpenMDAO to finite-difference across the model to compute the gradients for the optimizer
    prob.model.approx_totals()

    prob.setup()
    prob.set_solver_print(level=0)

    prob.run_driver()

    print('minimum found at')
    print(prob.get_val('x')[0])
    print(prob.get_val('z'))

    print('minumum objective')
    print(prob.get_val('obj')[0])

    print('GWP at objective')
    print(prob.get_val('GWP')[0])

    prob = om.Problem()
    prob.model = SellarMDALCA()

    prob.driver = om.ScipyOptimizeDriver()
    prob.driver.options['optimizer'] = 'COBYLA'
    # prob.driver.options['maxiter'] = 100
    prob.driver.options['tol'] = 1e-8

    prob.model.add_design_var('x', lower=0, upper=10)
    prob.model.add_design_var('z', lower=0, upper=10)
    prob.model.add_objective('GWP')
    prob.model.add_constraint('con1', upper=0)
    prob.model.add_constraint('con2', upper=0)

    # Ask OpenMDAO to finite-difference across the model to compute the gradients for the optimizer
    prob.model.approx_totals()

    prob.setup()
    prob.set_solver_print(level=0)

    prob.run_driver()

    print('minimum found at')
    print(prob.get_val('x')[0])
    print(prob.get_val('z'))

    print('minimum GWP')
    print(prob.get_val('GWP')[0])

    print('objective at minimum GWP')
    print(prob.get_val('obj')[0])
