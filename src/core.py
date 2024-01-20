from functools import partial
import geopandas as gpd
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
from matplotlib import pyplot as plt
import os
import pandas as pd
from shapely.geometry import LineString



if os.path.exists("data/"):
    PREFIX = "data/"
else:
    PREFIX = "_internal/data/"
GEOLOC_PATH = PREFIX + "geoloc_cities.csv"
EXISTING_DATA_PATH = PREFIX + "consolidated.csv"
SAMPLE_DATA_PATH = PREFIX + "sample.csv"
BACKGROUND_PATH = PREFIX + "NUTS_RG_20M_2021_4326.shp.zip"
EUROPE_LIMIT_COORDS = [-12, 30, 35, 65]


def load_geoloc():
    return pd.read_csv(GEOLOC_PATH)


def load_existing_routes():
    try:
        return pd.read_csv(EXISTING_DATA_PATH, parse_dates=[21])
    except FileNotFoundError:
        return pd.read_csv(SAMPLE_DATA_PATH, parse_dates=[21])


def initialize_background():
    bg = gpd.read_file(BACKGROUND_PATH)
    return bg[bg['LEVL_CODE'] == 0].clip(EUROPE_LIMIT_COORDS)


def geoloc_unknown_cities(known_geoloc, cities):
    
    geolocator = Nominatim(user_agent="ets-dashboard")
    geocode = partial(RateLimiter(geolocator.geocode, min_delay_seconds=1),
                      viewbox=((35,-12), (65,30)), bounded=True)

    geoloc_out = pd.DataFrame(cities, columns=['City'])
    all_lats = []
    all_lons = []
    for city in cities:
        loc = geocode(city)
        all_lats.append(loc.latitude)
        all_lons.append(loc.longitude)
    geoloc_out['Latitude'] = all_lats
    geoloc_out['Longitude'] = all_lons
    geoloc_out = pd.concat([known_geoloc, geoloc_out], axis=0).reset_index(drop=True)
    geoloc_out.to_csv(GEOLOC_PATH, index=False)


def load_and_append_extra_routes(existing, new_path):
    
    routes = pd.read_csv(new_path, parse_dates=[21])
    for col in ['Distance planifiée', 'Distance acceptée', 'Ravitaillé',
                'Coût du carburant', 'Vitesse maximale atteinte']:
        routes[col] = routes[col].str.split(' ').str[:-1].str.join('').astype(int)
    for col in ['Bénéfice', 'Amendes']:
        routes[col] = routes[col].str.strip('€').str.replace(' ', '').astype(int)
    routes['Masse'] = routes['Masse'].str.strip(' kg').str.replace(' ', '').astype(int)
    routes['Consommation moyenne'] = routes['Consommation moyenne'].str.split(' ').str[0].astype(float)
    routes['Plaque d\'immatriculation du camion'] = routes[
        'Plaque d\'immatriculation du camion'].str.split(':').str[1].str[:-1]

    unique_cities = set(routes['Depuis'].unique()).union(set(routes['Vers'].unique()))
    geoloc = load_geoloc()
    missing_cities = unique_cities.difference(set(geoloc['City'].unique()))
    if len(missing_cities) > 0:
        geoloc_unknown_cities(geoloc, missing_cities)
        geoloc = load_geoloc()   # reload, after completion
    routes = routes.merge(geoloc, how='left', left_on='Depuis', right_on='City')
    routes = routes.merge(geoloc, how='left', left_on='Vers', right_on='City', suffixes=('_from', '_to'))
    
    routes = pd.concat([existing, routes], axis=0).reset_index(drop=True)
    # remove duplicates if the submitted file has routes that we already know of
    routes = routes.drop_duplicates()
    routes.to_csv(EXISTING_DATA_PATH, index=False)
    
    return routes


def compute_stats(routes):
    
    stats = {}
    stats['Trajets pris en compte'] = str(routes.shape[0]) + ' trajets du ' + \
        str(routes['Date'].min()).split(' ')[0] + ' au ' + str(routes['Date'].max()).split(' ')[0]
    stats['Ville de départ la plus fréquente'] = routes['Depuis'].mode()[0] + ' : ' \
        + str(routes['Depuis'].value_counts().iloc[0])
    stats['Ville d\'arrivée la plus fréquente'] = routes['Vers'].mode()[0] + ' : ' \
        + str(routes['Vers'].value_counts().iloc[0])
    most_visits = (routes['Depuis'].value_counts() + routes['Vers'].value_counts()).sort_values(
        ascending=False, na_position='last')
    stats['Ville la plus visitée'] = most_visits.index[0] + ' : ' \
        + str(int(most_visits.iloc[0]))
    stats['Chargement le plus fréquent'] = routes['Chargement'].mode()[0] + ' : ' \
        + str(routes['Chargement'].value_counts().iloc[0]) + ' trajets'
    stats['Camion le plus utilisé'] = routes['Camion'].mode()[0] + ' ' + \
        routes['Plaque d\'immatriculation du camion'].mode()[0] + ' : ' \
        + str(routes['Camion'].value_counts().iloc[0]) + ' trajets'
    stats['Chargement le plus lourd'] = str(round(routes['Masse'].max()/1000)) + ' T'
    stats['Masse totale transportée'] = str(round(routes['Masse'].sum()/1000)) + ' T'
    stats['Distance totale planifiée'] = str(routes['Distance planifiée'].sum()) + ' km'
    stats['Distance totale effectuée'] = str(routes['Distance acceptée'].sum()) + ' km'
    stats['Consommation moyenne'] = str(round(
        (routes['Consommation moyenne'] * routes['Distance acceptée']).sum() / 
        routes['Distance acceptée'].sum(), 1)) + ' l/100 km'
    stats['Vitesse maximale'] = str(routes['Vitesse maximale atteinte'].max()) + ' km/h'
    stats['Bénéfice total'] = str(round(routes['Bénéfice'].sum()/10**6, 2)) + ' M€'
    stats['Total des amendes versées'] = str(round(routes['Amendes'].sum()/10**3, 2)) + ' k€'
    stats['Durée totale en jeu'] = str(round(routes['Temps pris (réel) [s]'].sum()/3600, 1)) + ' h'
    return stats


def count_visits(routes):
    
    visited = pd.concat(
        [routes[['City_from', 'Latitude_from', 'Longitude_from']].rename(
            lambda c: c.split('_')[0], axis=1), 
         routes[['City_to', 'Latitude_to', 'Longitude_to']].rename(
             lambda c: c.split('_')[0], axis=1)], 
        axis=0, ignore_index=True)
    return visited.groupby(list(visited.columns)).size().reset_index().rename({0: 'Visits'}, axis=1)


def plot_visited_cities(coords, bg):
    
    gpd_coords = gpd.GeoDataFrame(coords, geometry=gpd.points_from_xy(
        coords['Longitude'], coords['Latitude']), crs='EPSG:4326')
    
    fig = plt.figure(figsize=(7,7))
    fig.patch.set_facecolor('linen')
    ax = fig.gca()
    bg.plot(ax=ax, color='peru', edgecolor='dimgrey')
    # TODO: add city names
    gpd_coords.plot(ax=ax, cmap='viridis', column=gpd_coords['Visits'], 
                    legend=True, legend_kwds={'shrink': 0.6})
    ax.set_title("Villes les plus visitées")
    plt.subplots_adjust(left=0.05, right=1.05, top=1.1, bottom=-0.1)
    return fig


def plot_visited_cities_interactive(coords):
    
    gpd_coords = gpd.GeoDataFrame(coords, geometry=gpd.points_from_xy(
        coords['Longitude'], coords['Latitude']), crs='EPSG:4326')
    fig = gpd_coords.explore(
        column='Visits', tooltip=['City', 'Visits'], tiles='CartoDB positron', cmap='viridis', 
        vmax=gpd_coords['Visits'].max()+1, marker_kwds=dict(radius=5, fill=True), legend=True)
    return fig


def plot_routes_interactive(routes):
    
    # TODO: color by month of completion
    routes['geometry'] = routes.apply(lambda row: 
        LineString([[row['Longitude_from'], row['Latitude_from']],
                    [row['Longitude_to'], row['Latitude_to']]]), axis=1)
    gpd_routes = gpd.GeoDataFrame(routes, geometry='geometry', crs='EPSG:4326')
    gpd_routes['Date'] = gpd_routes['Date'].dt.strftime('%d/%m/%Y')
    gpd_routes['Temps de jeu'] = (gpd_routes['Temps pris (réel) [s]'] // 3600).astype(str) + ' h ' \
        + ((gpd_routes['Temps pris (réel) [s]'] % 3600)//60).astype(str) + ' min'
    fig = gpd_routes.explore(
        tooltip=['City_from', 'City_to'], tiles='CartoDB positron',
        popup=['Depuis', 'Vers', 'Chargement', 'Masse', 'Distance acceptée', 'Camion', 'Date', 'Temps de jeu'])
    return fig


def run(new_path):
    
    routes = load_existing_routes()
    bg = initialize_background()
    if new_path is not None:
        routes = load_and_append_extra_routes(routes, new_path)
    stats = compute_stats(routes)
    visits = count_visits(routes)
    plots = []
    plots.append(plot_visited_cities(coords=visits, bg=bg))
    inter_plots = []
    inter_plots.append(plot_visited_cities_interactive(coords=visits))
    # TODO: regular plot routes
    inter_plots.append(plot_routes_interactive(routes))
    return stats, plots, inter_plots
