import openmdao.api as om
import brightway2 as bw
import numpy as np
from bw2data.parameters import ActivityParameter


class GWP(om.ExplicitComponent):

    def setup(self):
        # Inputs outside the module
        self.add_input('y1', val=0.)
        self.add_input('y2', val=0.)

        # Outputs
        self.add_output('GWP', units='kg')

    def compute(self, inputs, outputs):
        y1 = inputs['y1']
        y2 = inputs['y2']
        env_data = [{
            'name': 'wood',
            'amount': y2,
        }, {
            'name': 'steel',
            'amount': y1,
        }]
        # bw.parameters.new_project_parameters(project_data)
        bw.parameters.new_database_parameters(env_data, "sellar")
        # ActivityParameter.recalculate_exchanges("project_parameters_group")
        ActivityParameter.recalculate_exchanges("lca_parameters")
        functional_unit = {("sellar", "sellar_problem"): 1}
        method_key = ('ReCiPe Midpoint (H) V1.13', 'climate change', 'GWP100')
        method = bw.methods[method_key]
        lca = bw.LCA(functional_unit, method_key)
        lca.lci()
        lca.lcia()
        outputs['GWP'] = lca.score
