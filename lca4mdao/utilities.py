from warnings import warn

import brightway2 as bw

from lca4mdao.parameter import parameters, MdaoParameterManager


def setup_bw(project_name):
    bw.projects.set_current(project_name)
    bw.bw2setup()
    print(bw.projects.report())


def setup_ecoinvent(fp, name="ecoinvent", overwrite=False):
    if overwrite or bw.Database(name).random() is None:
        ei = bw.SingleOutputEcospold2Importer(fp, name)
        ei.apply_strategies()
        ei.statistics()
        ei.write_database()
    else:
        warn("ecoinvent already imported")
    return bw.Database(name)


def cleanup_parameters():
    parameters.clean_mdao_parameters()


def convert_units(lca_unit):
    unit = lca_unit
    return unit

