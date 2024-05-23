# from src.model_configuration import ModelConfiguration
import src.data_preprocessing as dp
from src.energyhub import EnergyHub
import numpy as np

from src.result_management.read_results import add_values_to_summary

# Todo: save logging to a different place
# Todo: make sure create template functions dont overwrite stuff
# Todo: make it possible to add technology blocks retrospectively
# Todo: logging
# Todo: make template main file


path = "Z:/PyHub_data/TEST"

# dp.create_optimization_templates(path)
# dp.create_montecarlo_template_csv(path)
# dp.create_input_data_folder_template(path)

# dp.copy_technology_data(path, "C:/EHubversions/EHUB-Py/data")
# dp.copy_network_data(path, "C:/EHubversions/EHUB-Py/data")
# dp.load_climate_data_from_api(path)
# dp.fill_carrier_data(path, value=100, columns=['Import price', 'Import limit'], carriers=['electricity'], nodes=['node2'])

# #
pyhub = EnergyHub()
pyhub.read_data(path, start_period=1, end_period=11)
pyhub.quick_solve()

# add_values_to_summary('C:/EHubversions/EHUB-Py/userData/Summary.xlsx')

# dm.create_optimization_templates(path)
# dm.create_input_data_folder_template(path)
# data = dm.DataHandle(path)

# print(data.model_config)

# energyhub = EnergyHub(data)
# energyhub.quick_solve()
