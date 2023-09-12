from pyomo.environ import *
from pyomo.gdp import *
import src.global_variables as global_variables
import src.model_construction as mc


def constraints_tec_ocean_battery(b_tec, tec_data, energyhub):
    """
    Adds constraints to technology blocks for tec_type STOR, resembling a storage technology

    The performance
    functions are fitted in ``src.model_construction.technology_performance_fitting``.
    Note that this technology only works for one carrier, and thus the carrier index is dropped in the below notation.

    **Parameter declarations:**

    - :math:`{\\eta}_{in}`: Charging efficiency

    - :math:`{\\eta}_{out}`: Discharging efficiency

    - :math:`{\\lambda_1}`: Self-Discharging coefficient (independent of environment)

    - :math:`{\\lambda_2(\\Theta)}`: Self-Discharging coefficient (dependent on environment)

    - :math:`Input_{max}`: Maximal charging capacity in one time-slice

    - :math:`Output_{max}`: Maximal discharging capacity in one time-slice

    **Variable declarations:**

    - Storage level in :math:`t`: :math:`E_t`

    - Charging in in :math:`t`: :math:`Input_{t}`

    - Discharging in in :math:`t`: :math:`Output_{t}`

    **Constraint declarations:**

    - Maximal charging and discharging:

      .. math::
        Input_{t} \leq Input_{max}

      .. math::
        Output_{t} \leq Output_{max}

    - Size constraint:

      .. math::
        E_{t} \leq S

    - Storage level calculation:

      .. math::
        E_{t} = E_{t-1} * (1 - \\lambda_1) - \\lambda_2(\\Theta) * E_{t-1} + {\\eta}_{in} * Input_{t} - 1 / {\\eta}_{out} * Output_{t}

    - If ``allow_only_one_direction == 1``, then only input or output can be unequal to zero in each respective time
      step (otherwise, simultanous charging and discharging can lead to unwanted 'waste' of energy/material).

    :param obj model: instance of a pyomo model
    :param obj b_tec: technology block
    :param tec_data: technology data
    :return: technology block
    """
    model = energyhub.model

    # DATA OF TECHNOLOGY
    performance_data = tec_data.performance_data
    coeff = tec_data.fitted_performance.coefficients

    # Abdditional parameters
    eta_in = coeff['eta_in']
    eta_out = coeff['eta_out']
    eta_lambda = coeff['lambda']
    charge_max = coeff['charge_max']
    discharge_max = coeff['discharge_max']
    min_fill  = coeff['min_fill']
    pump_slots = coeff['pump_slots']
    turbine_slots = coeff['turbine_slots']

    # Full resolution
    input = b_tec.var_input
    output = b_tec.var_output
    set_t = model.set_t_full

    nr_timesteps_averaged = global_variables.averaged_data_specs.nr_timesteps_averaged

    # Additional sets
    b_tec.set_pump_slots = RangeSet(pump_slots)
    b_tec.set_turbine_slots = RangeSet(turbine_slots)

    # Additional decision variables
    b_tec.var_storage_level = Var(set_t,
                                  domain=NonNegativeReals,
                                  bounds=(b_tec.para_size_min, b_tec.para_size_max))
    b_tec.var_total_inflow = Var(set_t,
                                  domain=NonNegativeReals,
                                  bounds=(b_tec.para_size_min, b_tec.para_size_max))
    b_tec.var_total_outflow = Var(set_t,
                                 domain=NonNegativeReals,
                                 bounds=(b_tec.para_size_min, b_tec.para_size_max))

    # Fill constraints
    def init_size_constraint_up(const, t):
        return b_tec.var_storage_level[t] <= b_tec.var_size
    b_tec.const_size_up = Constraint(set_t, rule=init_size_constraint_up)

    def init_size_constrain_low(const, t):
        return b_tec.var_storage_level[t] >= min_fill * b_tec.var_size
    b_tec.const_size_low = Constraint(set_t, rule=init_size_constrain_low)

    # Storage level calculation
    def init_storage_level(const, t, car):
        if t == 1:  # couple first and last time interval
            return b_tec.var_storage_level[t] == \
                   b_tec.var_storage_level[max(set_t)] * (1 - eta_lambda) ** nr_timesteps_averaged + \
                   (b_tec.var_total_inflow[t] - b_tec.var_total_outflow[t]) * \
                   sum((1 - eta_lambda) ** i for i in range(0, nr_timesteps_averaged))
        else:  # all other time intervals
            return b_tec.var_storage_level[t] == \
                   b_tec.var_storage_level[t - 1] * (1 - eta_lambda) ** nr_timesteps_averaged + \
                   (b_tec.var_total_inflow[t] - b_tec.var_total_outflow[t]) * \
                   sum((1 - eta_lambda) ** i for i in range(0, nr_timesteps_averaged))

    b_tec.const_storage_level = Constraint(set_t, b_tec.set_input_carriers, rule=init_storage_level)

    def pumps_block_init(b_pump):
        """

        """
        # Parameters
        b_pump.para_size_min = Param(initialize=0)
        b_pump.para_size_max = Param(initialize=10)
        b_pump.para_capex = Param(initialize=5)

        # Decision Variables
        b_pump.var_size = Var(domain=NonNegativeReals,
                             bounds=(b_pump.para_size_min, b_pump.para_size_max))
        b_pump.var_input = Var(set_t, domain=NonNegativeReals,
                             bounds=(b_pump.para_size_min, b_pump.para_size_max))
        b_pump.var_inflow = Var(set_t, domain=NonNegativeReals,
                             bounds=(b_pump.para_size_min, b_pump.para_size_max))

        # THIS NEEDS TO BE FIXED
        b_pump.var_capex = Var(domain=NonNegativeReals, bounds=(0, b_pump.para_size_max*100))

        pump_types = range(0, 3)
        global_variables.big_m_transformation_required = 1

        def init_pump_types(dis, type):
            if type == 0:  # slot not used
                def init_inflow(const, t):
                    return b_pump.var_input[t] == 0
                dis.const_inflow = Constraint(set_t, rule=init_inflow)

                def init_pump_efficiency(const, t):
                    return b_pump.var_inflow[t] == 0
                dis.const_pump_efficiency = Constraint(set_t, rule=init_pump_efficiency)

                dis.const_size = Constraint(expr= b_pump.var_size == 0)
                dis.const_capex = Constraint(expr= b_pump.var_capex == 0)

            elif type == 1:  # type 1
                def init_inflow(const, t):
                    return b_pump.var_inflow[t] <= b_pump.var_size
                dis.const_inflow = Constraint(set_t, rule=init_inflow)

                def init_pump_efficiency(const, t, car):
                    return 0.99 * b_pump.var_inflow[t] == b_pump.var_input[t]
                dis.const_pump_efficiency = Constraint(set_t, b_tec.set_input_carriers, rule=init_pump_efficiency)

                dis.const_capex = Constraint(expr=b_pump.var_size * b_pump.para_capex == b_pump.var_capex)


            elif type == 2:  # type 2
                def init_inflow(const, t):
                    return b_pump.var_inflow[t] <= b_pump.var_size
                dis.const_inflow = Constraint(set_t, rule=init_inflow)

                def init_pump_efficiency(const, t, car):
                    return 0.7 * b_pump.var_inflow[t] == b_pump.var_input[t]
                dis.const_pump_efficiency = Constraint(set_t, b_tec.set_input_carriers, rule=init_pump_efficiency)

                dis.const_capex = Constraint(expr=b_pump.var_size * b_pump.para_capex * 0.8 == b_pump.var_capex)

        b_pump.dis_pump_types = Disjunct(pump_types, rule=init_pump_types)

        # Bind disjuncts
        def bind_disjunctions(dis):
            return [b_pump.dis_pump_types[i] for i in pump_types]
        b_pump.disjunction_pump_types = Disjunction(rule=bind_disjunctions)

        if global_variables.big_m_transformation_required:
            mc.perform_disjunct_relaxation(b_pump)

    b_tec.pump_block = Block(b_tec.set_pump_slots, rule=pumps_block_init)

    def turbines_block_init(b_turbine):
        """

        """
        # Parameters
        b_turbine.para_size_min = Param(initialize=0)
        b_turbine.para_size_max = Param(initialize=10)
        b_turbine.para_capex = Param(initialize=2)

        # Decision Variables
        b_turbine.var_size = Var(domain=NonNegativeReals,
                              bounds=(b_turbine.para_size_min, b_turbine.para_size_max))
        b_turbine.var_output = Var(set_t, domain=NonNegativeReals,
                               bounds=(b_turbine.para_size_min, b_turbine.para_size_max))
        b_turbine.var_outflow = Var(set_t, domain=NonNegativeReals,
                                bounds=(b_turbine.para_size_min, b_turbine.para_size_max))
        b_turbine.var_capex = Var(domain=NonNegativeReals)

        def init_inflow(const, t):
            return b_turbine.var_outflow[t] <= b_turbine.var_size
        b_turbine.const_inflow = Constraint(set_t, rule=init_inflow)

        def init_turbine_efficiency(const, t):
            return 0.8 * b_turbine.var_outflow[t] == b_turbine.var_output[t]
        b_turbine.const_turbine_efficiency = Constraint(set_t, rule=init_turbine_efficiency)

        b_turbine.const_capex = Constraint(expr=b_turbine.var_size * b_turbine.para_capex == b_turbine.var_capex)

        # if global_variables.big_m_transformation_required:
        #     mc.perform_disjunct_relaxation(b_turbine)

    b_tec.turbine_block = Block(b_tec.set_turbine_slots, rule=turbines_block_init)

    # Aggregate Input/Output
    def init_total_input(const, t, car):
        return b_tec.var_input[t, car] == \
               sum(b_tec.pump_block[pump].var_input[t] for pump in b_tec.set_pump_slots)
    b_tec.const_total_input = Constraint(set_t, b_tec.set_input_carriers, rule=init_total_input)

    def init_total_output(const, t, car):
        return b_tec.var_output[t, car] == \
               sum(b_tec.turbine_block[turbine].var_output[t] for turbine in b_tec.set_turbine_slots)
    b_tec.const_total_output = Constraint(set_t, b_tec.set_input_carriers, rule=init_total_output)

    def init_total_inflow(const, t):
        return b_tec.var_total_inflow[t] == \
               sum(b_tec.pump_block[pump].var_inflow[t] for pump in b_tec.set_pump_slots)
    b_tec.const_total_inflow = Constraint(set_t, rule=init_total_inflow)

    def init_total_outflow(const, t):
        return b_tec.var_total_outflow[t] == \
               sum(b_tec.turbine_block[turbine].var_outflow[t] for turbine in b_tec.set_turbine_slots)
    b_tec.const_total_outflow = Constraint(set_t, rule=init_total_outflow)


    # CAPEX Calculation
    b_tec.const_capex_aux = Constraint(expr= 10 * b_tec.var_size +
                                             sum(b_tec.turbine_block[turbine].var_capex for turbine in b_tec.set_turbine_slots) +
                                             sum(b_tec.pump_block[pump].var_capex for pump in b_tec.set_pump_slots) ==
                                             b_tec.var_capex_aux)

    return b_tec