#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
filelist

Author: Alper Çakan
"""

import sys
import os
from collections import deque
from datetime import datetime
import re

# Command line options
CMD_OPT_BEFORE = '-before'
CMD_OPT_AFTER = '-after'
CMD_OPT_MATCH = '-match'
CMD_OPT_BIGGER = '-bigger'
CMD_OPT_SMALLER = '-smaller'
CMD_OPT_DUPLCONT = '-duplcont'
CMD_OPT_DUPLNAME = '-duplname'
CMD_OPT_DELETE = '-delete'
CMD_OPT_ZIP = '-zip'
CMD_OPT_NOFILELIST = '-nofilelist'
CMD_OPT_STATS = '-stats'

def parse_args(argv):
  SELECTOR_OPTS = {
    CMD_OPT_BEFORE: True, # Option: Does it expect argument?
    CMD_OPT_AFTER: True,
    CMD_OPT_MATCH: True,
    CMD_OPT_BIGGER: True,
    CMD_OPT_SMALLER: True,
    CMD_OPT_DUPLCONT: False,
    CMD_OPT_DUPLNAME: False,
  }

  OPERATION_OPTS = {
    CMD_OPT_DELETE: False,
    CMD_OPT_ZIP: True
  }

  OUTPUT_MODE_OPTS = {
    CMD_OPT_NOFILELIST: False,
    CMD_OPT_STATS: False
  }

  selectors = {}
  operations = {}
  output_modes = {}
  paths = []

  expect_path = False
  i = 1
  while  i < len(argv):
    arg = argv[i]

    if expect_path:
      paths.append(arg)
    else:
      if arg in SELECTOR_OPTS:
        expects_arg = SELECTOR_OPTS[arg]
        res_dict = selectors
      elif arg in OPERATION_OPTS:
        expects_arg = OPERATION_OPTS[arg]
        res_dict = operations
      elif arg in OUTPUT_MODE_OPTS:
        expects_arg = OUTPUT_MODE_OPTS[arg]
        res_dict = output_modes
      else:
        expect_path = True
        continue

      if expects_arg:
        if i + 1 >= len(argv):
          return None

        res_dict[arg] = argv[i + 1]
        i += 1
      else:
        res_dict[arg] = True

    i += 1

  for (opt_dict, res_dict) in zip([SELECTOR_OPTS, OPERATION_OPTS, OUTPUT_MODE_OPTS],
                                  [selectors, operations, output_modes]):
    for opt in opt_dict:
      if not opt in res_dict:
        res_dict[opt] = False

  return (selectors, operations, output_modes, paths)

def resolve_datetime_selectors(selectors):
  DATETIME_FORMAT = '%Y%m%dT%H%M%S'
  DATETIME_LEN = 15
  DATE_FORMAT = '%Y%m%d'
  DATE_LEN = 8

  DATETIME_OPTS = [
    CMD_OPT_BEFORE,
    CMD_OPT_AFTER
  ]

  for opt in DATETIME_OPTS:
    val = selectors[opt]
    if val == False:
      continue

    try:
      if len(val) == DATETIME_LEN:
        val = datetime.strptime(val, DATETIME_FORMAT)
      else:
        val = datetime.strptime(val, DATE_FORMAT)

      selectors[opt] = val
    except ValueError:
      selectors[opt] = False
      return False

  return True

def resolve_size_selectors(selectors):
  SIZE_OPTS = [
    CMD_OPT_SMALLER,
    CMD_OPT_BIGGER
  ]

  MULTIPLIERS = {
    'k': 2**10,
    'm': 2**20,
    'g': 2**30,
    '': 1
  }

  for opt in SIZE_OPTS:
    val = selectors[opt]
    if val == False:
      continue

    if len(val) == 0:
      return False

    suffix = val[-1].lower()

    if suffix in MULTIPLIERS.keys():
      int_lit_str = val[:-1]
    elif ord(suffix) in range(ord('0'), ord('9')):
      int_lit_str = val
      suffix = ''
    else:
      return False

    try:
      selectors[opt] = int(int_lit_str) * MULTIPLIERS[suffix]

      if selectors[opt] < 0:
        return False
    except ValueError:
      return False

  return True

def resolve_match_selector(selectors):
  if selectors[CMD_OPT_MATCH] != False:
    selectors[CMD_OPT_MATCH] = re.compile(selectors[CMD_OPT_MATCH])

  return True

def traverse(options):
  pass

def main():
  ERR_MSG_ILLEGAL_OPT = "Illegal command line option was specified."
  ERR_MSG_ILLEGAL_ARG = "An illegal argument was supplied to one of the options."

  parsed = parse_args(sys.argv)

  if parsed == None:
    print(ERR_MSG_ILLEGAL_OPT)
    return

  if not (resolve_datetime_selectors(parsed[0]) and
          resolve_size_selectors(parsed[0]) and
          resolve_match_selector(parsed[0])):
    print(ERR_MSG_ILLEGAL_ARG)
    return

  print(parsed)

main()
