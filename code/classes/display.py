    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # Display code
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------

import time
import math
from datetime import datetime
from pytz import timezone

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageColor

VALUE_FONT = ImageFont.truetype('fonts/Ubuntu-Regular.ttf', 30)
NEW_FONT = ImageFont.truetype('fonts/Ubuntu-Regular.ttf', 20)
DEBUG_FONT = ImageFont.truetype('fonts/Ubuntu-Regular.ttf', 14)

# ST7735 color mappings
str_to_color = { "YELLOW": 0xFFE0,    # yellow 565 RGB
                 "BLUE": 0x001F    # blue 565 RGB
               }

CHART_SETTINGS = { "x": 0, "y": 100, "w": 160, "h": 28, # 'pixels' top-left coords and width, height.
                "step": 1,             # 'pixels': how many pixels to step in x direction for next()
                "time_scale": 0.1,      # 'seconds per pixel' x-scale for Bar add_time(timestamp, height_pixels )
                "bar_width": 1,        # 'pixels', width of value column
                "point_height": None,  # 'pixels', will display point of this height, not column to x-axis
                "cursor_width": 2,     # 'pixels', width of scrolling cursor
                "fg_color": [ 0xFF, 0xE0 ],    # yellow 565 RGB
                "bg_color": [ 0x00, 0x1F ],    # blue 565 RGB
                "cursor_color": [ 0x00, 0x00 ] # black 565 RGB
              }

VALUE_SETTINGS = {
    "VALUE_X": 59,
    "VALUE_Y": 70,
    "VALUE_WIDTH": 101,
    "VALUE_HEIGHT": 30,
    "VALUE_COLOR_FG": "WHITE",
    "VALUE_COLOR_BG": "BLUE",
    "VALUE_RIGHT_MARGIN": 10,

    "NEW_X": 59,
    "NEW_Y": 0,
    "NEW_WIDTH": 101,
    "NEW_HEIGHT": 18,
    "NEW_COLOR_FG": "BLUE",
    "NEW_COLOR_BG": "WHITE",

    "POT_X": 0,
    "POT_Y": 0,
    "POT_FG": "YELLOW",
    "POT_BG": "BLUE",
}

class Display(object):

    def __init__(self, settings=None, emulate=False):

        if emulate:
            from st7735_ijl20.st7735_emulator import ST7735_EMULATOR as ST7735
        else:
            from st7735_ijl20.st7735 import ST7735

        if settings is not None:
            self.settings = { **VALUE_SETTINGS, **settings }
        else:
            self.settings = VALUE_SETTINGS

        # Disable LCD display updates (e.g. for faster execution) if "DISPLAY": False in settings
        if 'DISPLAY' in self.settings and self.settings['DISPLAY'] == False:
            return
            
        if not "LOG_LEVEL" in self.settings:
            self.settings["LOG_LEVEL"] = 2

        t_start = time.process_time()

        self.prev_lcd_time = None

        self.prev_new_str = None # used to check if "new pot" string has changed so write.
        self.new_str = None

        self.LCD = ST7735()

        self.LCD.begin()

        image = Image.open('images/pot.bmp')
        #LCD.LCD_PageImage(image)
        self.LCD.display(image)

        self.pot = Pot(LCD=self.LCD,
                       x=self.settings["POT_X"],
                       y=self.settings["POT_Y"],
                       settings=self.settings)

        print("init_lcd in {:.3f} sec.".format(time.process_time() - t_start))

    # ------------------
    # Initial display
    # ------------------
    def begin(self):
        # Disable LCD display updates (e.g. for faster execution) if "DISPLAY": False in settings
        if 'DISPLAY' in self.settings and self.settings['DISPLAY'] == False:
            return
        self.chart = self.LCD.add_chart(CHART_SETTINGS)

        self.pot.begin()

    # -------------------------------------------------------------------
    # ------ DRAW NUMERIC VALUE ON LCD  ---------------------------------
    # -------------------------------------------------------------------
    def draw_value(self, value):
        # create a blank image to write the weight on
        image = Image.new( "RGB",
                           ( self.settings["VALUE_WIDTH"],
                             self.settings["VALUE_HEIGHT"]),
                           self.settings["VALUE_COLOR_BG"])

        draw = ImageDraw.Draw(image)

        # convert weight to string with fixed 5 digits including 1 decimal place, max 9999.9

        display_number = value

        if display_number >= 9999:
            display_number = 9999.1

        draw_string = "{:5.0f}".format(display_number) # 10 points for witty variable name

        # calculate x coordinate necessary to right-justify text
        string_width, string_height = draw.textsize(draw_string, font=VALUE_FONT)

        # embed this number into the blank image we created earlier
        draw.text((self.settings["VALUE_WIDTH"]-string_width-self.settings["VALUE_RIGHT_MARGIN"],-4),
                draw_string,
                fill = self.settings["VALUE_COLOR_FG"],
                font=VALUE_FONT)

        # display image on screen at coords x,y. (0,0)=top left.
        self.LCD.display_window(image,
                        self.settings["VALUE_X"],
                        self.settings["VALUE_Y"],
                        self.settings["VALUE_WIDTH"],
                        self.settings["VALUE_HEIGHT"])

    # -------------------------------------------------------------------
    # ------ DRAW NEW POT TIME ON LCD  ---------------------------------
    # -------------------------------------------------------------------
    def draw_new(self, new_str):
        # create a blank image to write the weight on
        image = Image.new( "RGB",
                           ( self.settings["NEW_WIDTH"],
                             self.settings["NEW_HEIGHT"]),
                           self.settings["NEW_COLOR_BG"])

        draw = ImageDraw.Draw(image)

        # embed this number into the blank image we created earlier
        draw.text((5,-3),
                new_str,
                fill=self.settings["NEW_COLOR_FG"],
                font=NEW_FONT)

        # display image on screen at coords x,y. (0,0)=top left.
        self.LCD.display_window(image,
                        self.settings["NEW_X"],
                        self.settings["NEW_Y"],
                        self.settings["NEW_WIDTH"],
                        self.settings["NEW_HEIGHT"])

    # -------------------------------------------------------------------
    # ------ DRAW DEBUG READINGS ON LCD       ---------------------------
    # -------------------------------------------------------------------
    def draw_debug(self, debug_list):
        # display a two-line debug display of the weights from both load cells
        if self.settings["LOG_LEVEL"] <= 2:
            image = Image.new("RGB", (160, 40), "BLACK")
            draw = ImageDraw.Draw(image)

            draw_string = "{:5.1f}".format(debug_list[0])
            draw.text((75,0), draw_string, fill="YELLOW", font=DEBUG_FONT)

            draw_string = "{:5.1f}".format(debug_list[1])
            draw.text((75,20), draw_string, fill="YELLOW", font=DEBUG_FONT)

            draw_string = "{:5.1f}".format(debug_list[2])
            draw.text((0,20), draw_string, fill="YELLOW", font=DEBUG_FONT)

            draw_string = "{:5.1f}".format(debug_list[3])
            draw.text((0,0), draw_string, fill="YELLOW", font=DEBUG_FONT)

            self.LCD.display_window(image, 0, 40, 160, 40)

    def update_new(self, ts):
        # Disable LCD display updates (e.g. for faster execution) if "DISPLAY": False in settings
        if 'DISPLAY' in self.settings and self.settings['DISPLAY'] == False:
            return
        self.new_str = datetime.fromtimestamp(ts,timezone('Europe/London')).strftime("%a %H:%M")

    # Update a PIL image with the weight, and send to LCD
    # Note we are creating an image smaller than the screen size, and only updating a part of the display
    def update(self, ts, sample_buffer, debug_list):

        # Disable LCD display updates (e.g. for faster execution) if "DISPLAY": False in settings
        if 'DISPLAY' in self.settings and self.settings['DISPLAY'] == False:
            return

        t_start = time.process_time()

        if (self.prev_lcd_time is None) or (ts - self.prev_lcd_time > 1):

            # get median weight value for 1 second
            sample_median, offset, duration, sample_count = sample_buffer.median(0,1)
            # get deviation from median over 1 second
            sample_deviation, offset, duration, sample_count = sample_buffer.deviation(0,1,sample_median)

            if not sample_median is None:

                self.draw_value(sample_median)

                # if level is stable then update pot level
                if not sample_deviation is None and sample_deviation < 30:
                    max_coffee_weight = self.settings["WEIGHT_FULL"] - self.settings["WEIGHT_EMPTY"]
                    pot_ratio = (sample_median - self.settings["WEIGHT_EMPTY"]) / max_coffee_weight
                    if pot_ratio > 1:
                        pot_ratio = 1
                    elif pot_ratio < 0.04: # Force to zero if little coffee in pot
                        pot_ratio = 0

                    self.pot.update(pot_ratio)

            if self.new_str != self.prev_new_str:
                self.draw_new(self.new_str)
                self.prev_new_str = self.new_str

            self.prev_lcd_time = ts

            if self.settings["LOG_LEVEL"] == 1:
                if sample_median == None:
                    print("loop update_lcd skipped (None) at {:.3f} secs.".format(time.process_time() - t_start))
                else:
                    print("loop update_lcd {:.1f} at {:.3f} secs.".format(sample_median, time.process_time() - t_start))

            # draw_debug() is disabled
            #self.draw_debug(debug_list)

        # -------------------------------------------------------------------
        # ------ ADD CURRENT WEIGHT TO BAR CHART   --------------------------
        # -------------------------------------------------------------------

        latest_sample = sample_buffer.get(0)
        if not latest_sample == None:
            # debug: need to link these constants to the actual bar settings...
            BAR_MAX_G = 5000
            BAR_MAX_Y = 40

            # Create a bar height proportional to the value, capped at bottom and top of chart.
            bar_height = math.floor(latest_sample["value"] / BAR_MAX_G * BAR_MAX_Y )

            if bar_height > BAR_MAX_Y:
                bar_height = BAR_MAX_Y
            elif bar_height < 1:
                bar_height = 1

            # This is a bar-per-sample. Could use time on x-axis.
            #self.chart.next(bar_height)
            self.chart.add_time(ts, bar_height)

    def finish(self):
        self.LCD.cleanup()

# Vertical bar display object
class VerticalBar(object):

    def __init__(self, LCD=None, x=0, y=0, w=40, h=128, settings=None):
        self.LCD = LCD

        # set pot coordinates on display
        self.x = x
        self.y = y
        self.w = w
        self.h = h

        # Set fg and bg colors
        if settings is None or not "POT_FG" in settings:
            self.FG_COLOR =str_to_color["YELLOW"]
        else:
            self.FG_COLOR = str_to_color[settings["POT_FG"]]

        if settings is None or not "POT_BG" in settings:
            self.BG_COLOR = str_to_color["BLUE"]
        else:
            self.BG_COLOR = str_to_color[settings["POT_BG"]]


    def begin(self):

        self.LCD.set_rectangle_color(self.x, self.y, self.w, self.h, self.BG_COLOR)

        self.prev_y = self.y + self.h


    # convert a 'full' ratio 0..1 to a y pixel offset from top of screen.
    def ratio_to_y(self, ratio):

        # ratio is 0..1
        return math.floor(self.y + self.h * (1 - ratio))

    # Update the displayed vertical bar
    def update(self, ratio):

        new_y = self.ratio_to_y(ratio)

        if new_y < self.prev_y:
            # new ratio was higher
            # add foreground pixels
            h = self.prev_y - new_y
            self.LCD.set_rectangle_color(self.x, new_y, self.w, h, self.FG_COLOR)
        elif new_y > self.prev_y:
            # new ratio was lower
            # reduce bar by adding background pixels
            h = new_y - self.prev_y
            self.LCD.set_rectangle_color(self.x, self.prev_y, self.w, h, self.BG_COLOR)

        self.prev_y = new_y

# Coffee Pot display object
class Pot(object):

    def __init__(self, LCD=None, x=0, y=28, settings=None):
        self.LCD = LCD

        # set pot coordinates on display
        self.x = x
        self.y = y
        self.w = 59
        self.h = 100
        self.bar_y_0 = self.h - 18 # level y-pixel for ratio=0
        self.bar_h = self.h - 52
        self.BG_COLOR = 0xFFFF
        self.FG_COLOR = 0x4145
        self.custom = [ self.LCD.image_to_data(Image.open('images/pot_0.png')),
                  self.LCD.image_to_data(Image.open('images/pot_1.png')),
                  self.LCD.image_to_data(Image.open('images/pot_2.png')),
                  self.LCD.image_to_data(Image.open('images/pot_3.png')),
                  self.LCD.image_to_data(Image.open('images/pot_4.png')),
                  self.LCD.image_to_data(Image.open('images/pot_5.png')),
                  self.LCD.image_to_data(Image.open('images/pot_6.png')),
                  self.LCD.image_to_data(Image.open('images/pot_7.png')),
                  self.LCD.image_to_data(Image.open('images/pot_8.png')),
                  self.LCD.image_to_data(Image.open('images/pot_9.png'))
        ]
        self.level_top = self.LCD.image_to_data(Image.open('images/pot_top.png'))
        self.level_base = self.LCD.image_to_data(Image.open('images/pot_0_normal.png'))

    def begin(self):
        # 59 x 100
        image = Image.open('images/pot_background.png')

        self.LCD.display_window(image, self.x, self.y, self.w, self.h)

        # These vars keep track of the previous level set, so we can optimise update()
        # record whether the previous reading was a custom image
        self.prev_y = self.y + 35 # record the 'previous' y-pixel of coffee amount
        self.prev_custom = False   # True if the previous level was set with a custom image
        self.prev_y_fill_down = 0 # display y-pixel to fill DOWN to if next value HIGHER

        self.update(0)


    # convert a 'full' ratio 0..1 to a y pixel offset from top of screen.
    def ratio_to_y(self, ratio):

        # ratio is 0..1
        return math.floor(self.y + self.bar_y_0 - self.bar_h * ratio)

    # Update the displayed vertical coffee level
    def update(self, ratio):

        #print("update pot_ratio", ratio)

        # new_y is the display y-offset of the amount of coffee
        #
        new_y = self.ratio_to_y(ratio)

        # if y offset of coffee is unchanged, then do nothing.

        if new_y == self.prev_y:
            return

        # check if previous display was a custom image, if so update base of pot
        if self.prev_custom:
            #print("was custom", self.prev_y)
            base_x = self.x
            base_y = self.y + self.bar_y_0 + 6
            base_w = 59
            base_h = 12
            self.LCD.set_window(base_x, base_y, base_w, base_h)
            self.LCD.send_data(self.level_base)
            self.prev_y_fill_down = base_y

        # width of top image to draw
        w = 41          # will alter for pot_0
        x = self.x+9    # will alter for pot_0

        # zero_offset is 0..9, index of image to use for bottom of pot
        zero_offset = self.y + self.bar_y_0 - new_y

        # if zero_offset is NOT within set of images in custom list
        if zero_offset >= len(self.custom):
            # not custom image required
            top_image = self.level_top
            h = 14
        else:
            # custom image required
            #print("zero_offset", zero_offset)
            h = zero_offset + 12
            top_image = self.custom[zero_offset]

        #print("height of image",h)

        # ----------------------------------------
        # display image and fill to previous image
        # ----------------------------------------
        if new_y < self.prev_y:
            #print("more coffee")
            # new ratio is higher than previous (y offset is DOWN the display)
            # add foreground pixels
            self.LCD.set_window(x, new_y, w, h)
            self.LCD.send_data(top_image)

            # if we have NOT used a custom image
            if zero_offset >= len(self.custom):
                # fill in an area below this top_image
                fill_x = self.x + 9
                fill_y = new_y + 14
                fill_w = 41
                fill_h = self.prev_y_fill_down - fill_y

                #print("filling", fill_x, fill_y, fill_w, fill_h)
                self.LCD.set_rectangle_color(fill_x, fill_y, fill_w, fill_h, self.FG_COLOR)

        elif new_y > self.prev_y:
            #print("less coffee")
            # new ratio was lower
            # reduce bar by adding background pixels
            if zero_offset == 0:
                zero_x = self.x
                zero_y = new_y+6 # image for zero coffee is taller.
                zero_w = 59
                zero_h = 12
                self.LCD.set_window(zero_x, zero_y, zero_w, zero_h)
            else:
                self.LCD.set_window(x, new_y, w, h)
            self.LCD.send_data(top_image)

            # fill in an area above this top_image
            fill_x = self.x + 9
            fill_y = self.prev_y
            fill_w = 41
            if zero_offset == 0:
                fill_h = new_y - self.prev_y + 6
            else:
                fill_h = new_y - self.prev_y
            #print("filling", fill_x, fill_y, fill_w, fill_h)
            self.LCD.set_rectangle_color(fill_x, fill_y, fill_w, fill_h, self.BG_COLOR)

        self.prev_custom = zero_offset < len(self.custom)
        self.prev_y_fill_down = new_y + 14
        #print("new_y was", new_y)
        #print("prev_custom", self.prev_custom)
        self.prev_y = new_y




