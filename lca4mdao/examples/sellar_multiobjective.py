import numpy as np
import openmdao.api as om
from matplotlib import pyplot as plt

from pymoo.termination.default import DefaultMultiObjectiveTermination

from lca4mdao.optimizer import PymooDriver
from lca4mdao.utilities import cleanup_parameters, setup_bw
from sellar import SellarMDA, build_data

if __name__ == '__main__':
    setup_bw("Example")
    build_data()
    cleanup_parameters()
    prob = om.Problem()
    prob.model = SellarMDA()

    prob.driver = PymooDriver()
    prob.driver.options['algorithm'] = 'NSGA2'
    prob.driver.options['termination'] = DefaultMultiObjectiveTermination(
        xtol=1e-8,
        cvtol=1e-6,
        ftol=1e-3,
        period=20,
        n_max_gen=500,
        n_max_evals=100000
    )

    prob.driver.options['verbose'] = True
    prob.driver.options['algorithm_options'] = {'pop_size': 200}

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
    print('Pareto front:')
    print(res.opt.get("F"))
    print('Corresponding design varables:')
    print(res.opt.get("X"))

    results = np.array(res.opt.get("F")).T
    plt.scatter(results[0, :], results[1, :])
    ax = plt.gca()
    ax.set_xlabel(r'global warming potential impact ($kg CO_{2} eq$)')
    ax.set_ylabel(r'Sellar problem objective function')
    plt.legend()
    plt.show()
