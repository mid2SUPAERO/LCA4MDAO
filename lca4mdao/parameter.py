import os

from asteval import Interpreter
from bw2data import projects, config
from bw2data.backends.peewee import ExchangeDataset
from bw2data.parameters import ParameterManager, ParameterBase, Group, databases, get_new_symbols, DatabaseParameter, \
    ActivityParameter, ProjectParameter, alter_parameter_formula, nonempty, ParameterizedExchange, GroupDependency
from bw2data.sqlite import PickleField, SubstitutableDatabase
from bw2data.utils import python_2_unicode_compatible
from bw2parameters import ParameterSet
from bw2parameters.errors import MissingName
from peewee import TextField, FloatField


@python_2_unicode_compatible
class MdaoParameter(ParameterBase):
    """Parameter set for a MDAO project. Group name is 'lca4mdao'.

    Columns:

        * name: str, unique
        * formula: str, optional
        * amount: float, optional
        * data: object, optional. Used for any other metadata.

    Note that there is no magic for reading and writing to ``data`` (unlike ``Activity`` objects) - it must be used directly.

    """
    name = TextField(index=True, unique=True)
    formula = TextField(null=True)
    amount = FloatField(null=True)
    data = PickleField(default={})

    _old_name = "'lca4mdao'"
    _new_name = "'lca4mdao'"
    _db_table = "mdaoparameter"

    def __str__(self):
        return "MDAO parameter: {}".format(self.name)

    def save(self, *args, **kwargs):
        Group.get_or_create(name='lca4mdao')[0].expire()
        super(MdaoParameter, self).save(*args, **kwargs)

    @staticmethod
    def load(group=None):
        """Return dictionary of parameter data with names as keys and ``.dict()`` as values."""

        def reformat(o):
            o = o.dict
            return (o.pop("name"), o)

        return dict([reformat(o) for o in MdaoParameter.select()])

    @staticmethod
    def static(ignored='lca4mdao', only=None):
        """Get dictionary of ``{name: amount}`` for all mdao parameters.

        ``only`` restricts returned names to ones found in ``only``. ``ignored`` included for API compatibility with other ``recalculate`` methods."""
        result = dict(MdaoParameter.select(
            MdaoParameter.name,
            MdaoParameter.amount
        ).tuples())
        if only is not None:
            result = {k: v for k, v in result.items() if k in only}
        return result

    @staticmethod
    def expired():
        """Return boolean - is this group expired?"""
        try:
            return not Group.get(name='lca4mdao').fresh
        except Group.DoesNotExist:
            return False

    @staticmethod
    def recalculate(ignored=None):
        """Recalculate all parameters.

        ``ignored`` included for API compatibility with other ``recalculate`` methods - it will really be ignored."""
        if not MdaoParameter.expired():
            return
        data = MdaoParameter.load()
        if not data:
            return
        ParameterSet(data).evaluate_and_set_amount_field()
        with parameters.db.atomic() as _:
            for key, value in data.items():
                MdaoParameter.update(
                    amount=value['amount'],
                ).where(MdaoParameter.name == key).execute()
            Group.get_or_create(name='lca4mdao')[0].freshen()
            MdaoParameter.expire_downstream('lca4mdao')

    @staticmethod
    def recalculate_exchanges():
        """Recalculate formulas for all parameterized exchanges in group ``group``."""
        if MdaoParameter.expired():
            MdaoParameter.recalculate()

        interpreter = Interpreter()
        for k, v in MdaoParameter.static().items():
            interpreter.symtable[k] = v
        # TODO: Remove uncertainty from exchanges? (from bw)
        for obj in ParameterizedExchange.select().where(
                ParameterizedExchange.group == 'lca4mdao'):
            exc = ExchangeDataset.get(id=obj.exchange)
            # databases.set_dirty(exc.get('output').database)
            exc.data['amount'] = interpreter(obj.formula)
            databases.set_dirty(exc.output_database)
            exc.save()

    @staticmethod
    def dependency_chain():
        """ Determine if ```MdaoParameter`` parameters have dependencies
        within the group.

        Returns:

        .. code-block:: python

            [
                {
                    'kind': 'mdao',
                    'group': 'lca4mdao',
                    'names': set of variables names
                }
            ]

        """
        data = MdaoParameter.load()
        if not data:
            return []

        # Parse all formulas, find missing variables
        needed = get_new_symbols(data.values())
        if not needed:
            return []

        missing = needed.difference(data)
        if missing:
            raise MissingName("The following variables aren't defined:\n{}".format("|".join(missing)))

        return [{'kind': 'mdao', 'group': 'lca4mdao', 'names': needed}]

    @staticmethod
    def is_dependency_within_group(name):  # TODO check dependency system
        own_group = next(iter(MdaoParameter.dependency_chain()), {})
        return True if name in own_group.get("names", set()) else False

    def is_deletable(self):
        """Perform a test to see if the current parameter can be deleted."""
        if MdaoParameter.is_dependency_within_group(self.name):
            return False
        # Test the project parameters
        if ProjectParameter.is_dependency_within_group(self.name):
            return False
        # Test the database parameters
        if DatabaseParameter.is_dependent_on(self.name):
            return False
        # Test activity parameters
        if ActivityParameter.is_dependent_on(self.name, "lca4mdao"):
            return False
        return True

    @classmethod
    def update_formula_parameter_name(cls, old, new):
        """ Performs an update of the formula of relevant parameters.

        NOTE: Make sure to wrap this in an .atomic() statement!
        """
        data = (
            alter_parameter_formula(p, old, new)
            for p in cls.select().where(cls.formula.contains(old))
        )
        cls.bulk_update(data, fields=[cls.formula], batch_size=50)
        Group.get_or_create(name='lca4mdao')[0].expire()

    @property
    def dict(self):
        """Parameter data as a standardized dictionary"""
        obj = nonempty({
            'name': self.name,
            'formula': self.formula,
            'amount': self.amount,
        })
        obj.update(self.data)
        return obj

    @staticmethod
    def clean():
        MdaoParameter.delete().where(True).execute()


class MdaoParameterManager(ParameterManager):
    def __init__(self):
        self.db = SubstitutableDatabase(
            os.path.join(projects.dir, "parameters.db"),
            [MdaoParameter, DatabaseParameter, ProjectParameter, ActivityParameter,
             ParameterizedExchange, Group, GroupDependency]
        )
        config.sqlite3_databases.append(("parameters.db", self.db))

    def new_mdao_parameters(self, data, overwrite=True):
        """Efficiently and correctly enter multiple parameters.

        Will overwrite existing mdao parameters with the same name, unless ``overwrite`` is false, in which case a ``ValueError`` is raised.

        ``data`` should be a list of dictionaries:

        .. code-block:: python

            [{
                'name': name of variable (unique),
                'amount': numeric value of variable (optional),
                'formula': formula in Python as string (optional),
                optional keys like uncertainty, etc. (no limitations)
            }]

        """
        potentially_non_unique_names = [ds['name'] for ds in data]
        unique_names = list(set(potentially_non_unique_names))
        assert len(unique_names) == len(potentially_non_unique_names), "Nonunique names: {}".format(
            [p for p in unique_names
             if potentially_non_unique_names.count(p) > 1]
        )

        def reformat(ds):
            return {
                'name': ds.pop('name'),
                'amount': ds.pop('amount', 0),
                'formula': ds.pop('formula', None),
                'data': ds
            }

        data = [reformat(ds) for ds in data]
        new = {o['name'] for o in data}
        existing = {o[0] for o in MdaoParameter.select(MdaoParameter.name).tuples()}

        if new.intersection(existing) and not overwrite:
            raise ValueError(
                "The following parameters already exist:\n{}".format(
                    "|".join(new.intersection(existing)))
            )

        with self.db.atomic():
            # Remove existing values
            MdaoParameter.delete().where(MdaoParameter.name << tuple(new)).execute()
            for idx in range(0, len(data), 100):
                MdaoParameter.insert_many(data[idx:idx + 100]).execute()
            Group.get_or_create(name='lca4mdao')[0].expire()
            MdaoParameter.recalculate()

    def new_mdao_parameter(self, lca_name, val=0., mdao_name=None):
        if mdao_name is None:
            mdao_name = lca_name
        data = [{
            'name': lca_name,
            'amount': val,
            'mdao_name': mdao_name,
        }]
        self.new_mdao_parameters(data, overwrite=True)

    def clean_mdao_parameters(self):
        with self.db.atomic():
            MdaoParameter.clean()

    def rename_mdao_parameter(self, parameter, new_name, update_dependencies=False):
        """ Given a parameter and a new name, safely update the parameter.

        Will raise a TypeError if the given parameter is of the incorrect type.
        Will raise a ValueError if other parameters depend on the given one
        and ``update_dependencies`` is False.

        """
        if not isinstance(parameter, MdaoParameter):
            raise TypeError("Incorrect parameter type for this method.")
        if parameter.name == new_name:
            return

        mdao = MdaoParameter.is_dependency_within_group(parameter.name)
        project = ProjectParameter.is_dependency_within_group(parameter.name)
        database = DatabaseParameter.is_dependent_on(parameter.name)
        activity = ActivityParameter.is_dependent_on(parameter.name, "project")

        if not update_dependencies and any([mdao, project, database, activity]):
            raise ValueError(
                "Parameter '{}' is used in other (downstream) formulas".format(parameter.name)
            )

        with self.db.atomic():
            # TODO check dependency system
            if project:
                ProjectParameter.update_formula_parameter_name(parameter.name, new_name)
            if database:
                DatabaseParameter.update_formula_project_parameter_name(parameter.name, new_name)
            if activity:
                ActivityParameter.update_formula_project_parameter_name(parameter.name, new_name)
            parameter.name = new_name
            parameter.save()
            self.recalculate()

    def recalculate(self):
        """Recalculate all expired mdao, project, database, and activity parameters, as well as exchanges."""
        if ProjectParameter.expired():
            ProjectParameter.recalculate()
        if MdaoParameter.expired():
            MdaoParameter.recalculate()
        for db in databases:
            if DatabaseParameter.expired(db):
                DatabaseParameter.recalculate(db)
        for obj in Group.select().where(
                Group.fresh == False):
            # Shouldn't be possible? Maybe concurrent access?
            if obj.name in databases or obj.name == 'project':
                continue
            ActivityParameter.recalculate(obj.name)
            ActivityParameter.recalculate_exchanges(obj.name)


parameters = MdaoParameterManager()
