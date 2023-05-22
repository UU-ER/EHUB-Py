import pandas as pd
import pickle
import numpy as np
from src.data_management.components.fit_technology_performance import perform_fitting_WT
import src.data_management as dm
import json
import os

def read_demand_data_eraa(scenario, year, climate_year):
    """
    reads demand data for respective climate year and region from TYNDP dataset

    :param str scenario: scenario to read
    :param int climate_year: climate year to read
    :param int year: year to read
    :return pandas.series demand_profile: demand profile as series
    """
    load_path = r'./cases/NorthSea/Demand_Electricity/Demand_'
    file_name = scenario + '_' + str(year) + '_ClimateYear' + str(climate_year) + '.csv'
    demand_profiles = pd.read_csv(load_path + file_name)

    return demand_profiles

def read_installed_capacity_eraa(region):
    """
    reads production profiles for respective climate year and region from ERAA dataset (year 2030).

    It adds solar, wind onshore and wind offshore respectively for the whole region.

    :param int climate_year: climate year to read
    :param str region: region to read
    :return dict capacity_factors: production profile as series
    """
    data_path = r'C:/Users/6574114/Documents/Research/EHUB-Py_Productive/cases/NorthSea/InstalledCapacity/ERAA_InstalledCapacity.xlsx'

    instcap = pd.read_excel(data_path, index_col= 2, sheet_name='Sheet1')

    Conv = {}
    RE = {}
    if instcap[region]['Nuclear'] >0:
        Conv['PowerPlant_Nuclear'] = instcap[region]['Nuclear']
    if instcap[region]['Gas'] > 0:
        Conv['PowerPlant_Gas'] = instcap[region]['Gas']
    # Conv['PowerPlant_Lignite'] = instcap[region]['Lignite']
    if instcap[region]['Hard Coal'] > 0:
        Conv['PowerPlant_Coal'] = instcap[region]['Hard Coal']
    if instcap[region]['Batteries'] > 0:
        Conv['Storage_Battery'] = instcap[region]['Batteries']
    if instcap[region]['Hydro - Pump Storage Closed Loop'] > 0:
        Conv['Storage_PumpedHydro_Closed'] = instcap[region]['Hydro - Pump Storage Closed Loop']
    RE['Wind_On'] = instcap[region]['Wind Onshore']
    RE['Wind_Of'] = instcap[region]['Wind Offshore']
    RE['PV'] = instcap[region]['Solar (Photovoltaic)']

    installed_capacities = {}
    installed_capacities['RE'] = RE
    installed_capacities['Conventional'] = Conv

    return installed_capacities


def calculate_production_profiles_offshore(offshore_nodes):
    # Get output from wind parks
    load_path = r'./data/climate_data/'
    data_path = r'./cases/NorthSea/Offshore_Parks/WindParkData.xlsx'
    park_data = pd.read_excel(data_path, sheet_name='Parks')
    park_data_2030 = park_data[park_data.YEAR <= 2030]

    # Output per transformer station (easy)
    output_per_substation = pd.DataFrame()
    for station in offshore_nodes:
        parks_at_station = park_data_2030[park_data_2030['Transformer Platform'] == station]
        output = np.zeros(8760)
        for idx in parks_at_station.index:
            name = parks_at_station['NAME'][idx]
            name = name.replace('(', '')
            name = name.replace(')', '')
            name = name.replace(' ', '_')
            load_file = load_path + name

            with open(load_file, 'rb') as handle:
                data = pickle.load(handle)

            cap_factors = perform_fitting_WT(data['dataframe'], 'WindTurbine_Offshore_11000', 0)
            cap_factors = cap_factors.coefficients['capfactor']
            output = output + cap_factors * parks_at_station['POWER_MW'][idx]
        output_per_substation[station] = output

    return output_per_substation

def read_network_data(nodes):
    data = {}

    distance = dm.create_empty_network_matrix(nodes)
    size = dm.create_empty_network_matrix(nodes)

    data_path = './cases/NorthSea/Networks/NetworkData.xlsx'
    size_matrix = pd.read_excel(data_path, index_col=0, sheet_name='NetworkSize')
    length_matrix = pd.read_excel(data_path, index_col=0, sheet_name='NetworkLength')
    type_matrix = pd.read_excel(data_path, index_col=0, sheet_name='NetworkType')

    for node1 in nodes:
        for node2 in nodes:
            if pd.isna(size_matrix[node1][node2]) and not pd.isna(size_matrix[node2][node1]):
                size_matrix[node1][node2] = size_matrix[node2][node1]
            if not pd.isna(size_matrix[node1][node2]) and pd.isna(size_matrix[node2][node1]):
                size_matrix[node2][node1] = size_matrix[node1][node2]

    for node1 in nodes:
        for node2 in nodes:
            distance.at[node1, node2] = 100
            if pd.isna(size_matrix[node1][node2]):
                size.at[node1, node2] = 0
                size.at[node2, node1] = 0
            else:
                size.at[node1, node2] = size_matrix[node1][node2]
                size.at[node2, node1] = size_matrix[node1][node2]

    data['size'] = size
    data['distance'] = distance

    return data


def write_to_technology_data(tec_data_path, year):
    tec_data_path = r'./cases/NorthSea/Technology_Data/'
    financial_data_path = r'./cases/NorthSea/Cost_Technologies/TechnologyCost.xlsx'

    financial_data = pd.read_excel(financial_data_path, sheet_name='ToModel' ,skiprows=1)
    financial_data = financial_data[financial_data['Year'] == year]

    for filename in os.listdir(tec_data_path):
        with open(os.path.join(tec_data_path, filename), 'r') as openfile:
            # Reading from json file
            tec_data = json.load(openfile)

        new_financial_data = financial_data[financial_data['Technology'] == filename.replace('.json', '')]

        tec_data['Economics']['unit_CAPEX'] = round(new_financial_data['Investment Cost'].values[0],2)
        tec_data['Economics']['OPEX_variable'] = round(new_financial_data['OPEX Variable'].values[0],3)
        tec_data['Economics']['OPEX_fixed'] = round(new_financial_data['OPEX Fixed'].values[0],3)
        tec_data['Economics']['lifetime'] = round(new_financial_data['Lifetime'].values[0],0)

        with open(os.path.join(tec_data_path, filename), 'w') as outfile:
            json.dump(tec_data, outfile, indent=2)