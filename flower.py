

from turtle import *

import colorsys

speed(0)

bgcolor("black")

pensize(2)


for i in range(16):

    for j in range(15):

        c=colorsys.hsv_to_rgb(i/15,j/20,1)
        color(c)
        rt(90)
        circle(200-j*6,90)
        lt(90)
        circle(200-j*6,90)
        rt(180)
    circle(60,24)

done()