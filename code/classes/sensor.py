#! /usr/bin/python3

# code version

VERSION = "0.50"

# Python libs
import time
import sys
import simplejson as json
import requests
import math

GPIO_FAIL = False
try:
    import RPi.GPIO as GPIO
except ImportError:
    GPIO_FAIL = True
    print("RPi.GPIO not loaded, running in SIMULATION_MODE")

# General utility function (like list_to_string)
from classes.sensor_utils import list_to_string

from classes.time_buffer import TimeBuffer

from classes.display import Display

# Data for pattern recognition

SAMPLE_HISTORY_SIZE = 1000
EVENT_HISTORY_SIZE = 5 # keep track of the most recent 5 events sent to server

# COFFEE POT EVENTS

EVENT_NEW = "COFFEE_NEW"
EVENT_EMPTY = "COFFEE_EMPTY"
EVENT_POURED = "COFFEE_POURED"
EVENT_REMOVED = "COFFEE_REMOVED"
EVENT_GROUND = "COFFEE_GROUND"

debug_list = [ 1, 2, 3, 4] # weights from each load cell, for debug display on LCD

class Sensor(object):

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # __init__() called on startup
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------

    def __init__(self, settings=None):
        global GPIO_FAIL

        self.SIMULATION_MODE = GPIO_FAIL

        self.settings = settings

        # times to control watchdog sends to platform
        self.prev_send_time = None

        self.display = Display(self.settings, self.SIMULATION_MODE)

        self.sample_buffer = TimeBuffer(size=SAMPLE_HISTORY_SIZE, settings=self.settings)

        self.event_buffer = TimeBuffer(size=EVENT_HISTORY_SIZE, settings=self.settings)


    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # SEND DATA TO PLATFORM
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------

    # Post data to platform as json.
    # post_data is a python dictionary to be converted to json.
    def send_data(self, post_data):
        try:
            print("send_data() to {}".format(self.settings["FEEDMAKER_URL"]))
            if not self.SIMULATION_MODE:
                response = requests.post(
                        self.settings["FEEDMAKER_URL"],
                        headers={ self.settings["FEEDMAKER_HEADER_KEY"] : self.settings["FEEDMAKER_HEADER_VALUE"] },
                        json=post_data
                        )
                print("status code:",response.status_code)

            debug_str = json.dumps( post_data,
                                    sort_keys=True,
                                    indent=4,
                                    separators=(',', ': '))
            print("sent:\n {}".format(debug_str))
        except Exception as e:
            print("send_data() error with {}".format(post_data))
            print(e)

    def send_weight(self, ts, weight_g):
        post_data = {  'msg_type': 'coffee_pot_weight',
                    'request_data': [ { 'acp_id': self.settings["SENSOR_ID"],
                                        'acp_type': self.settings["SENSOR_TYPE"],
                                        'acp_ts': ts,
                                        'acp_units': 'GRAMS',
                                        'weight': math.floor(weight_g+0.5), # rounded to integer grams
                                        'version': VERSION
                                        }
                                    ]
                }
        self.send_data(post_data)

    def send_event(self, ts, event_data):

        message_data = { 'acp_id': self.settings["SENSOR_ID"],
                         'acp_type': self.settings["SENSOR_TYPE"],
                         'acp_ts': ts,
                         'version': VERSION
                       }

        # merge dictionaries
        message_data = { **message_data, **event_data }

        post_data = { 'msg_type': 'coffee_pot_event',
                    'request_data': [ message_data ]
                }
        self.send_data(post_data)

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # EVENT PATTERN RECOGNITION
    #
    # In general these routines look at the sample_history buffer and
    # decide if an event has just become recognizable, e.g. POT_NEW
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------

    # Test if pot is FULL
    # True if median for 1 second is 3400 grams +/- 400
    # Returns tuple <Test true/false>, < next offset >
    def test_full(self,offset):
        m, next_offset, duration, sample_count = self.sample_buffer.median(offset, 1)
        if not m == None:
            return (abs(m - 3400) < 400), next_offset
        else:
            return None, None

    # Test if pot is REMOVED
    # True if median for 3 seconds is 0 grams +/- 100
    # Returns tuple <Test true/false>, < next offset >
    def test_removed(self,offset):
        m, next_offset, duration, sample_count = self.sample_buffer.median(offset, 3)
        if not m == None:
            return (abs(m) < 100), next_offset
        else:
            return None, None

    def test_event_new(self, ts):
        # Is the pot full now ?
        full, offset = self.test_full(0)

        # Was it removed before ?
        removed, new_offset = self.test_removed(offset)

        if removed and full:
            latest_event = self.event_buffer.get(0)
            if ((latest_event is None) or
               (latest_event["value"] != EVENT_NEW) or
               (ts - latest_event["ts"] > 600 )):
                return EVENT_NEW

        return None

    def test_event_removed(self, ts):
        # Is the pot removed now ?
        removed_now, offset = self.test_removed(0)

        # Was it removed before ?
        removed_before, new_offset = self.test_removed(offset)

        if removed_now and not removed_before:
            latest_event = self.event_buffer.get(0)
            if ((latest_event is None) or
               (latest_event["value"] != EVENT_REMOVED) or
               (ts - latest_event["ts"] > 600 )):
                return EVENT_REMOVED

        return None

    # Look in the sample_history buffer (including latest) and try and spot a new event.
    # Uses the event_history buffer to avoid repeated messages for the same event
    def test_event(self, ts, weight_g):
        for test in [ self.test_event_new,
                      self.test_event_removed
                    ]:
            event = test(ts)
            if not event is None:
                self.event_buffer.put(ts, event)
                self.send_event(ts, { "event_code": event, "weight": weight_g } )
                break

        return event

    # --------------------------------------------------------------------------------------
    # --------------------------------------------------------------------------------------
    #
    # process_sample(timestamp, value)
    #
    # Here is where we process each sensor sample, updating the LCD and checking for events
    #
    # --------------------------------------------------------------------------------------
    # --------------------------------------------------------------------------------------
    def process_sample(self, ts, value):

        t_start = time.process_time()

        if self.settings["LOG_LEVEL"] == 1:
            print("process_sample got value {:.1f} at {:.3f} secs.".format(value, time.process_time() - t_start))

        # store weight and time in sample_history
        self.sample_buffer.put(ts, value)

        #----------------
        # UPDATE DISPLAY
        # ---------------

        self.display.update(ts, self.sample_buffer, debug_list)

        # ----------------------
        # SEND EVENT TO PLATFORM
        # ----------------------

        self.test_event(ts, value)

        # ---------------------
        # SEND DATA TO PLATFORM
        # ---------------------

        if self.prev_send_time is None:
            self.prev_send_time = ts

        if ts - self.prev_send_time > 30:
            sample_value, offset, duration, sample_count = self.sample_buffer.median(0,2) # from latest ts, back 2 seconds

            if not sample_value == None:
                print ("SENDING WEIGHT {:5.1f}, {}".format(sample_value, time.ctime(ts)))

                self.send_weight(ts, sample_value)

                self.prev_send_time = ts

                if self.settings["LOG_LEVEL"] == 1:
                    print("process_sample send data at {:.3f} secs.".format(time.process_time() - t_start))
            else:
                print("process_sample send data NOT SENT as data value None")

        if self.settings["LOG_LEVEL"] == 1:
            print ("WEIGHT {:5.1f}, {}".format(value, time.ctime(ts)))

        if self.settings["LOG_LEVEL"] == 1:
            print("process_sample time (before sleep) {:.3f} secs.\n".format(time.process_time() - t_start))

    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------
    # finish() - cleanup and exit if main loop is interrupted
    # ----------------------------------------------------------------------
    # ----------------------------------------------------------------------

    def finish(self):
        print("\n")

        if not self.SIMULATION_MODE:

            self.display.finish()

            print("GPIO cleanup()...")

            GPIO.cleanup()

            print("Exitting")

            sys.exit()

