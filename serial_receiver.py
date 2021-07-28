"""

serial_receiver.py - debug tool for testing serial_sender.py

Receiver characters over an RS-232 connection from serial_sender.py

"""
import os
import time
import serial_sender
from serial_sender import log

# dotenv.load_dotenv()

serial_port_name = os.environ.get('SERIAL_PORT_NAME', "/dev/ttyUSB0")
serial_tcp_port = int(os.environ.get('SERIAL_TCP_PORT', 1111))


def main():

    time_to_go = time.time()
    time_stopped = time.time()
    time_after_read_last = time.time()
    tty = None
    line_cnt = 0
    late_data = ""          # total data received after RTS turned off
    worse_delay = 0
    worse_cnt = 0
    worse_late_data = ""
    worse_late_delay = 0    # Total time to receive late data in seconds.

    while True:
        if tty is None:
            tty = serial_sender.serial_check_and_open()
            if tty is None:
                time.sleep(0.5)     # Wait for port to open
                continue
            tty.timeout = 1.0

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
        data = tty.read_all()
        time_after_read = time.time()   # Need to timestamp this fast

        if len(data) == 0:
            # Timeout without receiving any data
            continue

        time_since_last_data = time_after_read - time_after_read_last
        time_after_read_last = time_after_read

        data = data.decode("utf-8")

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
            log(f"       most late data was: {worse_late_data!r} at {worse_late_delay*1000:.3f} ms")
            continue

        if '%' in data:
            # End of g code file.  Reset late data stats
            worse_delay = 0
            worse_cnt = 0
            worse_late_data = ""
            worse_late_delay = 0  # Total time to receive late data in seconds.

        line_cnt += data.count('\n')
        if line_cnt >= 5:
            # Tell sender to stop after every 5 lines received!
            tty.rts = False
            time_stopped = time.time()
            time_to_go = time_stopped + .5
            log("STOP on 5 nl!")
            line_cnt = 0
            late_data = ""


if __name__ == '__main__':
    main()
    exit(0)
