#!/usr/bin/env python3
"""REMOVED 2026-07-23 — this was a STALE FOSSIL and running it would have been destructive.

The live fabric prep is the one at the REPO ROOT:

    cd ~/Desktop/GCC_House_Model && python3 prep_fabrics.py

This builder/ copy was a 142-line snapshot from an earlier session: 10 fabrics, TILE_CM 8.0, and
crucially NO stripe_angle (deskew), NO stripe_period (period-snap), NO widen_lines (display
line-width floor) and NO STRIPE_CODES. HANDOVER.md's layout table pointed at THIS file, so the
standing next-action "batch all 117 fabrics" would have regenerated every tile without any of the
stripe corrections — re-introducing the 1.3 deg scan lean and the ghost-stripe wrap artefacts.

The original text is kept alongside as prep_fabrics.py.stale-2026-07-23.bak in case anything
referenced it.
"""
import os
import sys

sys.stderr.write(__doc__ + "\n")
sys.exit(2)
