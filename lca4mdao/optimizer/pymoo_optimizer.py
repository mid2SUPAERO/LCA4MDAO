import numpy as np
from openmdao.core.driver import Driver
from openmdao.core.problem import Problem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.algorithms.soo.nonconvex.de import DE
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.core.problem import ElementwiseProblem
from pymoo.core.termination import Termination
from pymoo.optimize import minimize

_optimizers = {'NSGA2', 'GA', 'DE'}
_gradient_optimizers = {''}
_hessian_optimizers = {''}
_bounds_optimizers = {'NSGA2', 'GA', 'DE'}
_constraint_optimizers = {'NSGA2', 'GA', 'DE'}
_constraint_grad_optimizers = _gradient_optimizers & _constraint_optimizers
_eq_constraint_optimizers = {''}
_global_optimizers = {'NSGA2', 'GA', 'DE'}
_multi_objectives_optimizers = {'NSGA2', }

_algorithms_dict = {
    'NSGA2': NSGA2,
    'GA': GA,
    'DE': DE,
}

CITATIONS = """
@article{pymoo,
    author={J. {Blank} and K. {Deb}},
    journal={IEEE Access},
    title={pymoo: Multi-Objective Optimization in Python},
    year={2020},
    volume={8},
    number={},
    pages={89497-89509},
}"""


class OpenMDAOProblem(ElementwiseProblem):
    def __init__(self, problem: Problem, design_vars, **kwargs):
        self.problem = problem
        n_var, n_obj, n_ieq_constr, n_eq_constr, xl, xu, var_names, var_sizes, obj_names, con_names = \
            self._get_pymoo_parameters(problem, design_vars)
        super(OpenMDAOProblem, self).__init__(
            n_var=n_var,
            n_obj=n_obj,
            n_ieq_constr=n_ieq_constr,
            n_eq_constr=n_eq_constr,
            xl=xl,
            xu=xu,
            **kwargs)
        self.var_names = var_names
        self.var_sizes = var_sizes
        self.obj_names = obj_names
        self.con_names = con_names
        # print(var_names, obj_names, con_names, n_var, n_obj, n_ieq_constr)

    @staticmethod
    def _get_pymoo_parameters(problem: Problem, design_vars):
        var_names = []
        var_sizes = []
        xl = []
        xu = []
        for name, meta in design_vars.items():
            size = meta['global_size'] if meta['distributed'] else meta['size']
            var_sizes.append(size)
            meta_low = meta['lower']
            meta_high = meta['upper']
            for j in range(size):
                if isinstance(meta_low, np.ndarray):
                    p_low = meta_low[j]
                else:
                    p_low = meta_low
                if isinstance(meta_high, np.ndarray):
                    p_high = meta_high[j]
                else:
                    p_high = meta_high
                xu.append(p_high)
                xl.append(p_low)
            var_names.append(name)
        n_var = sum(var_sizes)
        objs = problem.driver.get_objective_values()
        obj_names = list(objs.keys())
        n_obj = len(obj_names)
        in_cons = problem.driver.get_constraint_values(ctype='ineq')
        eq_cons = problem.driver.get_constraint_values(ctype='eq')
        con_names = list(in_cons.keys()) + list(eq_cons.keys())
        n_ieq_constr = len(in_cons.keys())
        n_eq_constr = len(eq_cons.keys())
        xl = np.array(xl)
        xu = np.array(xu)
        return n_var, n_obj, n_ieq_constr, n_eq_constr, xl, xu, var_names, var_sizes, obj_names, con_names

    def _evaluate(self, x, out, *args, **kwargs):
        i = 0
        for size, n in zip(self.var_sizes, self.var_names):
            if size == 1:
                self.problem.set_val(n, x[i])
            else:
                self.problem.set_val(n, np.array(x[i:i + size]))
            i += size
        self.problem.run_model()
        # objectives = [self.problem.model.get_val(n) for n in self.obj_names]
        out["F"] = np.array([self.problem.model.get_val(n) for n in self.obj_names])
        if self.n_constr > 0:
            # constraints = self.problem.driver.get_constraint_values(driver_scaling=True)
            out["G"] = np.array([self.problem.model.get_val(n) for n in self.con_names])
        # print(x, out)


class PymooDriver(Driver):
    def __init__(self, **kwargs):
        """
        Initialize the PymooDriver.
        """
        super().__init__(**kwargs)

        # What we support
        self.supports['optimization'] = True
        self.supports['inequality_constraints'] = True
        self.supports['equality_constraints'] = True
        self.supports['two_sided_constraints'] = True
        self.supports['linear_constraints'] = True
        self.supports['simultaneous_derivatives'] = True
        self.supports['multiple_objectives'] = True

        # What we don't support
        self.supports['active_set'] = False
        self.supports['integer_design_vars'] = False
        self.supports['distributed_design_vars'] = False
        self.supports._read_only = True

        # The user places optimizer-specific settings in here.
        self.opt_settings = {}

        self.result = None
        self._grad_cache = None
        self._con_cache = None
        self._con_idx = {}
        self._obj_and_nlcons = None
        self._dvlist = None
        self._lincongrad_cache = None
        self.fail = False
        self.iter_count = 0
        # self._check_jac = False
        self._exc_info = None
        self._total_jac_format = 'array'

        self.cite = CITATIONS

    def _declare_options(self):
        """
        Declare options before kwargs are processed in the init method.
        """
        self.options.declare('algorithm', 'NSGA2', values=_optimizers,
                             desc='Name of algorithm to use')
        self.options.declare('algorithm_options', dict(), types=dict,
                             desc='Option dictionary to be passed to the Algorithm')
        self.options.declare('termination', None, types=(tuple, Termination),
                             desc='Option dictionary to be passed to the Algorithm')
        # self.options.declare('tol', 1.0e-6, lower=0.0,
        #                      desc='Tolerance for termination. For detailed '
        #                           'control, use solver-specific options.')
        # self.options.declare('maxiter', 200, lower=0,
        #                      desc='Maximum number of iterations.')
        self.options.declare('verbose', False, types=bool,
                             desc='Set to False to prevent printing of Pymoo convergence messages')
        # self.options.declare('singular_jac_behavior', default='warn',
        #                      values=['error', 'warn', 'ignore'],
        #                      desc='Defines behavior of a zero row/col check after first call to'
        #                           'compute_totals:'
        #                           'error - raise an error.'
        #                           'warn - raise a warning.'
        #                           "ignore - don't perform check.")
        # self.options.declare('singular_jac_tol', default=1e-16,
        #                      desc='Tolerance for zero row/column check.')

    def _get_name(self):
        """
        Get name of current optimizer.

        Returns
        -------
        str
            The name of the current optimizer.
        """
        return "Pymoo_" + self.options['algorithm']

    def _setup_driver(self, problem):
        """
        Prepare the driver for execution.

        This is the final thing to run during setup.

        Parameters
        ----------
        problem : <Problem>
            Pointer
        """
        super()._setup_driver(problem)
        opt = self.options['algorithm']

        self.supports._read_only = False
        self.supports['gradients'] = opt in _gradient_optimizers
        self.supports['inequality_constraints'] = opt in _constraint_optimizers
        self.supports['two_sided_constraints'] = opt in _constraint_optimizers
        self.supports['equality_constraints'] = opt in _eq_constraint_optimizers
        self.supports['multiple_objectives'] = opt in _multi_objectives_optimizers
        self.supports._read_only = True
        # self._check_jac = self.options['singular_jac_behavior'] in ['error', 'warn']

        # Raises error if multiple objectives are not supported, but more objectives were defined.
        if not self.supports['multiple_objectives'] and len(self._objs) > 1:
            msg = '{} currently does not support multiple objectives.'
            raise RuntimeError(msg.format(self.msginfo))

    def get_driver_objective_calls(self):
        """
        Return number of objective evaluations made during a driver run.

        Returns
        -------
        int
            Number of objective evaluations made during a driver run.
        """
        if self.result and hasattr(self.result, 'nfev'):  # TODO : check pymoo API
            return self.result.nfev
        else:
            return None

    def get_driver_derivative_calls(self):
        """
        Return number of derivative evaluations made during a driver run.

        Returns
        -------
        int
            Number of derivative evaluations made during a driver run.
        """
        if self.result and hasattr(self.result, 'njev'):  # TODO : check pymoo API
            return self.result.njev
        else:
            return None

    def run(self):
        """
        Optimize the problem using selected Pymoo optimizer.

        Returns
        -------
        bool
            Failure flag; True if failed to converge, False is successful.
        """
        problem = self._problem()
        self.iter_count = 0
        self._check_for_missing_objective()

        model = problem.model

        self._con_cache = self.get_constraint_values()
        self._dvlist = list(self._designvars)

        algo = _algorithms_dict[self.options['algorithm']](**self.options['algorithm_options'])
        pymoo_problem = OpenMDAOProblem(problem, self._designvars)
        res = minimize(pymoo_problem, algo, self.options['termination'], verbose=self.options['verbose'])
        self.result = res
        # TODO Check possible conversion to nicer format
        self.fail = not res.success
        if pymoo_problem.n_obj <= 1:
            pymoo_problem.evaluate(res.X)
        return self.fail
