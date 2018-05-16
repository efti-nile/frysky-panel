#!/usr/bin/python3
# coding=UTF-8

import threading
import time

INSTREAM_ACQ_PER = 0.1  # Period of data acquisition from the input stream, seconds

# State machine variables
IDLE = -1

TEL_PACK_START = 0  # Telemetry packets
TEL_PACK = 1
TEL_PACK_VLT = 2
TEL_PACK_CUR = 3
TEL_PACK_SIG_LEV = 4

HUB_PACK_START = 10  # Sensors' hub packets
HUB_PRIM = 11
HUB_PAR_LSB = 12
HUB_PAR_MSB = 13

# Flag masks
GPS_LONG_BEF_PNT = 0x01
GPS_LONG_AFT_PNT = 0x02
GPS_LAT_BEF_PNT = 0x04
GPS_LAT_AFT_PNT = 0x08

prim_to_par = {  # Parameters names by their PRIMs
    0x12: 'long_bef_pnt',
    0x1A: 'long_aft_pnt',
    0x13: 'lat_bef_pnt',
    0x1B: 'lat_aft_pnt',
    0x03: 'rot_freq'
}


class FrySkyParserThread(threading.Thread):

    def __init__(self, input_stream):
        threading.Thread.__init__(self)
        self.input_stream = input_stream
        self.lock = threading.Lock()
        self.out_params = []
        self.term_sig = False
        self.pause_s = 0.0

    def set_pause(self, new_val_ms):
        self.pause_s = new_val_ms * 1e-3

    def run(self):
        state = IDLE
        gps_flags = 0x00
        pack_cntr = 0
        is_spec_byte_met = False

        while not self.term_sig:
            chunk = self.input_stream.read()
            if chunk == b'':
                time.sleep(INSTREAM_ACQ_PER)
            for cur_byte in chunk:
                if (cur_byte == 0x7D and TEL_PACK_START <= state <= TEL_PACK_SIG_LEV)\
                        or (cur_byte == 0x5D and HUB_PACK_START <= state <= HUB_PAR_MSB):
                    is_spec_byte_met = True
                    continue

                if TEL_PACK_START <= state <= TEL_PACK_SIG_LEV\
                        and is_spec_byte_met:
                    cur_byte = cur_byte ^ 0x20
                    is_spec_byte_met = False
                elif HUB_PACK_START <= state <= HUB_PAR_MSB\
                        and is_spec_byte_met:
                    cur_byte = cur_byte ^ 0x60
                    is_spec_byte_met = False

                pack_cntr += 1

                # Reset if more than 11 bytes. There are no packets longer than 11
                if pack_cntr >= 11:
                    state = IDLE

                # Telemetry parsing
                if cur_byte == 0x7E and state == IDLE:
                    state = TEL_PACK_START
                    pack_cntr = 0
                elif state == TEL_PACK_START and cur_byte == 0xFE:
                    state = TEL_PACK
                elif state == TEL_PACK:
                    self.push_param('vlt', 4.2 * (cur_byte / 256.0))
                    state = TEL_PACK_VLT
                elif state == TEL_PACK_VLT:
                    self.push_param('cur', 100.0 * (cur_byte / 256.0))
                    state = TEL_PACK_CUR
                elif state == TEL_PACK_CUR:
                    self.push_param('sig_lev', cur_byte)
                    state = TEL_PACK_SIG_LEV
                elif state == TEL_PACK_SIG_LEV and cur_byte == 0x7E:
                    state = IDLE
                    time.sleep(self.pause_s)

                # Sensor hub parsing
                if cur_byte == 0x5E and state == IDLE:
                    state = HUB_PACK_START
                    pack_cntr = 0
                elif state == HUB_PACK_START:
                    par_name = prim_to_par[cur_byte]
                    state = HUB_PRIM
                elif state == HUB_PRIM:
                    par_lsb_byte = cur_byte
                    state = HUB_PAR_LSB
                elif state == HUB_PAR_LSB:
                    par_msb_byte = cur_byte
                    if par_name == 'long_bef_pnt':
                        gps_flags |= GPS_LONG_BEF_PNT
                        gps_long_bef_pnt = par_msb_byte * 256 + par_lsb_byte
                    elif par_name == 'long_aft_pnt':
                        gps_flags |= GPS_LONG_AFT_PNT
                        gps_long_aft_pnt = par_msb_byte * 256 + par_lsb_byte
                    elif par_name == 'lat_bef_pnt':
                        gps_flags |= GPS_LAT_BEF_PNT
                        gps_lat_bef_pnt = par_msb_byte * 256 + par_lsb_byte
                    elif par_name == 'lat_aft_pnt':
                        gps_flags |= GPS_LAT_AFT_PNT
                        gps_lat_aft_pnt = par_msb_byte * 256 + par_lsb_byte
                    else:
                        self.push_param(par_name, par_msb_byte * 256 + par_lsb_byte)
                    state = HUB_PAR_MSB
                elif state == HUB_PAR_MSB and cur_byte == 0x5E:
                    state = IDLE
                    time.sleep(self.pause_s)

                # GPS processing
                if gps_flags == (GPS_LONG_BEF_PNT | GPS_LONG_AFT_PNT | GPS_LAT_BEF_PNT | GPS_LAT_AFT_PNT):
                    # Longitude
                    long_deg = gps_long_bef_pnt // 100
                    long_min = (gps_long_bef_pnt - long_deg * 100.0) + (gps_long_aft_pnt / 1000.0)
                    long = long_deg + (long_min / 60.0)
                    # Latitude
                    lat_deg = gps_lat_bef_pnt // 100
                    lat_min = (gps_lat_bef_pnt - lat_deg * 100.0) + (gps_lat_aft_pnt / 1000.0)
                    lat = lat_deg + (lat_min / 60.0)
                    self.push_param('coor', (long, lat))
                    gps_flags &= ~(GPS_LONG_BEF_PNT | GPS_LONG_AFT_PNT | GPS_LAT_BEF_PNT | GPS_LAT_AFT_PNT)

    def push_param(self, par_name, par_val):
        self.lock.acquire(blocking=1)
        self.out_params.append((par_name, par_val))
        self.lock.release()