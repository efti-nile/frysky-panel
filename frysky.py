#!/usr/bin/python3
# coding=UTF-8

from tkinter.messagebox import showerror
from tkinter.simpledialog import askfloat
from tkinter import *
from frysky_parser import FrySkyParserThread
import os.path
import json
import serial
from PIL import Image
from tkinter import filedialog

MAIN_WINDOW_TITLE = 'FrySky View Panel'
COM_SETTINGS_TITLE = 'COM settings'
MAIN_WINDOW_HEIGHT = 600
MAIN_WINDOW_WIDTH = 900
CANVAS_MARGIN_PX = 50

SETTINGS_BUTTON_PROMPT = 'ctrl + \'S\': COM settings'
OPEN_DUMP_FILE_PROMPT = 'ctrl + \'D\': open dump file'
STOP_PARSING_PROMPT = 'ctrl + \'C\': stop parsing'

STD_BAUDRATES_TABLE = ['9600', '19200', '38400', '115200']

CELL_CAPTION_WIDTH = 18

SETTINGS_FILE = 'settings.json'
MAP_FILE = 'map.png'

MAP_LONG_MIN = 53.32605 - 0.01
MAP_LONG_MAX = (53.32605 + 0.03578) + 0.01
MAP_LAT_MIN = 50.21002 - 0.01
MAP_LAT_MAX = 50.2458 + 0.01
MAP_WIDTH = 0.05578


class Gui(Tk):
    cells = (
        {'caption': 'Signal level',    'name': 'sig_lev',  'cell': None},
        {'caption': 'Current, A',      'name': 'cur',      'cell': None},
        {'caption': 'Voltage, V',      'name': 'vlt',      'cell': None},
        {'caption': 'Rot. freq., RPM', 'name': 'rot_freq', 'cell': None}
    )

    coor = []

    px_per_deg = 100.0 * 1000.0  # 100 pixels per 0.001 minute of angle (1.85 m)

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

        self.top_prompt = Label(inpan, text=SETTINGS_BUTTON_PROMPT, anchor='s')
        self.btm_prompt = Label(inpan, text=OPEN_DUMP_FILE_PROMPT, anchor='s')
        self.top_prompt.grid(row=1, column=0, sticky='S')
        self.btm_prompt.grid(row=2, column=0, sticky='S')

        self.can = Canvas(self, width=MAIN_WINDOW_WIDTH * 2 // 3, height=MAIN_WINDOW_HEIGHT,
                          background='#ffffff')
        self.can.grid(row=0, column=1, columnspan=2)
        self.can_base = (MAIN_WINDOW_WIDTH // 3, MAIN_WINDOW_HEIGHT // 2)  # canvas center

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

        self.img = Image.open(MAP_FILE)

        self.csd = None
        self.com_port = None
        self.dump_file = None
        self.parser = None
        self.leading_mark = None
        self.img_res = None
        self.img_rescrop = None
        self.canv = None

        self.coor_min_long, self.coor_max_long = 361.0, -1.0
        self.coor_min_lat, self.coor_max_lat = 361.0, -1.0

        self.set_idle_app_state()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def set_idle_app_state(self, event=None):
        self.bind('<Control-s>', self.open_com_settings_dialog)
        self.bind('<Control-d>', self.open_dump_file)
        self.unbind('<Control-c>')
        self.top_prompt.config(text=SETTINGS_BUTTON_PROMPT)
        self.btm_prompt.config(text=OPEN_DUMP_FILE_PROMPT)
        if self.com_port:
            self.com_port.close()
            self.com_port = None
        if self.dump_file:
            self.dump_file = None
        if self.parser:
            self.parser.term_sig = True
            self.parser = None
        self.coor = []

    def set_active_app_state(self):
        self.unbind('<Control-s>',)
        self.unbind('<Control-d>')
        self.bind('<Control-c>', self.set_idle_app_state)
        self.top_prompt.config(text=STOP_PARSING_PROMPT)
        self.btm_prompt.config(text='')

    def open_com_settings_dialog(self, event):
        self.csd = Toplevel(self)
        self.csd.title(COM_SETTINGS_TITLE)
        Label(self.csd, text='COM port:').grid(row=0, column=0)
        self.csd.com_str = StringVar()
        if 'com_str' in self.settings:
            self.csd.com_str.set(self.settings['com_str'])
        self.csd.com_str_entry = Entry(self.csd, textvariable=self.csd.com_str)
        self.csd.com_str_entry.grid(row=0, column=1)
        Label(self.csd, text='Baudrate:').grid(row=1, column=0)
        self.csd.baudrate_listbox = Listbox(self.csd)
        for item in STD_BAUDRATES_TABLE:
            self.csd.baudrate_listbox.insert(END, item)
        if 'baudrate_idx' in self.settings:
            self.csd.baudrate_listbox.select_set(self.settings['baudrate_idx'])
        self.csd.baudrate_listbox.grid(row=1, column=1)
        self.csd.ok_button = Button(self.csd, text='Open COM port', command=self.open_com_port)
        self.csd.ok_button.grid(row=2, column=0, columnspan=2)
        
    def open_com_port(self):
        com_str = self.csd.com_str.get()
        if not com_str:
            showerror('Error', 'Specify COM-port')
            return
        baudrate_idx = self.csd.baudrate_listbox.curselection()
        if not baudrate_idx:
            showerror('Error', 'Specify baud rate')
            return
        baudrate_idx = baudrate_idx[0]
        baudrate = STD_BAUDRATES_TABLE[baudrate_idx]
        self.settings['com_str'] = com_str
        self.settings['baudrate_idx'] = baudrate_idx
        try:
            self.com_port = serial.Serial(com_str, baudrate)
        except serial.SerialException:
            showerror('Error', 'Can\'t open specified port')
            return
        self.parser = FrySkyParserThread(self.com_port)
        self.parser.start()
        self.set_active_app_state()
        self.after(10, self.updater)
        self.csd.destroy()

    def open_dump_file(self, event):
        dump_file_name = filedialog.askopenfilename(filetypes=(('binary', '*.bin'), ('all', '*.*')))
        if not dump_file_name:
            showerror('Error', 'No file selected')
            return
        if not os.path.exists(dump_file_name):
            showerror('Error', 'File not found')
            return
        delay_ms = askfloat('Input', 'Which UI delay set between packets (ms)?')
        if delay_ms is None:
            delay_ms = 0.0
        self.dump_file = open(dump_file_name, 'rb')
        self.parser = FrySkyParserThread(self.dump_file)
        self.parser.set_pause(delay_ms)
        self.parser.start()
        self.set_active_app_state()
        self.after(10, self.updater)

    def updater(self):
        if not self.parser:
            return

        self.parser.lock.acquire(blocking=1)
        new_params = self.parser.out_params
        self.parser.out_params = []
        self.parser.lock.release()

        for par_name, par in new_params:
            if par_name == 'coor':
                new_coor = par
                self.coor.append(new_coor)
                if len(self.coor) == 1:
                    delta = 0.01
                    self.coor_max_long = new_coor[0] + delta
                    self.coor_max_lat = new_coor[1] + delta
                    self.coor_min_long = new_coor[0] - delta
                    self.coor_min_lat = new_coor[1] - delta
                    self.px_per_deg = float(MAIN_WINDOW_HEIGHT) * 0.5 / delta
                    redraw_needed = True
                else:
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
                    can_w = float(MAIN_WINDOW_WIDTH) * 2.0 / 3
                    can_h = float(MAIN_WINDOW_HEIGHT)

                    self.px_per_deg = min(can_w / float(self.coor_max_long - self.coor_min_long),
                                          can_h / float(self.coor_max_lat - self.coor_min_lat))

                    self.can_base = ((self.coor[0][0] - self.coor_min_long) * self.px_per_deg,
                                     can_h - (self.coor[0][1] - self.coor_min_lat) * self.px_per_deg)  # canvas center

                    # calc map scale
                    map_px_width = round(float(MAP_WIDTH) * self.px_per_deg)
                    map_trans = float(map_px_width) / float(self.img.size[0])
                    map_px_height = round(float(self.img.size[1]) * float(map_trans))

                    # transform
                    self.img_res = self.img.resize((map_px_width, map_px_height), Image.ANTIALIAS)

                    # calculate coordinates of lower left corner
                    margin_deg = float(CANVAS_MARGIN_PX) / self.px_per_deg
                    long_llcc = self.coor_min_long - margin_deg
                    lat_llcc = self.coor_min_lat - margin_deg

                    # calculate map coordinates
                    map_x_offset = round((long_llcc - MAP_LONG_MIN) * self.px_per_deg)
                    map_y_offset = round(float(map_px_height) - (lat_llcc - MAP_LAT_MIN) * self.px_per_deg - can_h)

                    self.img_rescrop = self.img_res.crop((map_x_offset, map_y_offset,
                                                          map_x_offset + can_w, map_y_offset + can_h))
                    self.img_rescrop.save('tmp.png')
                    self.canv = PhotoImage(file='tmp.png')

                    self.can.delete("all")
                    self.can.create_image(300, 300, image=self.canv)
                    for i in range(len(self.coor) - 1):
                        self.draw_arc(self.coor[i], self.coor[i + 1])
                else:
                    old_coor = self.coor[-2]
                    self.draw_arc(old_coor, new_coor)
            else:
                list(filter(lambda cell: cell['name'] == par_name, self.cells))[0]['cell'].configure(text=str(round(par, 2)))

        self.after(1000, self.updater)

    def draw_arc(self, old_coor, new_coor):
        delta_x = (new_coor[0] - old_coor[0]) * self.px_per_deg
        delta_y = -(new_coor[1] - old_coor[1]) * self.px_per_deg

        new_base_x = self.can_base[0] + delta_x
        new_base_y = self.can_base[1] + delta_y
        
        x1, y1 = self.can_base[0], self.can_base[1]
        x2, y2 = new_base_x, new_base_y

        can_w = MAIN_WINDOW_WIDTH * 2 // 3
        can_h = MAIN_WINDOW_HEIGHT
        
        x1_ = (x1 - can_w / 2) * ((can_w - CANVAS_MARGIN_PX) / can_w) + can_w / 2
        y1_ = (y1 - can_h / 2) * ((can_h - CANVAS_MARGIN_PX) / can_h) + can_h / 2

        x2_ = (x2 - can_w / 2) * ((can_w - CANVAS_MARGIN_PX) / can_w) + can_w / 2
        y2_ = (y2 - can_h / 2) * ((can_h - CANVAS_MARGIN_PX) / can_h) + can_h / 2
        
        self.can.create_line(x1_, y1_, x2_, y2_, smooth=1, width=2, fill='#ee1111')
        self.can_base = (new_base_x, new_base_y)

        self.can.create_oval(x2_ - 3, y2_ - 3, x2_ + 3, y2_ + 3, fill='green')

        if self.leading_mark:
            self.can.delete(self.leading_mark)
        self.leading_mark = self.can.create_oval(x2_ - 4, y2_ - 4, x2_ + 4, y2_ + 4, fill='red')

    def on_closing(self):
        with open(SETTINGS_FILE, 'w') as file:
            json.dump(self.settings, file)  # save current settings
        self.destroy()


if __name__ == '__main__':
    top = Gui()
    top.mainloop()
