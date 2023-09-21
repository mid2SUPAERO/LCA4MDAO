import csv
from importlib_resources import files
from warnings import warn
import brightway2 as bw
from lca4mdao.parameter import parameters

path = files('lca4mdao').joinpath('data/ecoinvent_units.csv')

with open(path, mode='r') as infile:
    reader = csv.reader(infile)
    _conversion_table = {rows[0]: rows[1] for rows in reader}


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


def cleanup_parameters(safe=True):
    parameters.clean_mdao_parameters(safe)


def configure_units(conversion_table: dict):
    global _conversion_table
    _conversion_table = conversion_table


def convert_units(lca_unit):
    if lca_unit in _conversion_table.keys():
        unit = _conversion_table[lca_unit]
    else:
        unit = lca_unit
        warn("LCA unit {} cannot be converted using the current unit conversion table.".format(lca_unit))
    return unit
