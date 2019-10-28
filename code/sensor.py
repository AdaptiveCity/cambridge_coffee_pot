#! /usr/bin/python3

# for dev / debug
DEBUG_LOG = False

# info sent in json packet to feed handler
SENSOR_ID = 'cambridge_coffee_pot'
SENSOR_TYPE = 'coffee_pot'
ACP_TOKEN = 'testtoken'

# linear calibration of A channels of both hx711
SCALE_REF_1 = 384.1 # grams per reading value
SCALE_REF_2 = 356.0

# Python libs
import time
import sys
import RPi.GPIO as GPIO
import simplejson as json
import requests

# D to A converter libs
from hx711_ijl20.hx711 import HX711

# LCD display libs
from st7735_ijl20.st7735 import ST7735

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageColor

# LCD panel size in pixels (0,0) is top left
DISPLAY_WIDTH = 160                # LCD panel width in pixels
DISPLAY_HEIGHT = 128               # LCD panel height

# Pixel size and coordinates of the 'Weight' display
DISPLAY_WEIGHT_HEIGHT = 40
DISPLAY_WEIGHT_WIDTH = 160
DISPLAY_WEIGHT_COLOR_FG = "WHITE"
DISPLAY_WEIGHT_COLOR_BG = "BLACK"
DISPLAY_WEIGHT_X = 0
DISPLAY_WEIGHT_Y = 60
DISPLAY_WEIGHT_RIGHT_MARGIN = 10


FONT = ImageFont.truetype('fonts/Ubuntu-Regular.ttf', 40)
DEBUG_FONT = ImageFont.truetype('fonts/Ubuntu-Regular.ttf', 14)

def init_lcd():
    t_start = time.process_time()

    LCD = ST7735()

    #Lcd_ScanDir = LCD_1in8.SCAN_DIR_DFT  #SCAN_DIR_DFT = D2U_L2R
    #LCD.LCD_Init(Lcd_ScanDir)

    LCD.begin()

    image = Image.open('pot.bmp')
    #LCD.LCD_PageImage(image)
    LCD.display(image)

    if DEBUG_LOG:
        print("init_lcd in {:.3f} sec.".format(time.process_time() - t_start))

    return LCD

# Initialize scales, return hx711 objects
# Note there are TWO load cells, each with their own HX711 A/D converter.
# Each HX711 has an A and a B channel, we are only using the A channel of each.
def init_scales():

    t_start = time.process_time()

    hx_1 = HX711(5, 6) # first hx711, connected to load cell 1
    hx_1.DEBUG_LOG = DEBUG_LOG

    hx_2 = HX711(12, 13) # second hx711, connected to load cell 2
    hx_2.DEBUG_LOG = DEBUG_LOG

    if DEBUG_LOG:
        print("init_scales HX objects created at {:.3f} secs.".format(time.process_time() - t_start))

    # set_reading_format(order bytes to build the "long" value, order of the bits inside each byte) MSB | LSB
    # According to the HX711 Datasheet, the second parameter is MSB so you shouldn't need to modify it.
    hx_1.set_reading_format("MSB", "MSB")
    hx_2.set_reading_format("MSB", "MSB")

    hx_1.set_reference_unit_A(SCALE_REF_1)
    hx_2.set_reference_unit_A(SCALE_REF_2)

    hx_1.reset()
    hx_2.reset()

    if DEBUG_LOG:
        print("init_scales HX objects reset at {:.3f} secs.".format(time.process_time() - t_start))

    # Here we initialize the 'empty weight' settings
    hx_1.tare_A()

    if DEBUG_LOG:
        print("init_scales tare 1 completed at {:.3f} secs.".format(time.process_time() - t_start))

    hx_2.tare_A()

    if DEBUG_LOG:
        print("init_scales tare 2 completed at {:.3f} secs.".format(time.process_time() - t_start))

    return [ hx_1, hx_2 ]

# Return the weight in grams, combined from both load cells
def get_weight():
    global hx # hx is [ hx_1, hx_2 ]
    global debug_weight1, debug_weight2

    t_start = time.process_time()

    # get_weight accepts a parameter 'number of times to sample weight and then average'
    weight_1 = hx[0].get_weight_A(1)
    debug_weight1 = weight_1 # store weight for debug display

    if DEBUG_LOG:
        print("init_scales weight_1 {:5.1f} completed at {:.3f} secs.".format(weight_1, time.process_time() - t_start))

    weight_2 = hx[1].get_weight_A(1)
    debug_weight2 = weight_2 # store weight for debug display

    if DEBUG_LOG:
        print("init_scales weight_2 {:5.1f} completed at {:.3f} secs.".format(weight_2, time.process_time() - t_start))

    return weight_1  + weight_2 # grams

# Update a PIL image with the weight, and send to LCD
# Note we are creating an image smaller than the screen size, and only updating a part of the display
def update_lcd(weight_g):
    global LCD

    t_start = time.process_time()

    # create a blank image to write the weight on
    image = Image.new("RGB", (DISPLAY_WEIGHT_WIDTH, DISPLAY_WEIGHT_HEIGHT), DISPLAY_WEIGHT_COLOR_BG)
    draw = ImageDraw.Draw(image)

    # convert weight to string with fixed 5 digits including 1 decimal place, max 9999.9

    if weight_g >= 10000:
        weight_g = 9999.9

    draw_string = "{:5.1f}".format(weight_g) # 10 points for witty variable name

    # calculate x coordinate necessary to right-justify text
    string_width, string_height = draw.textsize(draw_string, font=FONT)

    # embed this number into the blank image we created earlier
    draw.text((DISPLAY_WEIGHT_WIDTH-string_width-DISPLAY_WEIGHT_RIGHT_MARGIN,0),
              draw_string,
              fill = DISPLAY_WEIGHT_COLOR_FG,
              font=FONT)

    # display image on screen at coords x,y. (0,0)=top left.
    #LCD.LCD_ShowImage(image,
    LCD.display_window(image,
                      DISPLAY_WEIGHT_X,
                      DISPLAY_WEIGHT_Y,
                      DISPLAY_WEIGHT_WIDTH,
                      DISPLAY_WEIGHT_HEIGHT)

    # DEBUG: display the debug weights (from each load cell) if they've been set
    if debug_weight1 != 0:
        image = Image.new("RGB", (50, 40), "BLACK")
        draw = ImageDraw.Draw(image)
        draw_string = "{:5.1f}".format(debug_weight1)
        draw.text((0,0), draw_string, fill="YELLOW", font=DEBUG_FONT)
        draw_string = "{:5.1f}".format(debug_weight2)
        draw.text((0,20), draw_string, fill="YELLOW", font=DEBUG_FONT)
        LCD.display_window(image, 110, 5, 50, 40)

    if DEBUG_LOG:
        print("LCD updated with weight in {:.3f} secs.".format(time.process_time() - t_start))

def cleanAndExit():
    print(" GPIO cleanup()...")

    GPIO.cleanup()

    sys.exit()

def send_data(post_data, token):
    response = requests.post('https://tfc-app2.cl.cam.ac.uk/test/feedmaker/test/general',
              headers={'X-Auth-Token': token },
              json=post_data
              )

    print("status code",response.status_code)

def init():
    global LCD
    global hx
    LCD = init_lcd()
    hx = init_scales()

def loop():
    prev_time = time.time() # floating point seconds in epoch

    while True:
        try:
            t_start = time.process_time()
            # get readings from A and B channels
            weight_g = get_weight()

            if DEBUG_LOG:
                print("loop got weight at {:.3f} secs.".format(time.process_time() - t_start))

            update_lcd(weight_g)

            if DEBUG_LOG:
                print("loop update_lcd at {:.3f} secs.".format(time.process_time() - t_start))

            now = time.time() # floating point time in seconds since epoch
            if now - prev_time > 30:
                print ("SENDING WEIGHT {:5.1f}, {}".format(weight_g, time.ctime(now)))
                post_data = { 'request_data': [ { 'acp_id': SENSOR_ID,
                                                  'acp_type': SENSOR_TYPE,
                                                  'acp_ts': now,
                                                  'weight': weight_g,
                                                  'acp_units': 'GRAMS'
                                                 }
                                              ]
                            }
                send_data(post_data, ACP_TOKEN)
                prev_time = now

                if DEBUG_LOG:
                    print("loop send data at {:.3f} secs.".format(time.process_time() - t_start))

            elif DEBUG_LOG:
                print ("WEIGHT {:5.1f}, {}".format(weight_g, time.ctime(now)))

            #hx.power_down()
            #hx.power_up()

            if DEBUG_LOG:
                print("loop time (before sleep) {:.3f} secs.".format(time.process_time() - t_start))

            time.sleep(1.0)

        except (KeyboardInterrupt, SystemExit):
            cleanAndExit()

# globals
LCD = None # ST7735 LCD display chip
hx = None # LIST of hx711 A/D chips

debug_weight1 = 0.0 # weights from each load cell, for debug
debug_weight2 = 0.0

# Initialize everything
init()

# Infinite loop until killed, reading weight and sending data
loop()


