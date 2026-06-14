#!/usr/bin/env python3
"""
token_watch.py - measure the Wyze token lifetime and flag the moment it expires.

Pings the Wyze cloud (get_object_list) on a timer using the token from the
capture. Logs every check to capture/token_watch.log. When the token flips from
valid -> expired it prints a banner and writes capture/TOKEN_EXPIRED.flag -- your
cue to re-capture (open the Roku app while the proxy runs) so we can finally see
the refresh call and decide if it can be automated. Pure PC-side; no phone needed
to just measure the lifetime.

    py token_watch.py            # check every 600 s (10 min)
    py token_watch.py 300        # custom interval (seconds)
    py token_watch.py once       # single check, print result, exit
"""
import datetime
import os
import sys
import time

import roku_bulb as rb

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, "capture", "token_watch.log")
FLAG = os.path.join(HERE, "capture", "TOKEN_EXPIRED.flag")


def check_once():
    recs = rb.load_records()
    status, body = rb.wyze_get_object_list(recs)
    valid = body is not None and '"code":"1"' in body
    return valid, status, body


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else "600"
    if arg == "once":
        valid, status, _ = check_once()
        print("valid=%s  http=%s" % (valid, status))
        return

    interval = int(arg)
    start = time.time()
    print("Wyze token watchdog: checking every %d s. Ctrl-C to stop." % interval)
    if os.path.exists(FLAG):
        os.remove(FLAG)
    last_valid = None
    while True:
        valid, status, _ = check_once()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        hrs = (time.time() - start) / 3600.0
        line = "%s  valid=%-5s  http=%s  (%.2f h since watch start)" % (now, valid, status, hrs)
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
        print(line)
        if last_valid is True and valid is False and status is not None:
            msg = ("TOKEN EXPIRED after ~%.2f h valid. Re-capture now: start the proxy, "
                   "open the Roku app, and it will refresh -- that's the call we need." % hrs)
            print("=" * 72 + "\n" + msg + "\n" + "=" * 72)
            try:
                with open(FLAG, "w", encoding="utf-8") as f:
                    f.write(now + "  " + msg + "\n")
            except Exception:
                pass
        last_valid = valid
        time.sleep(interval)


if __name__ == "__main__":
    main()
