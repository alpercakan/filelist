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
import zipfile

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
  }

  OPERATION_OPTS = {
    CMD_OPT_DELETE: False,
    CMD_OPT_ZIP: True
  }

  OUTPUT_MODE_OPTS = {
    CMD_OPT_NOFILELIST: False,
    CMD_OPT_STATS: False,
    CMD_OPT_DUPLCONT: False,
    CMD_OPT_DUPLNAME: False,
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

      if arg in res_dict:
        return False

      if expects_arg:
        if i + 1 >= len(argv):
          return False

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

  if output_modes[CMD_OPT_DUPLCONT] and output_modes[CMD_OPT_DUPLNAME]:
    # we do not accept both at the same time
    return False

  if output_modes[CMD_OPT_NOFILELIST] and \
     (output_modes[CMD_OPT_DUPLCONT] or output_modes[CMD_OPT_DUPLNAME]):
    # duplcont and duplname wants file listing
    return False

  if (output_modes[CMD_OPT_DUPLCONT] or output_modes[CMD_OPT_DUPLNAME]) and \
     (operations[CMD_OPT_DELETE] or operations[CMD_OPT_ZIP]):
    return False

  if operations[CMD_OPT_DELETE] and operations[CMD_OPT_ZIP]:
    return False

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
        val = (datetime.strptime(val, DATETIME_FORMAT), True)
      else:
        val = (datetime.strptime(val, DATE_FORMAT), False)

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
      num_lit_str = val[:-1]
    else:
      num_lit_str = val
      suffix = ''

    try:
      selectors[opt] = float(num_lit_str) * MULTIPLIERS[suffix]

      if selectors[opt] < 0:
        return False
    except ValueError:
      return False

  return True


def resolve_match_selector(selectors):
  if selectors[CMD_OPT_MATCH] != False:
    try:
      re.compile(selectors[CMD_OPT_MATCH])
    except:
      return False

    selectors[CMD_OPT_MATCH] = re.compile('({})\Z'.format(selectors[CMD_OPT_MATCH]))

  return True


def resolve_paths(paths):
  if len(paths) == 0:
    paths.append('.')

  for i in range(len(paths)):
    paths[i] = os.path.abspath(paths[i])

    if not os.path.isdir(paths[i]):
      return False

  return True


def select(file_path, selectors):
  file_name = os.path.basename(file_path)
  file_stats = os.stat(file_path)
  modif_datetime = datetime.fromtimestamp(file_stats.st_mtime)
  modif_date = modif_datetime.replace(hour = 0, minute = 0, second = 0,
                                      microsecond = 0)

  if selectors[CMD_OPT_MATCH] != False and \
     not selectors[CMD_OPT_MATCH].match(file_name):

    return False

  if selectors[CMD_OPT_BEFORE] != False:
    lower_lim = selectors[CMD_OPT_BEFORE][0]

    if selectors[CMD_OPT_BEFORE][1]:
      modif_val = modif_datetime
    else:
      modif_val = modif_date

    if not lower_lim >= modif_val:
      return False

  if selectors[CMD_OPT_AFTER] != False:
    upper_lim = selectors[CMD_OPT_AFTER][0]

    if selectors[CMD_OPT_AFTER][1]:
      modif_val = modif_datetime
    else:
      modif_val = modif_date

    if not upper_lim <= modif_val:
      return False

  if selectors[CMD_OPT_SMALLER] != False and \
     not selectors[CMD_OPT_SMALLER] >= file_stats.st_size:

    return False

  if selectors[CMD_OPT_BIGGER] != False and \
     not selectors[CMD_OPT_BIGGER] <= file_stats.st_size:

    return False

  return True


def traverse(path, visit_table, selected, stats, selectors, output_modes):
  q = deque([path])
  visit_table[path] = True

  while q:
    cur_dir = q.popleft()
    dir_cont = os.listdir(cur_dir)

    for name in dir_cont:
      cur_item = os.path.join(cur_dir, name)

      if cur_item in visit_table:
        continue

      if os.path.isdir(cur_item):
        if os.path.islink(cur_item):
          cur_item = os.path.realpath(cur_item) # Eliminate symnolic links

        q.append(cur_item)
        visit_table[cur_item] = True # a directory
      elif os.path.isfile(cur_item):
        file_size = os.path.getsize(cur_item)

        stats['visit_count'] += 1
        stats['visit_size'] += file_size

        visit_table[cur_item] = False # not a directory

        if select(cur_item, selectors):
          selected.add(cur_item)

          if not output_modes[CMD_OPT_NOFILELIST]:
            stats['list_count'] += 1
            stats['list_size'] += file_size
            print(cur_item)


def print_dupl(selected, duplname, stats):
  DUPL_BUCKET_SEPARATOR = '------'

  buckets = {}

  for visited_item in selected:
    if duplname:
      bucket_key = os.path.basename(visited_item)
    else:
      file = open(visited_item, 'rb')
      bucket_key = file.read()
      file.close()

    if not bucket_key in buckets:
      buckets[bucket_key] = []

    buckets[bucket_key].append(visited_item)

  for name, bucket in buckets.iteritems():
    bucket.sort()

    for path in bucket:
      stats['list_count'] += 1
      stats['list_size'] += os.path.getsize(path)

      print(path)

    print(DUPL_BUCKET_SEPARATOR)


def print_stats(stats):
  STAT_MSG_VISIT_COUNT = 'Total number of files visited: {}'
  STAT_MSG_VISIT_SIZE = 'Total size of files visited: {} bytes'
  STAT_MSG_LIST_COUNT = 'Total number of files listed: {}'
  STAT_MSG_LIST_SIZE = 'Total size of files listed: {} bytes'

  print('')
  print(STAT_MSG_VISIT_COUNT.format(stats['visit_count']))
  print(STAT_MSG_VISIT_SIZE.format(stats['visit_size']))
  print(STAT_MSG_LIST_COUNT.format(stats['list_count']))
  print(STAT_MSG_LIST_SIZE.format(stats['list_size']))


def delete_files(files):
  for file in files:
    os.remove(file)


def zip_files(files, zip_path):
  if os.path.exists(zip_path):
    return False

  zip_file = zipfile.ZipFile(zip_path, 'w')
  written_set = set()

  for file in files:
    orig_file_name = os.path.basename(file)
    no_collision_name = orig_file_name

    counter = 0

    while no_collision_name in written_set:
      counter += 1
      no_collision_name = '({}) {}'.format(counter, no_collision_name)

    zip_file.write(file, no_collision_name)
    written_set.add(no_collision_name)

  zip_file.close()

  return True


def main():
  ERR_MSG_ILLEGAL_OPT = 'Illegal or conflicting command line option(s) was specified.'
  ERR_MSG_ILLEGAL_ARG = 'An illegal argument was supplied to one of the options.'
  ERR_MSG_PATH_NOT_DIR = 'One of the following supplied paths is non-existent or is not a directory:'
  ERR_MSG_ZIP_FAILED = 'The zipping operation failed.'

  parsed = parse_args(sys.argv)

  if parsed == False:
    print(ERR_MSG_ILLEGAL_OPT)
    return

  (selectors, operations, output_modes, paths) = parsed

  if not (resolve_datetime_selectors(selectors) and
          resolve_size_selectors(selectors) and
          resolve_match_selector(selectors)):
    print(ERR_MSG_ILLEGAL_ARG)
    return

  if not resolve_paths(paths):
    print(ERR_MSG_PATH_NOT_DIR)
    print(', '.join('"' + s + '"' for s in paths))
    return

  visit_table = {}
  stats = {
    'visit_count': 0,
    'list_count': 0,
    'visit_size': 0,
    'list_size': 0
  }
  selected = set()

  if output_modes[CMD_OPT_DUPLCONT] or output_modes[CMD_OPT_DUPLNAME]:
    output_modes[CMD_OPT_NOFILELIST] = True

  for path in paths:
    traverse(path, visit_table, selected, stats, selectors, output_modes)

  if output_modes[CMD_OPT_DUPLNAME] or output_modes[CMD_OPT_DUPLCONT]:
    print_dupl(sorted(selected) if output_modes[CMD_OPT_DUPLNAME] else selected,
               output_modes[CMD_OPT_DUPLNAME],
               stats)

  if output_modes[CMD_OPT_STATS]:
    print_stats(stats)

  if operations[CMD_OPT_ZIP]:
    if not zip_files(selected, operations[CMD_OPT_ZIP]):
      print(ERR_MSG_ZIP_FAILED)

  if operations[CMD_OPT_DELETE]:
    delete_files(selected)


def main_wrapper():
  ERR_MSG_UNC_EXC = 'An uncaught exception occured: {}'

  try:
    main()
  except Exception as e:
    print(ERR_MSG_UNC_EXC.format(e.message))


main()
