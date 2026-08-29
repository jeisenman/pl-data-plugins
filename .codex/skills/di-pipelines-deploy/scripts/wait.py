#!/usr/bin/env python3
"""Sleep for the requested number of seconds."""

import argparse
import time


def main() -> None:
    parser = argparse.ArgumentParser(description="Sleep for a number of seconds.")
    parser.add_argument("seconds", type=float)
    args = parser.parse_args()

    if args.seconds < 0:
        parser.error("seconds must be non-negative")

    time.sleep(args.seconds)


if __name__ == "__main__":
    main()
