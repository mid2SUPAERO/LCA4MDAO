import warnings

import numpy as np
from openmdao.api import ExplicitComponent
import brightway2 as bw
from .parameter import _add_lca_parameter, parameters


class ExplicitComponentLCA(ExplicitComponent):
    def add_output(self, name, val=1.0, shape=None, units=None, lca_key=None, lca_name=None,
                   lca_units=None, lca_parent=("mdao", "functional_unit"), exchange_type="technosphere", res_units=None,
                   desc='', lower=None, upper=None, ref=1.0, ref0=0.0, res_ref=None, tags=None,
                   shape_by_conn=False, copy_shape=None, distributed=None):
        if lca_key is not None:
            if not np.isscalar(val):
                msg = '%s: The LCA option is only compatible with scalar variables'
                raise TypeError(msg % self.msginfo)
            if lca_name is None:
                lca_name = name
            if lca_units is None:
                if units is None:
                    lca_units = 'unit'
                else:
                    lca_units = units
            # TODO add unit conversion and check
            try:
                check_unit = bw.get_activity(lca_key).get('unit')
            except KeyError:
                check_unit = None
            if check_unit != lca_units:
                warnings.warn("Unit specified for the output {} ({}) differs from database entry {} ({})."
                              .format(name, lca_units, lca_key, check_unit))
            activity = bw.get_activity(lca_parent)
            for exc in activity.exchanges():
                if exc.input == lca_key:
                    exc.delete()
            activity.new_exchange(input=lca_key, amount=val, formula=lca_name, type=exchange_type).save()
            parameters.new_mdao_parameter(lca_name, val, name)
            parameters.add_exchanges_to_group("lca4mdao", activity)

        return super().add_output(name, val=val, shape=shape, units=units,
                                  res_units=res_units, desc=desc,
                                  lower=lower, upper=upper,
                                  ref=ref, ref0=ref0, res_ref=res_ref,
                                  tags=tags, shape_by_conn=shape_by_conn,
                                  copy_shape=copy_shape, distributed=distributed)
