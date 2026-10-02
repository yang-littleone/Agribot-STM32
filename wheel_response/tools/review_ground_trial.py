"""Review saved GROUND data and terminal output before the next manual START. No I/O to the vehicle."""
import argparse
from review_air_trial import review
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('directory');a=ap.parse_args()
    raise SystemExit(0 if review(a.directory,condition='GROUND') else 2)
