"""

serial_receiver.py - debug tool for testing serial_sender.py

Receive characters over an RS-232 connection from serial_sender.py and
manipulate RTS to force the sender to stop and start sending much as how the
Matsuura acts when doing a drip feed.

Can be used on the same computer as serial_sender or a different one. I've
tested with two USB to RS-232 adaptors linked by an RS-232 null modem wire
(cross over wire).

This outputs extensive logging and timing information about what was received,
and will currently turn RTS off (to signal the sender to stop sending), after
each 5 \n characters (RTS_STOP_LINES) received and then turn it back on after
0.5 seconds (RTS_STOP_TIME).

This looks for, and tracks, characters received after the sender was told to
stop to help us under the Matsuura RS-232 Overrun alarms we have seen.  The
Matsuura manual claims the alarm indicates that more than 10 characters were
received.

Results using my MacBook Pro laptop and two FTDI based USB to Serial converters
show the application will consistently receive about 2 to 4 characters after
every stop but the time stamps implies this is not real overrun but rather just
characters buffered in the converter and not sent back over USB until after the
converter was told to set RTS low.  I could not make the serial_sender and
these two converts show any type of error that would explain the Matsuura
alarms.

I did see a few errant cases of receiving many characters as much as 92 ms
after the sender was told to stop, but after more code clean up and more
extensive timing logging added these errant cases seem to have vanished.

"""

import os
import time
import serial_sender
from serial_sender import log
from serial_sender import SerialPort
from zlib import crc32

Serial_port_name = os.environ.get('SERIAL_PORT_NAME', "/dev/ttyUSB0")

RTS_STOP_LINES = 5     # Tell sender to stop after this many \n received
RTS_STOP_TIME = 0.5     # seconds to pause before telling sender to start


def main():
    while True:
        try:
            main_loop()
        except OSError as err:
            log(f"OSError {err.strerror}")
            # Need to force this to close since I have such
            # stupid code structure at work here
            serial_sender.serial_connection = None
            time.sleep(1.0)


def main_loop():
    time_to_go = time.time()
    time_stopped = time.time()
    time_after_read_last = time.time()
    tty = SerialPort(Serial_port_name)
    line_cnt = 0
    late_data = ""          # total data received after RTS turned off
    worse_delay = 0
    worse_cnt = 0
    worse_late_data = ""
    worse_late_delay = 0    # Total time to receive late data in seconds.
    crc32_value = 0

    while True:
        tty.check_open()

        if tty.is_not_open:
            time.sleep(1.0)
            continue

        now = time.time()
        # log(f"now is {now} and time_to_go is {time_to_go}")

        if time_to_go and now > time_to_go:
            # Turn on RTS
            tty.rts = True
            log(f"GO")
            time_to_go = None
            time_after_read_last = now

        # Get all the data that's in the buffer and return instantly, or
        # if no data, wait until something shows up, but don't wait longer
        # than the timeout
        time_before_read = time.time()
        byte_data = tty.read_all()
        time_after_read = time.time()   # Need to timestamp this fast

        if len(byte_data) == 0:
            # Timeout without receiving any data
            continue

        crc32_value = crc32(byte_data, crc32_value)

        time_since_last_data = time_after_read - time_after_read_last
        time_after_read_last = time_after_read

        # byte_data = b"\xf9THis is a test" -- test code to trigger error
        try:
            data = byte_data.decode("utf-8")
        except UnicodeDecodeError as err:
            log(f"UnicodeDecoderError: {err}")
            log(f"    byte data: {byte_data!s}")
            continue

        msg = (f"read {len(data):4} bytes"
               f" in {(time_after_read-time_before_read)*1000_000:5.0f} µs"
               f"  {time_since_last_data * 1000:7.3f} ms since last read"
               f" {data!r}")
        log(msg)

        if not tty.rts:
            # Received data after we lowered RTS and told the sender to stop
            time_to_stop = time_after_read-time_stopped
            worse_delay = max(worse_delay, time_to_stop)
            # Add data to late data buffer in case the late data shows up
            # across multiple reads.
            late_data += data
            if len(late_data) >= worse_cnt:
                worse_cnt = len(late_data)
                # Save the data and time of this worse case
                worse_late_data = late_data
                worse_late_delay = time_to_stop
            log(f"ERROR: ---- received data {time_to_stop * 1000.0:.3f} ms after rts was off! {data!r} ------")
            log(f"       worse time was: {worse_delay*1000:.3f} ms")
            log(f"       most late data was: {worse_late_data!r}"
                f" {len(worse_late_data)} bytes"
                f" at {worse_late_delay*1000:.3f} ms")
            continue

        if '%' in data:
            # End of G-code file.  Reset late data stats
            worse_delay = 0
            worse_cnt = 0
            worse_late_data = ""
            worse_late_delay = 0  # Total time to receive late data in seconds.
            log(f"END OF G-code, crc: {crc32_value:08X}")
            crc32_value = 0

        line_cnt += data.count('\n')
        if line_cnt >= RTS_STOP_LINES:
            # Tell sender to stop after every 5 lines received!
            tty.rts = False
            time_stopped = time.time()
            time_to_go = time_stopped + RTS_STOP_TIME
            log(f"STOP on {RTS_STOP_LINES} nl!")
            line_cnt = 0
            late_data = ""


if __name__ == '__main__':
    main()
    exit(0)
