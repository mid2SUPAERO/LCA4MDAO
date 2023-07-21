import numpy as np
from bw2data.parameters import Group, ActivityParameter
from openmdao.api import ExplicitComponent
import brightway2 as bw
from .parameter import MdaoParameter, parameters


class LcaCalculationComponent(ExplicitComponent):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._lca_outputs = dict()

    def add_lca_output(self, name, functional_unit, method_key, val=1.0, units=None, desc='',
                       lower=None, upper=None, ref=1.0, ref0=0.0, tags=None):
        if tags is None:
            tags = 'lca'
        elif isinstance(tags, str):
            tags = [tags, 'lca']
        elif isinstance(tags, list):
            tags.append('lca')
        elif isinstance(tags, set):
            tags.add('lca')
        else:
            raise TypeError('The tags argument should be a str, set, or list')
        self._lca_outputs[name] = (functional_unit, method_key)
        self.add_output(name, val=val, units=units, desc=desc,
                        lower=lower, upper=upper, ref=ref, ref0=ref0, tags=tags)

    def compute(self, inputs, outputs, discrete_inputs=None, discrete_outputs=None):
        with parameters.db.atomic() as _:
            for name, param in MdaoParameter.load().items():
                MdaoParameter.update(
                    amount=inputs[param["mdao_name"]][0],
                ).where(MdaoParameter.name == name).execute()
        Group.get_or_create(name='lca4mdao')[0].expire()
        MdaoParameter.recalculate_exchanges()
        for output_name in self._lca_outputs.keys():
            (functional_unit, method_key) = self._lca_outputs[output_name]
            lca = bw.LCA(functional_unit, method_key)
            lca.lci()
            lca.lcia()
            outputs[output_name] = lca.score

    def _setup_procs(self, pathname, comm, mode, prob_meta):
        super()._setup_procs(pathname, comm, mode, prob_meta)
        # TODO check dependency chain if multiple LCA modules
        for name, param in MdaoParameter.load().items():
            self.add_input(param["mdao_name"], val=param["amount"], tags='lca')
        self.declare_partials(['*'], ['*'], method='fd')

