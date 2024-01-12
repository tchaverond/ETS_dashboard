import geopandas as gpd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from matplotlib import pyplot as plt
import pandas as pd



GEOLOC_PATH = "data/geoloc_cities.csv"
EXISTING_DATA_PATH = "data/consolidated.csv"
SAMPLE_DATA_PATH = "data/sample.csv"
BACKGROUND_PATH = "data/NUTS_RG_20M_2021_4326.shp.zip"
EUROPE_LIMIT_COORDS = [-12, 30, 35, 65]


def load_geoloc():
    return pd.read_csv(GEOLOC_PATH)


def load_existing_data():
    try:
        return pd.read_csv(EXISTING_DATA_PATH, parse_dates=[20])
    except FileNotFoundError:
        return pd.read_csv(SAMPLE_DATA_PATH, parse_dates=[20])


def initialize_background():
    bg = gpd.read_file(BACKGROUND_PATH)
    return bg[bg['LEVL_CODE'] == 0].clip(EUROPE_LIMIT_COORDS)


def geoloc_unknown_cities(cities):
    
    geolocator = Nominatim(user_agent="ets-dashboard")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1)

    geoloc_out = pd.DataFrame(cities, columns=['City'])
    all_lats = []
    all_lons = []
    for city in cities:
        loc = geocode(city)
        all_lats.append(loc.latitude)
        all_lons.append(loc.longitude)
    geoloc_out['Latitude'] = all_lats
    geoloc_out['Longitude'] = all_lons
    geoloc_out.to_csv(GEOLOC_PATH, index=False)


def load_and_append_extra_data(existing, new_path):
    
    data = pd.read_csv(new_path, parse_dates=[20])
    # remove duplicates if the submitted file has routes that we already know of
    for col in ['Distance planifiée', 'Distance acceptée', 'Ravitaillé',
                'Coût du carburant', 'Vitesse maximale atteinte']:
        data[col] = data[col].str.split(' ').str[:-1].str.join('').astype(int)
    for col in ['Bénéfice', 'Amendes']:
        data[col] = data[col].str.strip('€').str.replace(' ', '').astype(int)
    data['Masse'] = data['Masse'].str.strip(' kg').str.replace(' ', '').astype(int)
    data['Consommation moyenne'] = data['Consommation moyenne'].str.split(' ').str[0].astype(float)
    data['Plaque d\'immatriculation du camion'] = data[
        'Plaque d\'immatriculation du camion'].str.split(':').str[1].str[:-1]

    unique_cities = set(data['Depuis'].unique()).union(set(data['Vers'].unique()))
    geoloc = load_geoloc()
    missing_cities = unique_cities.difference(set(geoloc['City'].unique()))
    if len(missing_cities) > 0:
        geoloc_unknown_cities(missing_cities)
        geoloc = load_geoloc()   # reload, after completion
    data = data.merge(geoloc, how='left', left_on='Depuis', right_on='City')
    data = data.merge(geoloc, how='left', left_on='Vers', right_on='City', suffixes=('_from', '_to'))
    
    data = pd.concat([existing, data], axis=0).reset_index(drop=True)
    data = data.drop_duplicates()
    data.to_csv(EXISTING_DATA_PATH, index=False)
    
    return data


def compute_stats(data):
    
    stats = {}
    stats['Trajets pris en compte'] = str(data.shape[0]) + ' trajets du ' + \
        str(data['Date'].min()).split(' ')[0] + ' au ' + str(data['Date'].max()).split(' ')[0]
    stats['Ville de départ la plus fréquente'] = data['Depuis'].mode()[0] + ' : ' \
        + str(data['Depuis'].value_counts().iloc[0])
    stats['Ville d\'arrivée la plus fréquente'] = data['Vers'].mode()[0] + ' : ' \
        + str(data['Vers'].value_counts().iloc[0])
    stats['Chargement le plus fréquent'] = data['Chargement'].mode()[0] + ' : ' \
        + str(data['Chargement'].value_counts().iloc[0])
    stats['Camion le plus utilisé'] = data['Camion'].mode()[0] + ' ' + \
        data['Plaque d\'immatriculation du camion'].mode()[0] + ' : ' \
        + str(data['Camion'].value_counts().iloc[0]) + ' trajets'
    stats['Chargement le plus lourd'] = str(round(data['Masse'].max()/1000)) + ' T'
    stats['Masse totale transportée'] = str(round(data['Masse'].sum()/1000)) + ' T'
    stats['Distance totale planifiée'] = str(data['Distance planifiée'].sum()) + ' km'
    stats['Distance totale effectuée'] = str(data['Distance acceptée'].sum()) + ' km'
    stats['Consommation moyenne'] = str(round(
        (data['Consommation moyenne'] * data['Distance acceptée']).sum() / data['Distance acceptée'].sum(), 1)) + ' l/100 km'
    stats['Vitesse maximale'] = str(data['Vitesse maximale atteinte'].max()) + ' km/h'
    stats['Bénéfice total'] = str(round(data['Bénéfice'].sum()/10**6, 2)) + ' M€'
    stats['Total des amendes versées'] = str(round(data['Amendes'].sum()/10**3, 2)) + ' k€'
    return stats


def count_visits(data):
    
    visited = pd.concat(
        [data[['City_from', 'Latitude_from', 'Longitude_from']].rename(
            lambda c: c.split('_')[0], axis=1), 
         data[['City_to', 'Latitude_to', 'Longitude_to']].rename(
             lambda c: c.split('_')[0], axis=1)], 
        axis=0, ignore_index=True)
    return visited.groupby(list(visited.columns)).size().reset_index().rename({0: 'Visits'}, axis=1)


def plot_visited_cities(coords, bg):
    
    gpd_coords = gpd.GeoDataFrame(coords, geometry=gpd.points_from_xy(
        coords['Longitude'], coords['Latitude']), crs='EPSG:4326')
    
    fig = plt.figure(figsize=(8,8))
    fig.patch.set_facecolor('linen')
    ax = fig.gca()
    bg.plot(ax=ax, color='peru', edgecolor='dimgrey')
    # TODO: add city names
    gpd_coords.plot(ax=ax, cmap='viridis', column=gpd_coords['Visits'], 
                    legend=True, legend_kwds={'shrink': 0.6})
    ax.set_title("Villes les plus visitées")
    plt.subplots_adjust(left=0.05, right=1.05, top=1.1, bottom=-0.1)
    return fig


def plot_visited_cities_interactive(coords, bg):
    
    gpd_coords = gpd.GeoDataFrame(coords, geometry=gpd.points_from_xy(
        coords['Longitude'], coords['Latitude']), crs='EPSG:4326')
    fig = gpd_coords.explore(
        column='Visits', tooltip=['City', 'Visits'], cmap='viridis', 
        vmax=gpd_coords['Visits'].max()+1, marker_kwds=dict(radius=5, fill=True), legend=True)
    return fig


def plot_routes(coords):
    pass


def run(new_path):
    
    data = load_existing_data()
    bg = initialize_background()
    if new_path is not None:
        data = load_and_append_extra_data(data, new_path)
    stats = compute_stats(data)
    visits = count_visits(data)
    plots = []
    plots.append(plot_visited_cities(coords=visits, bg=bg))
    inter_plots = []
    inter_plots.append(plot_visited_cities_interactive(coords=visits, bg=bg))
    # plots.append(plot_routes(coords))
    return stats, plots, inter_plots
