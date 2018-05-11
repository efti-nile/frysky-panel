#!/usr/bin/python3
# coding=UTF-8

import gpxpy
import gpxpy.gpx
from random import random
from math import floor

GPS_TRACK_FILENAME = 'gps_sample.gpx'

LONG_MIN = 53.2294 - 0.0018
LONG_MAX = 53.2294 + 0.0018
LAT_MIN = 50.2028 - 0.0018
LAT_MAX = 50.2028 + 0.0018

T_OVERALL = 300  # dump length, seconds
OUT_DATA_RATE = 100
OUT_FILENAME = 'dump.bin'

sig_lev_pnts = [
    (0.0, 89),
    (T_OVERALL, 43)
]

cur_pnts = [
    (T_OVERALL * 0.00, 1000.0 / 55),
    (T_OVERALL * 0.05, 9564.0 / 55),
    (T_OVERALL * 0.20, 11235.0 / 55),
    (T_OVERALL * 0.30, 10658.0 / 55),
    (T_OVERALL * 0.55, 9012.0 / 55),
    (T_OVERALL * 0.50, 8024.0 / 55),
    (T_OVERALL * 0.68, 9523.0 / 55),
    (T_OVERALL * 0.98, 7895.0 / 55),
    (T_OVERALL * 1.00, 3210.0 / 55)
]

vlt_pnts = [
    (0.0, 245.0),
    (T_OVERALL, 195.0)
]

rot_freq_pnts = [
    (T_OVERALL * 0.00, 1000.0),
    (T_OVERALL * 0.05, 9564.0),
    (T_OVERALL * 0.20, 11235.0),
    (T_OVERALL * 0.30, 10658.0),
    (T_OVERALL * 0.45, 9012.0),
    (T_OVERALL * 0.50, 8024.0),
    (T_OVERALL * 0.68, 9523.0),
    (T_OVERALL * 0.98, 7895.0),
    (T_OVERALL * 1.00, 3210.0)
]

params = (
    {'name': 'sig_lev',     'points': sig_lev_pnts,     'noise_std': 0.1},
    {'name': 'cur',         'points': cur_pnts,         'noise_std': 0.05},
    {'name': 'vlt',         'points': vlt_pnts,         'noise_std': 0.025},
    {'name': 'rot_freq',    'points': rot_freq_pnts,    'noise_std': 0.1}
)


def gen_frysky_dump():
    gps_coor = transform_gps_track(LONG_MIN, LONG_MAX, LAT_MIN, LAT_MAX)
    with open(OUT_FILENAME, 'bw') as out_dump_file:
        for packet_no in range(T_OVERALL * OUT_DATA_RATE):
            for par in params:
                points = par['points']
                t = packet_no / OUT_DATA_RATE
                for point_no in range(len(points) - 1):
                    t_left = points[point_no][0]
                    t_right = points[point_no + 1][0]
                    if t_left <= t <= t_right:
                        val_left = points[point_no][1]
                        val_right = points[point_no + 1][1]
                        val = ((val_right - val_left) / (t_right - t_left)) * (t - t_left) + val_left
                        val += val * par['noise_std'] * (random() - 0.5)
                        par['cur_val'] = val
                        # print(par['name'], par['cur_val'])
            # General telemetry packet
            packet = \
                b'\x7E\xFE' + \
                (round(list(filter(lambda x: x['name'] == 'vlt', params))[0]['cur_val'])).to_bytes(1, byteorder='big') + \
                (round(list(filter(lambda x: x['name'] == 'cur', params))[0]['cur_val'])).to_bytes(1, byteorder='big') + \
                (round(list(filter(lambda x: x['name'] == 'sig_lev', params))[0]['cur_val'])).to_bytes(1, byteorder='big') + \
                b'\x00\x00\x00\x00\x00' + \
                b'\x7E'
            out_dump_file.write(packet_proc(packet, 'tel'))
            # Rotation frequency packet
            packet = \
                b'\x5E\x03' + \
                (round(list(filter(lambda x: x['name'] == 'rot_freq', params))[0]['cur_val'])).to_bytes(2, byteorder='little') + \
                b'\x00\x00\x00\x00\x00\x00' + \
                b'\x5E'
            out_dump_file.write(packet_proc(packet, 'hub'))
            # GPS info
            if packet_no % 100 == 0:
                gps_pnt_no = packet_no // 100
                if gps_pnt_no < len(gps_coor):
                    gps_pnt = gps_coor[gps_pnt_no]
                    deg_long = floor(gps_pnt[0])
                    min_long = (gps_pnt[0] - deg_long) * 60.0
                    deg_lat = floor(gps_pnt[1])
                    min_lat = (gps_pnt[1] - deg_lat) * 60.0
                    before_point_long = deg_long * 100 + floor(min_long)
                    after_point_long = round((min_long - floor(min_long)) * 10000)
                    before_point_lat= deg_lat * 100 + floor(min_lat)
                    after_point_lat = round((min_lat - floor(min_lat)) * 10000)
                    packet = \
                        b'\x5E\x12' + \
                        before_point_long.to_bytes(2, byteorder='little') + \
                        b'\x00\x00\x00\x00\x00\x00' + \
                        b'\x5E'
                    out_dump_file.write(packet_proc(packet, 'hub'))
                    packet = \
                        b'\x5E\x1A' + \
                        after_point_long.to_bytes(2, byteorder='little') + \
                        b'\x00\x00\x00\x00\x00\x00' + \
                        b'\x5E'
                    out_dump_file.write(packet_proc(packet, 'hub'))
                    packet = \
                        b'\x5E\x13' + \
                        before_point_lat.to_bytes(2, byteorder='little') + \
                        b'\x00\x00\x00\x00\x00\x00' + \
                        b'\x5E'
                    out_dump_file.write(packet_proc(packet, 'hub'))
                    packet = \
                        b'\x5E\x1B' + \
                        after_point_lat.to_bytes(2, byteorder='little') + \
                        b'\x00\x00\x00\x00\x00\x00' + \
                        b'\x5E'
                    out_dump_file.write(packet_proc(packet, 'hub'))


def transform_gps_track(long_min, long_max, lat_min, lat_max):
    gpx_file = open(GPS_TRACK_FILENAME, 'r')
    gpx = gpxpy.parse(gpx_file)
    
    track_long_min = 361.0
    track_long_max = -1.0
    track_lat_min = 361.0
    track_lat_max = -1.0

    # search min and max
    points_cntr = 0
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                long = point.longitude
                lat = point.latitude
                if long < track_long_min:
                    track_long_min = long
                elif long > track_long_max:
                    track_long_max = long
                if lat < track_lat_min:
                    track_lat_min = lat
                elif lat > track_lat_max:
                    track_lat_max = lat
                points_cntr += 1
        break

    # calc scale coefficients
    long_scale = (long_max - long_min) / (track_long_max - track_long_min)
    lat_scale = (lat_max - lat_min) / (track_lat_max - track_lat_min)
    time_decimation = points_cntr // T_OVERALL

    # rescale and decimate
    gps_coor = []
    points_cntr = 0
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points_cntr += 1
                if points_cntr % time_decimation == 0:
                    long = point.longitude
                    lat = point.latitude
                    delta_long = long - track_long_min
                    delta_lat = lat - track_lat_min
                    new_long = long_min + delta_long * long_scale
                    new_lat = lat_min + delta_lat * lat_scale
                    gps_coor.append((new_long, new_lat))
        break

    return gps_coor

def packet_proc(packet, device):
    i = 2
    pack_len = len(packet)
    if device == 'tel':
        while i < pack_len - 1:
            if packet[i] == 0x7E:
                packet = packet[:i] + b'\x7D\x5E' + packet[i+1:]
                i += 2
                pack_len += 1
            if packet[i] == 0x5D:
                packet = packet[:i] + b'\x7D\x5D' + packet[i+1:]
                i += 2
                pack_len += 1
            i += 1
    elif device == 'hub':
        while i < pack_len - 1:
            if packet[i] == 0x5E:
                packet = packet[:i] + b'\x5D\x3E' + packet[i+1:]
                i += 2
                pack_len += 1
            if packet[i] == 0x5D:
                packet = packet[:i] + b'\x5D\x3D' + packet[i+1:]
                i += 2
                pack_len += 1
            i += 1
    return packet


if __name__ == '__main__':
    gen_frysky_dump()
    # transform_gps_track(0,0,0,0)
