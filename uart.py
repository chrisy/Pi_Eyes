#!/usr/bin/python -u

import sys
import time
import serial
import threading
from scipy.signal import lfilter


UART_PORT    = "/dev/ttyAMA0"
UART_BAUD    = 115200

POINTS_COUNT = 4


class uartThread(threading.Thread):
    sio = None
    targets = None
    lux = None
    points_x = None
    points_y = None

    def __init__(self, uart):
        super(uartThread, self).__init__()
        #self.sio = io.TextIOWrapper(io.BufferedReader(uart))
        self.sio = uart
        self.targets = ()
        self.lux = 0.0
        self.points_x = [0] * POINTS_COUNT
        self.points_y = [0] * POINTS_COUNT

        n = 15
        self.b_x = [1.0 / n] * n
        self.a_x = 1

        n = 5
        self.b_y = [1.0 / n] * n
        self.a_y = 1

        self.running = True

    def run(self):
        latest = None

        # Purge any buffered bytes
        self.sio.reset_input_buffer()

        while self.running:
            # read the uart
            try:
                line = self.sio.readline()
            except:
                time.sleep(0.1)
                continue

            if ':' not in line:
                continue

            parts = line.split(':')
            if parts[0] == 'lux':
                # reset the latest
                try:
                    lux = float(parts[1])
                except:
                    continue
                latest = {
                    'lux': lux,
                    'blobs': [],
                }
            elif parts[0] == 'blob' and latest:
                blob = {}
                for item in parts[1:]:
                    if '=' not in item:
                        continue
                    try:
                        k, v = item.split('=')
                        blob[k] = float(v)
                    except:
                        blob = None
                        break
                if blob and len(blob):
                    latest['blobs'].append(blob)
            elif parts[0] == 'fps' and latest:
                try:
                    latest['fps'] = float(parts[1])
                except:
                    latest = None
                    continue
                # it's complete, process the contents
                self.process(latest)
                latest = None

    def process(self, latest):
        # sort the blobs by size, use the largest
        t = ()
        if 'blobs' in latest and len(latest['blobs']) > 0:
            blob = sorted(latest['blobs'], key=lambda x:x.get('s', 0), reverse=True)[0]
            # store with coords converted into x,y tuples scaled to our usable range
            t = ( (blob['x'] * 60.0 - 30.0), -(blob['y'] * 60.0 - 30.0) )

        if t and False:
            sys.stderr.write("new x:%1.1f y:%1.1f lux:%1.1f fps:%1.1f      \r" % (
                   t[0],
                   t[1],
                   latest['lux'] if 'lux' in latest else 0.0,
                   latest['fps'] if 'fps' in latest else 0.0))

        if t:
            # accumulate points in a rolling buffer
            self.points_x.pop(0)
            self.points_y.pop(0)
            self.points_x.append(t[0])
            self.points_y.append(t[1])

            # run a filter on the accumulated points
            x = lfilter(self.b_x, self.a_x, self.points_x)
            y = lfilter(self.b_y, self.a_y, self.points_y)

            t = (x[-1], y[-1])
        else:
            t = (None, None)

        sys.stdout.write("%s,%s,%s,%s\n" % (t[0], t[1], latest['lux'], latest['fps']))


uart = serial.Serial(UART_PORT)
uart.baudrate = UART_BAUD

uart_thread = uartThread(uart)
uart_thread.daemon = True
uart_thread.start()

del uart

while True:
    time.sleep(1)

