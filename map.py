import re
import json
import pandas as pd
import folium
from geopy import distance
from folium.plugins import GroupedLayerControl, HeatMap, PolyLineOffset
import matplotlib.colors as mcolors

tulaCoord = [54.1913, 37.6165]
tulaZoom = 13
dataFolder = 'data'
dataYear = 2022
dataMonth = 12
dataDay = 1

m = folium.Map(tulaCoord, zoom_start=tulaZoom)
road_network = pd.read_csv('data/routers_network/road_network.csv', sep=';')
wifi_routers = pd.read_csv('data/routers_network/wifi_routers.csv', sep=';')
car_detections = pd.DataFrame(columns=['from_router_id', 'to_router_id', 'seconds', 'count', 'seconds_avr', 'mins_avr', 'hours_avr', 'dist', 'speed_avr', 'date_time', 'color', 'width', 'opacity'])


def init_road_network():
    road_network['geom'] = road_network['geom'].apply(lambda s: re.findall(r'.*\((.*)\)', s)[0].replace(',', ' '))
    road_network['latitude_0'] = road_network['geom'].apply(lambda s: get_coord(s, 1))
    road_network['longitude_0'] = road_network['geom'].apply(lambda s: get_coord(s, 0))
    road_network['latitude_1'] = road_network['geom'].apply(lambda s: get_coord(s, 3))
    road_network['longitude_1'] = road_network['geom'].apply(lambda s: get_coord(s, 2))
    road_network['latitude_2'] = road_network['geom'].apply(lambda s: get_coord(s, 5))
    road_network['longitude_2'] = road_network['geom'].apply(lambda s: get_coord(s, 4))
    road_network.drop(columns=['geom', 'group_id'], inplace=True)


def init_wifi_routers():
    geom_separators = r"\s|\(|\)"
    wifi_routers['longitude'] = wifi_routers['geom'].apply(lambda s: float(re.split(geom_separators, s)[2]))
    wifi_routers['latitude'] = wifi_routers['geom'].apply(lambda s: float(re.split(geom_separators, s)[3]))
    wifi_routers.drop(columns=['geom'], inplace=True)
    wifi_routers['address_json'] = wifi_routers['address_json'].apply(lambda s: json.loads(s)['rus'])
    wifi_routers.rename(columns={'address_json': 'address'}, inplace=True)


def init_car_detections(folder, year, month, day, hour):
    path = f"{folder}/{year}/{month}/{day}/{hour}.csv"
    df = pd.read_csv(path, sep=';')
    df['seconds_avr'] = (df['seconds'] + 0.0001) / df['count']
    df['mins_avr'] = df['seconds_avr'] / 60.0
    df['hours_avr'] = df['mins_avr'] / 60.0
    df['dist'] = df.apply(
        lambda row: get_distance_km(get_sniffer_latlon(row['from_router_id']), get_sniffer_latlon(row['to_router_id'])),
        axis=1)
    df['speed_avr'] = df.apply(lambda row: min(row['dist'] / row['hours_avr'], 250), axis=1)
    df['date_time'] = f"{year}-{month}-{day} {hour}:00:00"
    meanCarCount = df['count'].mean()
    maxSpeed = df['speed_avr'].max()
    colors = ['red', 'yellow', 'green']
    cmap = mcolors.LinearSegmentedColormap.from_list('custom_colormap', colors)
    df['color'] = df.apply(lambda row: mcolors.to_hex(cmap(row['speed_avr'] / maxSpeed)), axis=1)
    df['width'] = df.apply(lambda row: 1 if row['count'] < meanCarCount else 3, axis=1)
    df['opacity'] = df.apply(lambda row: row['count'] / meanCarCount, axis=1)
    return df

def get_coord(s, i):
    return float(s.split()[i])


def get_sniffer_latlon(guid):
    filtered_df = wifi_routers[wifi_routers['guid'] == guid]
    lat = filtered_df['latitude'].values[0]
    lon = filtered_df['longitude'].values[0]
    return [lat, lon]


def get_distance_km(p1, p2):
    return distance.distance(p1, p2).km


def build_sniffers_layout():
    sniffersData = []
    sniffersGroup = folium.FeatureGroup(name='Sniffer Markers', show=True).add_to(m)
    sniffersHeatmapGroup = folium.FeatureGroup(name="Sniffer Heatmap", show=False).add_to(m)
    for ind in wifi_routers.index:
        latitude = wifi_routers['latitude'][ind]
        longitude = wifi_routers['longitude'][ind]
        address = f"{wifi_routers['guid'][ind]} - {wifi_routers['address'][ind]}"
        folium.Marker([latitude, longitude], popup=address).add_to(sniffersGroup)
        sniffersData.append([latitude, longitude, 1.0])
    HeatMap(sniffersData).add_to(sniffersHeatmapGroup)


def build_routes_layout():
    routesGroup = folium.FeatureGroup(name='Routes', show=False).add_to(m)
    minLat, maxLat, minLon, maxLon = 54.1646166190679, 54.2491761841739, 37.5726628595483, 37.67935
    for ind in road_network.index:
        lat0 = road_network['latitude_0'][ind]
        lon0 = road_network['longitude_0'][ind]
        if lat0 > maxLat or lat0 < minLat or lon0 > maxLon or lon0 < minLon:
            continue
        lat1 = road_network['latitude_1'][ind]
        lon1 = road_network['longitude_1'][ind]
        if lat1 > maxLat or lat1 < minLat or lon1 > maxLon or lon1 < minLon:
            continue
        lat2 = road_network['latitude_2'][ind]
        lon2 = road_network['longitude_2'][ind]
        if lat2 > maxLat or lat2 < minLat or lon2 > maxLon or lon2 < minLon:
            continue
        folium.PolyLine(
            locations=[[lat0, lon0], [lat1, lon1], [lat2, lon2]],
            color="#FF0000",
            weight=3,
        ).add_to(routesGroup)


def build_graph():
    features = []
    for ind in car_detections.index:
        from_latlon = get_sniffer_latlon(car_detections['from_router_id'][ind])
        to_latlon = get_sniffer_latlon(car_detections['to_router_id'][ind])
        count = car_detections['count'][ind]
        mins = car_detections['mins_avr'][ind]
        coords = [[from_latlon[1], from_latlon[0]], [to_latlon[1], to_latlon[0]]]
        dist = car_detections['dist'][ind]
        speed = car_detections['speed_avr'][ind]
        color = car_detections['color'][ind]
        width = car_detections['width'][ind]
        opacity = car_detections['opacity'][ind]
        date_time = car_detections['date_time'][ind]
        features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
                "properties": {
                    "popup": f"distance: {round(dist, 2)} km <br> time: {round(mins, 2)} min <br> speed: {round(speed, 2)} km/h <br> count:{count}",
                    "times": [date_time, date_time],
                    "style": {
                        "color": color,
                        "opacity": opacity,
                        "width": width
                    },
                },
            }
        )
    folium.plugins.TimestampedGeoJson(
        {
            "type": "FeatureCollection",
            "features": features,
        },
        period="PT1H",
        add_last_point=False,
        auto_play=False
    ).add_to(m)

    # folium.plugins.PolyLineOffset(
    #     coords,
    #     weight=2,
    #     dash_array=dash,
    #     color=color,
    #     opacity=opacity,
    #     tooltip=f"distance: {round(dist, 2)} km <br> time: {round(mins, 2)} min <br> speed: {round(speed, 2)} km/h <br> count:{count}"
    # ).add_to(sniffersGraphLeaksGroup if is_leak else sniffersGraphGroup)


init_road_network()
init_wifi_routers()

for hour in range(0, 24):
    df = init_car_detections(dataFolder, dataYear, dataMonth, dataDay, hour)
    car_detections = pd.concat([car_detections, df], ignore_index=True)
    print(f"{hour} - done")
print("data load - done")

build_sniffers_layout()
print("sniffersGroup and Heatmap - done")
build_routes_layout()
print("routesGroup - done")
build_graph()
print("sniffersGraphGroup - done")

folium.LayerControl().add_to(m)
m.show_in_browser()
