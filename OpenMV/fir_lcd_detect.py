# Uses the thermopile shield as crude object location detector. Relative position is
# transmitted over the UART pins (UART 3)
#

debug = True

import sensor, image, time, fir, pyb

print(repr(pyb.freq()))

# Setup the UART
uart_bus = 1
uart_baud = 115200
uart = pyb.UART(uart_bus, baudrate=uart_baud, flow=0, bits=8, parity=None, stop=1, timeout_char=10)

def send(text):
    global uart
    print(text)
    uart.write("%s\r\n" % text)

# Send an initial message
send("")
send("status:starting")

# Reset sensor
sensor.reset()

# Set sensor settings
sensor.set_contrast(1)
sensor.set_brightness(0)
sensor.set_saturation(2)
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.QQVGA2)

# The following registers fine-tune the image
# sensor window to align it with the FIR sensor.
if (sensor.get_id() == sensor.OV2640):
    sensor.__write_reg(0xFF, 0x01) # switch to reg bank
    sensor.__write_reg(0x17, 0x19) # set HSTART
    sensor.__write_reg(0x18, 0x43) # set HSTOP

# Initialize the thermal sensor
fir.init()

# FPS clock
clock = time.clock()

# fir region of display
fir_height = 34
fir_yoffset = (sensor.height() // 2) - (fir_height // 2)
fir_region = [0, fir_yoffset, sensor.width(), fir_height]
fir_scale = [0, 35]

# Our fir threshold range
fir_threshold = [56, 73, 8, 69, -3, 76] # Middle L, A, B values.
fir_threshold = [32, 95, -18, 40, -22, 92]
# TODO need to tune this

fps_target = 10
fps_delay_max = 500
fps_delay = 100
fps_delay_inc = 1

dbg_row = 0

learn = False
learn_count = 200
learn_width = 50

if learn:
    # Capture the color thresholds for whatever was in the center of the image.
    r = [(sensor.width()//2)-(learn_width//2), fir_yoffset, learn_width, fir_height]

    print("Auto algorithms done. Hold the object you want to track in front of the camera in the box.")
    print("MAKE SURE THE COLOR OF THE OBJECT YOU WANT TO TRACK IS FULLY ENCLOSED BY THE BOX!")
    for i in range(60):
        img = sensor.snapshot()
        img.draw_rectangle(r)

    print("Learning thresholds...")
    threshold = [50, 50, 0, 0, 0, 0] # Middle L, A, B values.
    for i in range(learn_count):
        img = sensor.snapshot()

        ta, ir, to_min, to_max = fir.read_ir()
        fir.draw_ir(img, ir, alpha=256, scale=fir_scale)

        hist = img.get_histogram(roi=r)
        lo = hist.get_percentile(0.01) # Get the CDF of the histogram at the 1% range (ADJUST AS NECESSARY)!
        hi = hist.get_percentile(0.99) # Get the CDF of the histogram at the 99% range (ADJUST AS NECESSARY)!
        # Average in percentile values.
        threshold[0] = (threshold[0] + lo.l_value()) // 2
        threshold[1] = (threshold[1] + hi.l_value()) // 2
        threshold[2] = (threshold[2] + lo.a_value()) // 2
        threshold[3] = (threshold[3] + hi.a_value()) // 2
        threshold[4] = (threshold[4] + lo.b_value()) // 2
        threshold[5] = (threshold[5] + hi.b_value()) // 2
        for blob in img.find_blobs([threshold], pixels_threshold=100, area_threshold=100, merge=True, margin=16):
            img.draw_rectangle(blob.rect())
            img.draw_cross(blob.cx(), blob.cy())
            img.draw_rectangle(r)

    send("Learnt: %s" % repr(threshold))
    while True:
        time.sleep(1)

def dbg(img, txt):
    global dbg_row

    img.draw_string(1, dbg_row+1, txt, color = (0x00, 0x00, 0x00))
    img.draw_string(0, dbg_row, txt, color = (0xff, 0xff, 0xff))

    dbg_row += 8

# Tell the rpi we've started
send("status:started")

while(True):
    clock.tick()
    time.sleep(fps_delay)

    # reset text line
    dbg_row = 0

    # Capture an image
    img = sensor.snapshot()

    # Calc luminosity (for some definition) of image and send to the Pi.
    # Intention is to link iris diameter to brightness.
    stats = img.get_statistics()
    lux = stats.uq() + stats.median()
    if lux > 100:
        lux = 100
    send("lux:%d" % lux)

    # Capture FIR data
    #   ta: Ambient temperature
    #   ir: Object temperatures (IR array)
    #   to_min: Minimum object temperature
    #   to_max: Maximum object temperature
    ta, ir, to_min, to_max = fir.read_ir()

    # Draw IR data on the framebuffer
    # "scale" is set such that body temperatures saturate the scale
    fir.draw_ir(img, ir, alpha=256, scale=fir_scale)

    # draw bounds of fir image
    img.draw_rectangle(fir_region)

    # Do some detection on the FIR region of the image
    blob_count = 0
    for blob in img.find_blobs([fir_threshold],
            pixels_threshold=4, area_threshold=4,
            merge=True, margin=16,
            roi=fir_region):
        # display where the blob is
        img.draw_rectangle(blob.rect())

        # tell rpi where the blob is
        send("blob:x=%1.2f:y=%1.2f:s=%1.1f" % (
            blob.cx() / sensor.width(),
            (blob.cy() - fir_yoffset) / fir_height,
            blob.area()/50
        ))
        blob_count += 1

    # Print FPS.
    fps = clock.fps()
    send("fps:%1.1f" % fps)

    # Adjust FPS towards target
    if fps < fps_target:
        fps_delay -= fps_delay_inc
        if fps_delay < 0:
            fps_delay = 0
    elif fps > fps_target:
        fps_delay += fps_delay_inc
        if fps_delay > fps_delay_max:
            fps_delay = fps_delay_max

    if debug:
        dbg(img, "fps: %1.1f" % fps)
        dbg(img, "lux: %1.1f" % lux)
        dbg(img, "blobs: %d" % blob_count)
