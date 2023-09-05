import csv
import os
import logging
import numpy as np
import brightway2 as bw
import pandas as pd
from bw2data.parameters import ActivityParameter
from matplotlib import pyplot as plt

from openmdao.api import (
    Problem,
    Group,
    ScipyOptimizeDriver,
    ExplicitComponent,
    ExecComp,
    SqliteRecorder,
    DirectSolver,
    IndepVarComp,
    NewtonSolver,
)

# imports for the airplane model itself
from openconcept.aerodynamics import PolarDrag
from openconcept.weights import TwinSeriesHybridEmptyWeight
from openconcept.propulsion import TwinSeriesHybridElectricPropulsionSystem
from openconcept.mission import FullMissionAnalysis
from openconcept.examples.aircraft_data.KingAirC90GT import data as acdata
from openconcept.utilities import AddSubtractComp, Integrator, DictIndepVarComp, LinearInterpolator, plot_trajectory
from openconcept.examples.HybridTwin import AugmentedFBObjective, SeriesHybridTwinModel

# File path for ecoinvent datasets
fp = '/home/dmsm/t.bellier/Documents/Code/BE_LCA/datasets_old'
# functional unit (may be overridden later)
functional_unit = {("aircraft", "hybrid_aircraft"): 1, ("aircraft", "hybrid_flight"): 1}
# GWP method key
method_key = ('ReCiPe Midpoint (H) V1.13', 'climate change', 'GWP100')
# Useful keys from ecoinvent
battery = ('ecoinvent 3.8 cutoff', '4d29fc61b64f4a197d0d8140c50303c1')
engine = ('ecoinvent 3.8 cutoff', '5b209277ded8cf1b79b2a1f01b01530b')
aluminium = ('ecoinvent 3.8 cutoff', 'dcda39687497d1f2dd8e2f14f0a33eb7')
electricity = ('ecoinvent 3.8 cutoff', '99f8b09ecdf1deeca9f1df809f5faf3d')
kerosene = ('ecoinvent 3.8 cutoff', 'f615134e6ac28aca9ddfa97e40d068ea')
motor = ('ecoinvent 3.8 cutoff', 'b9e213312fd98ceeb5a05e4373e4eeb4')
CO2 = ('biosphere3', 'e259263c-d1f1-449f-bb9b-73c6d0a32a00')


def setup_brightway():
    bw.projects.set_current("Example")
    bw.bw2setup()
    print(bw.projects.report())


def setup_ecoinvent():
    if bw.Database("ecoinvent 3.8 cutoff").random() is None:
        ei = bw.SingleOutputEcospold2Importer(fp, "ecoinvent 3.8 cutoff")
        ei.apply_strategies()
        ei.statistics()
        ei.write_database()
    else:
        print("ecoinvent 3.8 cutoff already imported")
    ecoinvent = bw.Database("ecoinvent 3.8 cutoff")
    print(ecoinvent.random())


def build_data():
    aircraft = bw.Database('aircraft')
    aircraft.register()
    aircraft.delete()

    env_data = {
        ("aircraft", "hybrid_aircraft"): {
            'name': 'hybrid_aircraft',
            'unit': 'unit',
            'location': 'GLO',
            'exchanges': [{
                'input': battery,
                'amount': 0.,
                'formula': "battery",
                'type': 'technosphere'
            }, {
                'input': motor,
                'amount': 0.,
                'formula': "motor",
                'type': 'technosphere'
            }, {
                'input': engine,
                'amount': 0.,
                'formula': "engine",
                'type': 'technosphere'
            }, {
                'input': aluminium,
                'amount': 0.,
                'formula': "aluminium",
                'type': 'technosphere'
            }]
        },
        ("aircraft", "hybrid_flight"): {
            'name': 'hybrid_aircraft',
            'unit': 'unit',
            'location': 'GLO',
            'exchanges': [{
                'input': electricity,
                'amount': 0.,
                'formula': "electricity",
                'type': 'technosphere'
            }, {
                'input': kerosene,
                'amount': 0.,
                'formula': "kerosene",
                'type': 'technosphere'
            }, {
                'input': CO2,
                'amount': 0.,
                'formula': "kerosene * 3.15",
                'type': 'biosphere'
            }]
        }
    }

    aircraft.write(env_data)


class GWP(ExplicitComponent):  # TODO delete when unused
    def initialize(self):
        self.options.declare("cycles", default=1000)

    def setup(self):
        # Inputs outside the module
        # self.add_input('engine_weight', val=0., units='kg')
        # self.add_input('motor_weight', val=0., units='kg')
        # self.add_input('range', units='NM')
        self.add_input('battery_weight', units='kg')
        self.add_input('structure_weight', units='kg')
        # self.add_input('electricity', val=0., units='kW * h')
        self.add_input('kerosene', units='kg')

        # Outputs
        self.add_output('GWP', units='kg')

        self.declare_partials(["GWP"], ['battery_weight', 'structure_weight', 'kerosene'], method='fd')
        # self.declare_coloring()

    def compute(self, inputs, outputs):
        # engine_weight = inputs['engine_weight']
        engine_weight = 0.
        # motor_weight = inputs['motor_weight']
        motor_weight = 0.
        battery_weight = inputs['battery_weight']
        structure_weight = inputs['structure_weight']
        # electricity = inputs['electricity']
        electricity = 0.
        kerosene = inputs['kerosene']
        cycles = self.options['cycles']
        env_data = [{
            'name': 'engine',
            'amount': engine_weight,
        }, {
            'name': 'motor',
            'amount': motor_weight,
        }, {
            'name': 'battery',
            'amount': battery_weight,
        }, {
            'name': 'aluminium',
            'amount': structure_weight,
        }, {
            'name': 'electricity',
            'amount': electricity * cycles,
        }, {
            'name': 'kerosene',
            'amount': kerosene * cycles,
        }]
        bw.parameters.new_database_parameters(env_data, "aircraft")
        ActivityParameter.recalculate_exchanges("aircraft_parameters")
        functional_unit = {("aircraft", "hybrid_aircraft"): 1, ("aircraft", "hybrid_flight"): 1}
        # functional_unit = {("aircraft", "hybrid_flight"): 1}
        method_key = ('ReCiPe Midpoint (H) V1.13', 'climate change', 'GWP100')
        lca = bw.LCA(functional_unit, method_key)
        lca.lci()
        lca.lcia()
        outputs['GWP'] = lca.score


class ElectricTwinAnalysisGroup(Group):
    """This is an example of a balanced field takeoff and three-phase mission analysis."""

    def initialize(self):
        self.options.declare("cycles", default=1000)

    def setup(self):
        # Define number of analysis points to run pers mission segment
        nn = 11

        # Define a bunch of design variables and airplane-specific parameters
        dv_comp = self.add_subsystem("dv_comp", DictIndepVarComp(acdata), promotes_outputs=["*"])
        dv_comp.add_output_from_dict("ac|aero|CLmax_TO")
        dv_comp.add_output_from_dict("ac|aero|polar|e")
        dv_comp.add_output_from_dict("ac|aero|polar|CD0_TO")
        dv_comp.add_output_from_dict("ac|aero|polar|CD0_cruise")

        dv_comp.add_output_from_dict("ac|geom|wing|S_ref")
        dv_comp.add_output_from_dict("ac|geom|wing|AR")
        dv_comp.add_output_from_dict("ac|geom|wing|c4sweep")
        dv_comp.add_output_from_dict("ac|geom|wing|taper")
        dv_comp.add_output_from_dict("ac|geom|wing|toverc")
        dv_comp.add_output_from_dict("ac|geom|hstab|S_ref")
        dv_comp.add_output_from_dict("ac|geom|hstab|c4_to_wing_c4")
        dv_comp.add_output_from_dict("ac|geom|vstab|S_ref")
        dv_comp.add_output_from_dict("ac|geom|fuselage|S_wet")
        dv_comp.add_output_from_dict("ac|geom|fuselage|width")
        dv_comp.add_output_from_dict("ac|geom|fuselage|length")
        dv_comp.add_output_from_dict("ac|geom|fuselage|height")
        dv_comp.add_output_from_dict("ac|geom|nosegear|length")
        dv_comp.add_output_from_dict("ac|geom|maingear|length")

        dv_comp.add_output_from_dict("ac|weights|MTOW")
        dv_comp.add_output_from_dict("ac|weights|W_fuel_max")
        dv_comp.add_output_from_dict("ac|weights|MLW")
        dv_comp.add_output_from_dict("ac|weights|W_battery")

        dv_comp.add_output_from_dict("ac|propulsion|engine|rating")
        dv_comp.add_output_from_dict("ac|propulsion|propeller|diameter")
        dv_comp.add_output_from_dict("ac|propulsion|generator|rating")
        dv_comp.add_output_from_dict("ac|propulsion|motor|rating")
        dv_comp.add_output("ac|propulsion|battery|specific_energy", val=300, units="W*h/kg")

        dv_comp.add_output_from_dict("ac|num_passengers_max")
        dv_comp.add_output_from_dict("ac|q_cruise")
        dv_comp.add_output_from_dict("ac|num_engines")

        mission_data_comp = self.add_subsystem("mission_data_comp", IndepVarComp(), promotes_outputs=["*"])
        mission_data_comp.add_output("batt_soc_target", val=0.1, units=None)

        self.add_subsystem(
            "analysis",
            FullMissionAnalysis(num_nodes=nn, aircraft_model=SeriesHybridTwinModel),
            promotes_inputs=["*"],
            promotes_outputs=["*"],
        )

        self.add_subsystem(
            "margins",
            ExecComp(
                "MTOW_margin = MTOW - OEW - total_fuel - W_battery - payload",
                MTOW_margin={"units": "lbm", "val": 100},
                MTOW={"units": "lbm", "val": 10000},
                OEW={"units": "lbm", "val": 5000},
                total_fuel={"units": "lbm", "val": 1000},
                W_battery={"units": "lbm", "val": 1000},
                payload={"units": "lbm", "val": 1000},
            ),
            promotes_inputs=["payload"],
        )
        self.connect("cruise.OEW", "margins.OEW")
        self.connect("descent.fuel_used_final", "margins.total_fuel")
        self.connect("ac|weights|MTOW", "margins.MTOW")
        self.connect("ac|weights|W_battery", "margins.W_battery")

        self.add_subsystem("aug_obj", AugmentedFBObjective(), promotes_outputs=["mixed_objective"])
        self.connect("ac|weights|MTOW", "aug_obj.ac|weights|MTOW")
        self.connect("descent.fuel_used_final", "aug_obj.fuel_burn")

        self.add_subsystem('lca', GWP(cycles=self.options["cycles"]), promotes_outputs=["GWP"])
        # self.connect("", "lca.engine")
        # self.connect("", "lca.motor")
        self.connect("ac|weights|W_battery", "lca.battery_weight")
        self.connect("cruise.OEW", "lca.structure_weight")
        # self.connect("", "lca.electricity")
        self.connect("descent.fuel_used_final", "lca.kerosene")


def plot_trajectory_compact(
        prob, x_var, x_unit, y_vars, y_units, phases, x_label=None, y_labels=None, marker="o", plot_title="Trajectory",
        file=None,
):
    val_list = []
    for phase in phases:
        val_list.append(prob.get_val(phase + "." + x_var, units=x_unit))
    x_vec = np.concatenate(val_list)

    fig, axes = plt.subplots(len(y_vars), 1, sharex=True, figsize=(6.4, len(y_vars) * 1.6))

    for i, y_var in enumerate(y_vars):
        val_list = []
        for phase in phases:
            val_list.append(prob.get_val(phase + "." + y_var, units=y_units[i]))
        y_vec = np.concatenate(val_list)
        axes[i].plot(x_vec, y_vec, marker)
        if y_labels is not None:
            if y_labels[i] is not None:
                axes[i].set_ylabel(y_labels[i])
        else:
            axes[i].set_ylabel(y_var)
    if plot_title:
        plt.title(plot_title)
    if x_label is None:
        plt.xlabel(x_var)
    else:
        plt.xlabel(x_label)
    if file is not None:
        plt.savefig(file)
    plt.show()


def configure_problem():
    prob = Problem()
    prob.model = ElectricTwinAnalysisGroup()
    prob.model.nonlinear_solver = NewtonSolver(iprint=1)
    prob.model.options["assembled_jac_type"] = "csc"
    prob.model.linear_solver = DirectSolver(assemble_jac=True)
    prob.model.nonlinear_solver.options["solve_subsystems"] = True
    prob.model.nonlinear_solver.options["maxiter"] = 10
    prob.model.nonlinear_solver.options["atol"] = 1e-7
    prob.model.nonlinear_solver.options["rtol"] = 1e-7
    return prob


def set_values(prob, num_nodes, design_range, spec_energy):
    # set some (required) mission parameters. Each pahse needs a vertical and air-speed
    # the entire mission needs a cruise altitude and range
    prob.set_val("climb.fltcond|vs", np.ones((num_nodes,)) * 1500, units="ft/min")
    prob.set_val("climb.fltcond|Ueas", np.ones((num_nodes,)) * 124, units="kn")
    prob.set_val("cruise.fltcond|vs", np.ones((num_nodes,)) * 0.01, units="ft/min")
    prob.set_val("cruise.fltcond|Ueas", np.ones((num_nodes,)) * 170, units="kn")
    prob.set_val("descent.fltcond|vs", np.ones((num_nodes,)) * (-600), units="ft/min")
    prob.set_val("descent.fltcond|Ueas", np.ones((num_nodes,)) * 140, units="kn")

    prob.set_val("cruise|h0", 29000, units="ft")
    prob.set_val("mission_range", design_range, units="NM")
    prob.set_val("payload", 1000, units="lb")
    prob.set_val("ac|propulsion|battery|specific_energy", spec_energy, units="W*h/kg")

    # (optional) guesses for takeoff speeds may help with convergence
    prob.set_val("v0v1.fltcond|Utrue", np.ones((num_nodes)) * 50, units="kn")
    prob.set_val("v1vr.fltcond|Utrue", np.ones((num_nodes)) * 85, units="kn")
    prob.set_val("v1v0.fltcond|Utrue", np.ones((num_nodes)) * 85, units="kn")

    # set some airplane-specific values
    prob["analysis.cruise.acmodel.OEW.const.structural_fudge"] = 2.0
    prob["ac|propulsion|propeller|diameter"] = 2.2
    prob["ac|propulsion|engine|rating"] = 1117.2

    # hybridization values
    prob["cruise.hybridization"] = 0.05840626452293813
    prob["climb.hybridization"] = 0.05840626452293813
    prob["descent.hybridization"] = 0.05840626452293813


def run_hybrid_twin_analysis(plots=False):
    prob = configure_problem()
    prob.setup(check=False)
    prob["cruise.hybridization"] = 0.05840626452293813
    set_values(prob, 11, 500, 450)
    prob.run_model()
    if plots:
        show_outputs(prob)
    return prob


def show_outputs(prob, plots=False):
    # print some outputs
    vars_list = [
        "ac|weights|MTOW",
        "climb.OEW",
        "descent.fuel_used_final",
        "rotate.range_final",
        "descent.propmodel.batt1.SOC_final",
        "cruise.hybridization",
        "climb.hybridization",
        "descent.hybridization",
        "ac|weights|W_battery",
        "margins.MTOW_margin",
        "ac|propulsion|motor|rating",
        "ac|propulsion|generator|rating",
        "ac|propulsion|engine|rating",
        "ac|geom|wing|S_ref",
        "v0v1.Vstall_eas",
        "v0v1.takeoff|vr",
        "engineoutclimb.gamma",
        "GWP",
    ]
    units = ["lb", "lb", "lb", "ft", None, None, None, None, "lb", "lb", "hp", "hp", "hp", "ft**2", "kn", "kn", "deg",
             "kg"]
    nice_print_names = [
        "MTOW",
        "OEW",
        "Fuel used",
        "TOFL (over 35ft obstacle)",
        "Final state of charge",
        "Cruise hybridization",
        "Climb hybridization",
        "Descent hybridization",
        "Battery weight",
        "MTOW margin",
        "Motor rating",
        "Generator rating",
        "Engine rating",
        "Wing area",
        "Stall speed",
        "Rotate speed",
        "Engine out climb angle",
        "GWP",
    ]
    print("=======================================================================")
    for i, thing in enumerate(vars_list):
        print(nice_print_names[i] + ": " + str(prob.get_val(thing, units=units[i])[0]) + " " + str(units[i]))

    # plot some stuff

    if plots:
        x_var = "range"
        x_unit = "NM"
        y_vars = ["fltcond|h", "fltcond|Ueas", "fuel_used", "throttle", "fltcond|vs", "propmodel.batt1.SOC"]
        y_units = ["ft", "kn", "lbm", None, "ft/min", None]
        x_label = "Range (nmi)"
        y_labels = [
            "Altitude (ft)",
            "Veas airspeed (knots)",
            "Fuel used (lb)",
            "Throttle setting",
            "Vertical speed (ft/min)",
            "Battery SOC",
        ]
        y_vars = ["fltcond|h", "throttle", "fuel_used", "propmodel.batt1.SOC"]
        y_units = ["ft", None, "kg", None]
        x_label = r"range (NM)"
        y_labels = [
            r"altitude (ft)",
            r"throttle setting",
            r"fuel used (kg)",
            r"battery SOC",
        ]
        phases = ["v0v1", "v1vr", "v1v0", "rotate"]
        # plot_trajectory(
        #     prob,
        #     x_var,
        #     x_unit,
        #     y_vars,
        #     y_units,
        #     phases,
        #     x_label=x_label,
        #     y_labels=y_labels,
        #     marker="-",
        #     plot_title="Takeoff Profile",
        # )

        phases = ["v0v1", "v1vr", "v1v0", "rotate", "climb", "cruise", "descent"]
        phases = ["rotate", "climb", "cruise", "descent"]

        if isinstance(plots, str):
            plot_trajectory_compact(
                prob,
                x_var,
                x_unit,
                y_vars,
                y_units,
                phases,
                x_label=x_label,
                y_labels=y_labels,
                marker="-",
                plot_title=None,
                file=plots
            )
        else:
            plot_trajectory_compact(
                prob,
                x_var,
                x_unit,
                y_vars,
                y_units,
                phases,
                x_label=x_label,
                y_labels=y_labels,
                marker="-",
                plot_title="Full Mission Profile",
            )


if __name__ == "__main__":
    setup_brightway()
    setup_ecoinvent()
    build_data()
    # for run type choose choose optimization, comp_sizing, or analysis
    # run_type = "example"
    run_type = "optimization"
    num_nodes = 11
    # plots = "reports/traj_400.png"
    plots = None
    # save_file = "reports/400_bis.csv"
    save_file = None
    save_final_design = "reports/design.csv"

    if run_type == "example":
        # runs a default analysis-only mission (no optimization)
        run_hybrid_twin_analysis(plots=plots)

    else:
        # can run a sweep of design range and spec energy (not tested)
        # design_ranges = [300, 350, 400, 450, 500]
        # specific_energies = [250,300,350,400,450,500,550,600,650,700,750,800]

        # or a single point
        design_ranges = [300, 400, 500]
        specific_energies = [450]
        # design_ranges = np.linspace(150, 300, 20)
        GWP_results = []
        cruise_hybrid = []
        bad_ranges = []
        good_ranges = []

        designs = []

        write_logs = False
        if write_logs:
            logging.basicConfig(filename="opt.log", filemode="w", format="%(name)s - %(levelname)s - %(message)s")
        # run a sweep of cases at various specific energies and ranges
        for design_range in design_ranges:
            for this_spec_energy in specific_energies:
                try:
                    prob = configure_problem()
                    spec_energy = this_spec_energy
                    if run_type == "optimization":
                        print("======Performing Multidisciplinary Design Optimization===========")
                        prob.model.add_design_var("ac|weights|MTOW", lower=4000, upper=5700)
                        prob.model.add_design_var("ac|geom|wing|S_ref", lower=15, upper=40)
                        prob.model.add_design_var("ac|propulsion|engine|rating", lower=1, upper=3000)
                        prob.model.add_design_var("ac|propulsion|motor|rating", lower=450, upper=3000)
                        prob.model.add_design_var("ac|propulsion|generator|rating", lower=1, upper=3000)
                        prob.model.add_design_var("ac|weights|W_battery", lower=20, upper=2250)
                        prob.model.add_design_var("ac|weights|W_fuel_max", lower=500, upper=3000)
                        prob.model.add_design_var("cruise.hybridization", lower=0.001, upper=0.999)
                        prob.model.add_design_var("climb.hybridization", lower=0.001, upper=0.999)
                        prob.model.add_design_var("descent.hybridization", lower=0.01, upper=1.0)

                        prob.model.add_constraint("margins.MTOW_margin", lower=0.0)
                        prob.model.add_constraint("rotate.range_final", upper=1357)
                        prob.model.add_constraint("v0v1.Vstall_eas", upper=42.0)
                        prob.model.add_constraint("descent.propmodel.batt1.SOC_final", lower=0.0)
                        prob.model.add_constraint("climb.throttle", upper=1.05 * np.ones(num_nodes))
                        prob.model.add_constraint(
                            "climb.propmodel.eng1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "climb.propmodel.gen1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "climb.propmodel.batt1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "cruise.propmodel.eng1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "cruise.propmodel.gen1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "cruise.propmodel.batt1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "descent.propmodel.eng1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "descent.propmodel.gen1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "descent.propmodel.batt1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "v0v1.propmodel.batt1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint("engineoutclimb.gamma", lower=0.02)
                        # prob.model.add_objective("GWP", units='kg')
                        prob.model.add_objective("mixed_objective")  # TODO add this objective

                    elif run_type == "comp_sizing":
                        print("======Performing Component Sizing Optimization===========")
                        prob.model.add_design_var("ac|propulsion|engine|rating", lower=1, upper=3000)
                        prob.model.add_design_var("ac|propulsion|motor|rating", lower=1, upper=3000)
                        prob.model.add_design_var("ac|propulsion|generator|rating", lower=1, upper=3000)
                        prob.model.add_design_var("ac|weights|W_battery", lower=20, upper=2250)
                        prob.model.add_design_var("cruise.hybridization", lower=0.01, upper=0.5)

                        prob.model.add_constraint("margins.MTOW_margin", equals=0.0)  # TODO implement
                        prob.model.add_constraint("rotate.range_final", upper=1357)  # TODO check units
                        prob.model.add_constraint("descent.propmodel.batt1.SOC_final", lower=0.0)
                        prob.model.add_constraint(
                            "v0v1.propmodel.eng1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "v0v1.propmodel.gen1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "v0v1.propmodel.batt1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "climb.propmodel.eng1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "climb.propmodel.gen1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint(
                            "climb.propmodel.batt1.component_sizing_margin", upper=1.0 * np.ones(num_nodes)
                        )
                        prob.model.add_constraint("climb.throttle", upper=1.05 * np.ones(num_nodes))
                        prob.model.add_objective("fuel_burn")

                    else:
                        print("======Analyzing Fuel Burn for Given Mision============")
                        prob.model.add_design_var("cruise.hybridization", lower=0.01, upper=0.5)
                        prob.model.add_constraint("descent.propmodel.batt1.SOC_final", lower=0.0)
                        prob.model.add_objective("descent.fuel_used_final")

                    prob.driver = ScipyOptimizeDriver()
                    if write_logs:
                        filename_to_save = "case_" + str(spec_energy) + "_" + str(design_range) + ".sql"
                        if os.path.isfile(filename_to_save):
                            print("Skipping " + filename_to_save)
                            continue
                        recorder = SqliteRecorder(filename_to_save)
                        prob.driver.add_recorder(recorder)
                        prob.driver.recording_options["includes"] = []
                        prob.driver.recording_options["record_objectives"] = True
                        prob.driver.recording_options["record_constraints"] = True
                        prob.driver.recording_options["record_desvars"] = True

                    prob.setup(check=False)
                    set_values(prob, num_nodes, design_range, spec_energy)

                    run_flag = prob.run_driver()

                    if run_flag:
                        bad_ranges.append(design_range)
                    else:
                        good_ranges.append(design_range)
                        GWP_results.append(prob.get_val("GWP", units='kg')[0])
                        cruise_hybrid.append(prob.get_val("cruise.hybridization")[0])
                        # raise ValueError("Opt failed")

                    if save_final_design:
                        design = prob.driver.get_design_var_values()
                        designs.append(design)

                except BaseException as e:
                    if write_logs:
                        logging.error("Optimization " + filename_to_save + " failed because " + repr(e))
                    prob.cleanup()
                    try:
                        os.rename(filename_to_save, filename_to_save.split(".sql")[0] + "_failed.sql")
                    except WindowsError as we:
                        if write_logs:
                            logging.error("Error renaming file: " + repr(we))
                        os.remove(filename_to_save)

        show_outputs(prob, plots=plots)
        data = pd.DataFrame({"range": good_ranges, "GWP": GWP_results, "hybridisation": cruise_hybrid})
        if save_file:
            data.to_csv(save_file)
        if save_final_design:
            with open(save_final_design, 'w+') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=designs[0].keys())
                writer.writeheader()
                writer.writerows(designs)
        print(k for k in bw.Database('aircraft').search('*'))
        data.plot.scatter(x="GWP", y="range", c="hybridisation")
        plt.show()
