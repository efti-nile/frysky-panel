#!/usr/bin/python3
# coding=UTF-8

import threading
import _thread

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
    out_params = []

    def __init__(self, input_stream):
        threading.Thread.__init__(self)
        self.input_stream = input_stream

    def run(self):
        global out_params
        state = IDLE
        gps_flags = 0x00
        pack_cntr = 0

        while True:
            byte = int.from_bytes(self.input_stream.read(1), byteorder='little')
            pack_cntr += 1

            # Reset if more than 11 bytes. There are no packets longer than 11
            if pack_cntr >= 11:
                state = IDLE

            # Telemetry parsing
            if byte == 0x7E and state == IDLE:
                state = TEL_PACK_START
                pack_cntr = 0
            elif state == TEL_PACK_START and byte == 0xFE:
                state = TEL_PACK
            elif state == TEL_PACK:
                self.out_params.append(('vlt', 4.2 * (byte / 256.0)))
                state = TEL_PACK_VLT
            elif state == TEL_PACK_VLT:
                self.out_params.append(('cur', 100.0 * (byte / 256.0)))
                state = TEL_PACK_CUR
            elif state == TEL_PACK_CUR:
                self.out_params.append(('sig_lev', byte))
                state = TEL_PACK_SIG_LEV
            elif state == TEL_PACK_SIG_LEV and byte == 0x7E:
                state = IDLE
            else:
                pass

            # Sensor hub parsing
            if byte == 0x5E and state == IDLE:
                state = HUB_PACK_START
                pack_cntr = 0
            elif state == HUB_PACK_START:
                par_name = prim_to_par[byte]
                state = HUB_PRIM
            elif state == HUB_PRIM:
                par_lsb_byte = byte
                state = HUB_PAR_LSB
            elif state == HUB_PAR_LSB:
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
                    par_msb_byte = byte
                    self.out_params.append((par_name, par_msb_byte * 256 + par_lsb_byte))
                state = HUB_PAR_MSB
            elif state == HUB_PAR_MSB and byte == 0x5E:
                state = IDLE

            # GPS processing
            if gps_flags & GPS_LONG_BEF_PNT and gps_flags & GPS_LONG_AFT_PNT:
                long_deg = gps_long_bef_pnt // 100
                long_min = (gps_long_bef_pnt - long_deg * 100.0) + (gps_long_aft_pnt / 1000.0)
                long = long_deg + (long_min / 60.0)
                self.out_params.append(('long', long))
                gps_flags = gps_flags & (GPS_LAT_BEF_PNT | GPS_LAT_AFT_PNT)
            if gps_flags & GPS_LAT_BEF_PNT and gps_flags & GPS_LAT_AFT_PNT:
                lat_deg = gps_lat_bef_pnt // 100
                lat_min = (gps_lat_bef_pnt - lat_deg * 100.0) + (gps_lat_aft_pnt / 1000.0)
                lat = lat_deg + (lat_min / 60.0)
                self.out_params.append(('lat', lat))
                print('lat', lat)
                gps_flags = gps_flags & (GPS_LONG_BEF_PNT | GPS_LONG_AFT_PNT)
