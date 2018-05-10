#!/usr/bin/python3
# coding=UTF-8

from tkinter import *
import _thread
from rand_coord import next_rand_coord
from frysky_parser import FrySkyParserThread
import os.path
import json

MAIN_WINDOW_TITLE = 'FrySky View Panel'
MAIN_WINDOW_HEIGHT = 600
MAIN_WINDOW_WIDTH = 900

SETTINGS_BUTTON_PROMPT = 'ctrl + \'S\': COM settings'

CELL_CAPTION_WIDTH = 18

SETTINGS_FILE = 'settings.json'

INPUT_TEST = 'dump.bin'

MODE = 'test'

class Gui(Tk):
    cells = (
        {'caption': 'Signal level',    'name': 'sig_lev',  'cell': None},
        {'caption': 'Current, A',      'name': 'cur',      'cell': None},
        {'caption': 'Voltage, V',      'name': 'vlt',      'cell': None},
        {'caption': 'Rot. freq., RPM', 'name': 'rot_freq', 'cell': None}
    )

    coor = []

    px_per_minute = 100.0 * 1000.0  # 100 pixels per 0.001 minute of angle (1.85 m)

    def __init__(self):
        Tk.__init__(self)
        self.title(MAIN_WINDOW_TITLE)
        self.geometry('{0}x{1}'.format(MAIN_WINDOW_WIDTH, MAIN_WINDOW_HEIGHT))
        self.resizable(0, 0)

        # Load default settings if settings file exists
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE) as f:
                self.settings = json.load(f)
        else:
            self.settings = {}

        inpan = Frame(self, relief=SUNKEN,
                      width=MAIN_WINDOW_WIDTH // 3, height=MAIN_WINDOW_HEIGHT)
        inpan.grid(row=0, column=0, columnspan=1)

        Label(inpan, text=SETTINGS_BUTTON_PROMPT, anchor='s').grid(row=1, column=0, sticky='S')

        self.can = Canvas(self, width=MAIN_WINDOW_WIDTH * 2 // 3, height=MAIN_WINDOW_HEIGHT,
                          background='#ffffff')
        self.can.grid(row=0, column=1, columnspan=2)
        self.can_base = (MAIN_WINDOW_WIDTH // 3, MAIN_WINDOW_HEIGHT // 2)  # canvas center
        
        self.coor_base = next_rand_coord()
        self.coor.append(self.coor_base)
        delta = 1e-4
        self.coor_max_long = self.coor_base[0] + delta
        self.coor_max_lat = self.coor_base[1] + delta
        self.coor_min_long = self.coor_base[0] - delta
        self.coor_min_lat = self.coor_base[1] - delta
        self.px_per_minute = (MAIN_WINDOW_HEIGHT // 2) / delta

        genpan = Frame(self, width=MAIN_WINDOW_WIDTH // 3)
        genpan.grid(row=0, column=0, sticky='ewn')

        genpan_cap = Label(genpan, text='General info', bg='#cccccc')
        genpan_cap.grid(row=0, column=0, sticky='ew', columnspan=2)

        row_cntr = 2
        for cell in self.cells:
            cap = Label(genpan, text=cell['caption'], width=CELL_CAPTION_WIDTH)
            cap.grid(row=row_cntr, column=0)
            cell['cell'] = Label(genpan, text='n/d', width=CELL_CAPTION_WIDTH, anchor='w',
                                 bg='#eeeeee')
            cell['cell'].grid(row=row_cntr, column=1)
            row_cntr += 1

        if MODE == 'test':
            in_file = open(INPUT_TEST, 'rb')
        else:
            print('Only test mode now')

        self.parser = FrySkyParserThread(in_file)
        self.parser.start()

        self.after(1000, self.updater)

    def updater(self):
        new_coor = next_rand_coord()
        old_coor = self.coor[-1]
        self.coor.append(new_coor)
        redraw_needed = False

        if new_coor[0] < self.coor_min_long:
            self.coor_min_long = new_coor[0]
            redraw_needed = True
        elif new_coor[0] > self.coor_max_long:
            self.coor_max_long = new_coor[0]
            redraw_needed = True
            
        if new_coor[1] < self.coor_min_lat:
            self.coor_min_lat = new_coor[1]
            redraw_needed = True
        elif new_coor[1] > self.coor_max_lat:
            self.coor_max_lat = new_coor[1]
            redraw_needed = True

        if redraw_needed:
            can_w = MAIN_WINDOW_WIDTH * 2 // 3
            can_h = MAIN_WINDOW_HEIGHT

            self.px_per_minute = min(can_w / (self.coor_max_long - self.coor_min_long),
                                     can_h / (self.coor_max_lat - self.coor_min_lat))

            self.can_base = ((self.coor[0][0] - self.coor_min_long) * self.px_per_minute,
                             can_h - (self.coor[0][1] - self.coor_min_lat) * self.px_per_minute)  # canvas center

            self.can.delete("all")
            for i in range(len(self.coor) - 1):
                self.draw_arc(self.coor[i], self.coor[i + 1])
        else:
            self.draw_arc(old_coor, new_coor)

        self.after(1000, self.updater)

    def draw_arc(self, old_coor, new_coor):
        delta_x = (new_coor[0] - old_coor[0]) * self.px_per_minute
        delta_y = -(new_coor[1] - old_coor[1]) * self.px_per_minute

        new_base_x = self.can_base[0] + delta_x
        new_base_y = self.can_base[1] + delta_y

        self.can.create_line(self.can_base[0], self.can_base[1],
                             new_base_x, new_base_y)

        self.can_base = (new_base_x, new_base_y)

    def on_closing(self):
        with open(SETTINGS_FILE, 'w') as file:
            json.dump(self.settings, file)  # save current settings
        self.destroy()


if __name__ == '__main__':
    top = Gui()
    top.mainloop()
