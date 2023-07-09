import brightway2 as bw
from bw2data.parameters import ActivityParameter, DatabaseParameter, ProjectParameter, Group
import pandas as pd
from peewee import IntegrityError

#### Setup
bw.projects.set_current("Example")
bw.bw2setup()
print(bw.projects.report())


def setup_ecoinvent():
    if bw.Database("ecoinvent 3.8 cutoff").random() is None:
        fp = '/home/dmsm/t.bellier/Documents/Code/BE_LCA/datasets_old'
        ei = bw.SingleOutputEcospold2Importer(fp, "ecoinvent 3.8 cutoff")
        ei.apply_strategies()
        ei.statistics()
        ei.write_database()
    else:
        print("ecoinvent 3.8 cutoff already imported")
    ecoinvent = bw.Database("ecoinvent 3.8 cutoff")
    print(ecoinvent.random())


def build_data():
    sellar = bw.Database('sellar')
    sellar.register()
    sellar.delete()

    wood = ('ecoinvent 3.8 cutoff', 'a63dd664a99c9e82c192f8c50a9b4cfb')
    steel = ('ecoinvent 3.8 cutoff', '580b7aea44c188e5958b4c6bd6ec515a')

    data = {
        ("sellar", "sellar_problem"): {
            'name': 'sellar_problem',
            'unit': 'unit',
            'location': 'GLO',
            'exchanges': [{
                'input': wood,
                'amount': 0.,
                'formula': "wood",
                'type': 'technosphere'
            }, {
                'input': steel,
                'amount': 0.,
                'formula': "steel",
                'type': 'technosphere'
            }]
        }
    }

    sellar.write(data)

    env_data = [{
        'name': 'wood',
        'amount': 0.,
    }, {
        'name': 'steel',
        'amount': 0.,
    }]

    bw.parameters.new_database_parameters(env_data, "sellar")

    for a in sellar:
        # a.new_exchange(amount=0., input=concrete, type="technosphere", formula="concrete_volume").save()

        bw.parameters.add_exchanges_to_group("lca_parameters", a)

    ActivityParameter.recalculate_exchanges("lca_parameters")


if __name__ == '__main__':
    setup_ecoinvent()
    build_data()
