import glob
import os
import pandas as pd
from datetime import datetime
from pathlib import Path


def filter_logs(wifi_logs, hour):
    df = pd.DataFrame(columns=['from_router_id', 'to_router_id', 'seconds'])
    grouped_wifi_logs = wifi_logs.groupby('user_mac')
    for user_mac, user_logs in grouped_wifi_logs:
        user_logs.sort_values(by='tm', inplace=True)
        prev_id = user_logs.iloc[0]['router_id']
        for i in range(1, len(user_logs)):
            row = user_logs.iloc[i]
            cur_id = row['router_id']
            if cur_id != prev_id:
                prev_time = user_logs.iloc[i - 1]['tm']
                time = row['tm'] - prev_time
                df.loc[len(df)] = [cur_id, prev_id, time.total_seconds()]
            prev_id = cur_id

    filtered_groups = []
    groups = df.groupby(by=['from_router_id', 'to_router_id'])
    for edge, group_df in groups:
        q1 = group_df['seconds'].quantile(0.25)
        q3 = group_df['seconds'].quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        filtered_group_df = group_df[(group_df['seconds'] >= lower_bound) & (group_df['seconds'] <= upper_bound)]
        filtered_groups.append(filtered_group_df)

    df = pd.concat(filtered_groups)
    df = df.groupby(by=['from_router_id', 'to_router_id']).agg({'seconds': ['sum', 'count']}).reset_index()
    df.columns = ['from_router_id', 'to_router_id', 'seconds', 'count']

    return df


def process_log(path):
    df = pd.read_csv(path, sep=';')
    df['tm'] = df['tm'].apply(lambda s: datetime.strptime(s, '%Y-%m-%d %H:%M:%S.%f %z'))

    groups = df.groupby([df['tm'].dt.hour])
    for hour, group_df in groups:
        h = hour[0]
        new_df = filter_logs(group_df, h)

        name = os.path.basename(path)
        parts = name.split(sep='_')
        year = int(parts[2])
        month = int(parts[3])
        day = int(parts[4])
        output_dir = f'data/{year}/{month}/{day}'

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        new_df.to_csv(f'{output_dir}/{h}.csv', index=False, sep=';')


def process_logs():
    csv_files = glob.glob('original/wifi_logs_*/*.csv', recursive=True)
    csv_files = sorted(csv_files)
    for csv_file in csv_files:
        process_log(csv_file)

process_logs()