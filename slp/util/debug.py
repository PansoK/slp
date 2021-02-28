# flake8: noqa

"""
Patch Python 3.7+ breakpoint to use ipdb instead of pdb, if ipdb is installed
"""
import sys
from loguru import logger

try:
    import ipdb as pdb
except:
    import pdb


def set_trace():
    pdb.set_trace()


sys.breakpointhook = set_trace  # type: ignore
