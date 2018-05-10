from random import random

coor = (53.2415, 50.2212)
STEP = 0.001


def next_rand_coord():
    global coor
    coor = (coor[0] + STEP * (random() - 0.5),
            coor[1] + STEP * (random() - 0.5))
    return coor

