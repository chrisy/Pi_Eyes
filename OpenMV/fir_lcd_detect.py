# Uses the thermopile shield as crude object location detector. Relative position is
# transmitted over the UART pins (UART 3)
#

import sensor, image, time, fir, lcd
from pyb import UART

# Setup the UART
uart = UART(3, 115200)
uart.init(115200, flow=0, bits=8, parity=None, stop=1)

# Send an initial message
uart.write("status:starting\n")

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

# Initialize the lcd sensor
lcd.init()

# FPS clock
clock = time.clock()

# fir region of display
fir_height = 20
fir_yoffset = (sensor.height // 2) - (fir_height //2)
fir_region = [0, fir_yoffset, sensor.width, fir_height ]

# Our fir threshold range
fir_threshold = [50, 50, 0, 0, 0, 0] # Middle L, A, B values.
# TODO need to tune this

# Tell the rpi we've started
uart.write("status:started\n")

while(True):
    clock.tick()

    # Capture an image
    image = sensor.snapshot()

    # TODO calc lux (for some definition) of image and send to pi
    # intention is to link iris diameter to brightness
    uart.write("lux:0.0\n")

    # Capture FIR data
    #   ta: Ambient temperature
    #   ir: Object temperatures (IR array)
    #   to_min: Minimum object temperature
    #   to_max: Maximum object temperature
    ta, ir, to_min, to_max = fir.read_ir()

    # Draw IR data on the framebuffer
    fir.draw_ir(image, ir, alpha=256, scale=[0, 35]) # idea is that body temp saturates the scale

    # draw bounds of fir image
    image.draw_rectangle(fir_region)

    uart.write("blobs:start\n")

    # Do some detection on the FIR region of the image
    for blobs in img.find_blobs([fir_threshold],
            pixels_threshold=4, area_threshold=4,
            merge=True, margin=1,
            roi=fir_region):
        # display where the blob is
        img.draw_rectangle(blob.rect())

        # tell rpi where the blob is
        uart.write("x:%f y:%f\n" % (blob.cx() / sensor.width, (blob.cy() - fir_yoffset) / fir_height)

    uart.write("blobs:end\n")


    # Draw ambient, min and max temperatures.
    image.draw_string(0, 0, "Ta: %0.2f"%ta, color = (0xFF, 0x00, 0x00))
    image.draw_string(0, 8, "To min: %0.2f"%to_min, color = (0xFF, 0x00, 0x00))
    image.draw_string(0, 16, "To max: %0.2f"%to_max, color = (0xFF, 0x00, 0x00))

    # Display image on LCD
    lcd.display(image)

    # Print FPS.
    print(clock.fps())
