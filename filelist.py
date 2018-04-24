#!/usr/bin/python
# -*- coding: utf-8 -*-


"""filelist

This module implements a file utility program that can traverse directories
and report path names of files that satisfy some search criteria. The program
can be invoked as follows on the console:

  filelist [options] [directory list]

where both arguments are optional. For further information and details about
the options and the directory list, please consult the project report and
description.

Author: Alper Çakan
"""

import sys
import os
from collections import deque
from datetime import datetime
import re
import zipfile
import hashlib


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
  """Parse command line arguments.

  Parses the given command line arguments to obtain the supplied options,
  safely failing when there are inconsistencies. Also, the options are grouped
  and their arguments are included in the return value. Furthermore, the all of
  the returned dictionaries are key-safe: every legal options is included in
  the corresponding dictionary (with value False in case that option is not
  supplied in the arguments). However, note that this method does not verify
  options which acceps arguments (ex: size option with argument minus 73
  would not bother this method) and the argument options or the paths list
  is not processed in way, they are just passed along.

  Args:
    argv (list): The list of command line arguments as obtained by sys.argv,
    including the first argument (which is the script path).

  Returns:
    tuple: A quadruple on success, None on failure.
    The quadruple consists of selectors, operations, output modes and paths
    respectively.
  """

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
        # when we encounter an argument which is not an option, we assume that
        # this and the all of the rest of the arguments are paths.
        expect_path = True
        continue

      if arg in res_dict:
        return None

      if expects_arg:
        if i + 1 >= len(argv):
          return False

        res_dict[arg] = argv[i + 1]

        # the next was argument for this option, and we already consumed it,
        # so increment twice
        i += 1
      else:
        # option with no argument, so just give True as value to show existence
        res_dict[arg] = True

    i += 1

  # all options are False by default, set the defaults for "key-safety"
  for (opt_dict, res_dict) \
        in zip([SELECTOR_OPTS, OPERATION_OPTS, OUTPUT_MODE_OPTS],
               [selectors, operations, output_modes]):

    for opt in opt_dict:
      if not opt in res_dict:
        res_dict[opt] = False

  if output_modes[CMD_OPT_DUPLCONT] and output_modes[CMD_OPT_DUPLNAME]:
    # we do not accept both at the same time
    return None

  if output_modes[CMD_OPT_NOFILELIST] and \
     (output_modes[CMD_OPT_DUPLCONT] or output_modes[CMD_OPT_DUPLNAME]):
    # duplcont and duplname wants file listing, conflicts nofilelist
    return None

  if (output_modes[CMD_OPT_DUPLCONT] or output_modes[CMD_OPT_DUPLNAME]) and \
     (operations[CMD_OPT_DELETE] or operations[CMD_OPT_ZIP]):
    # duplcont and duplname is listing purposes and hence they should not be
    # given together with operational options
    return None

  if operations[CMD_OPT_DELETE] and operations[CMD_OPT_ZIP]:
    # delete and zip together is dangerous
    return None

  return (selectors, operations, output_modes, paths)


def resolve_datetime_selectors(selectors):
  """Transforms the given datetime selector strings into datetime objects.

  Args:
    selectors (dict): The dictionary of selectors. Note that this will contain
    the result (i.e., the method works in-place). It is allowed that this does
    not contain any datetime selectors. In such a case, this method has no
    effect.

  Returns:
    bool: True on success, False on failure.
  """

  DATETIME_FORMAT = '%Y%m%dT%H%M%S' # YYYYMMDDTHHMMSS
  DATETIME_LEN = 15
  DATE_FORMAT = '%Y%m%d' # YYYYMMDD
  DATE_LEN = 8

  DATETIME_OPTS = [
    CMD_OPT_BEFORE,
    CMD_OPT_AFTER
  ]

  for opt in DATETIME_OPTS:
    val = selectors[opt]
    if val == False:
      # skip non-existent datetime selectors
      continue

    # guard against incorrect datetime/date formats
    try:
      if len(val) == DATETIME_LEN:
        # this should be datetime
        val = (datetime.strptime(val, DATETIME_FORMAT), True)
      else:
        # this should be date only
        val = (datetime.strptime(val, DATE_FORMAT), False)

      selectors[opt] = val
    except ValueError:
      # format was wrong, remove the selector and return with failure
      selectors[opt] = False
      return False

  return True


def resolve_size_selectors(selectors):
  """Transforms the given size selector strings to float type repr. byte count.

  Args:
    selectors (dict): The dictionary of selectors. Note that this will contain
    the result (i.e., the method works in-place). It is allowed that this does
    not contain any size selectors. In such a case, this method has no effect.

  Returns:
    bool: True on success, False on failure.
  """

  SIZE_OPTS = [
    CMD_OPT_SMALLER,
    CMD_OPT_BIGGER
  ]

  MULTIPLIERS = {
    'k': 2**10, # kilo
    'm': 2**20, # mega
    'g': 2**30, # giga
    '': 1
  }

  for opt in SIZE_OPTS:
    val = selectors[opt]
    if val == False:
      # skip non-existent size selectors
      continue

    # check that val is not empty so that the suffix extraction does not go
    # out of bounds of the string
    if len(val) == 0:
      return False

    suffix = val[-1].lower()

    if suffix in MULTIPLIERS.keys():
      num_lit_str = val[:-1]
    else:
      num_lit_str = val
      suffix = ''

    # guard against non-numbers
    try:
      selectors[opt] = float(num_lit_str) * MULTIPLIERS[suffix]

      if selectors[opt] < 0:
        # negative not allowed
        return False
    except ValueError:
      # the size option argument was not a number
      return False

  return True


def resolve_match_selector(selectors):
  """Transforms the given match selector strings to a compiled regex object.

  Args:
    selectors (dict): The dictionary of selectors. Note that this will contain
    the result (i.e., the method works in-place). It is allowed that this does
    not contain any match selectors. In such a case, this method has no effect.

  Returns:
    bool: True on success, False on failure.
  """

  if selectors[CMD_OPT_MATCH] != False:
    # guard against illegal regexes
    try:
      re.compile(selectors[CMD_OPT_MATCH])
    except:
      return False

    # we wrap the given pattern and add \Z to it so that the final pattern
    # becomes a only-full-match pattern (ex: pattern "a" does not match "abc")
    # because unlike Pyton 3, we do not have the method "fullmatch" in Python 2
    selectors[CMD_OPT_MATCH] = \
      re.compile('({})\Z'.format(selectors[CMD_OPT_MATCH]))

  return True


def resolve_paths(paths):
  """Transforms and verifies the given directory lists which is to be used as
  the traversal roots.

  Args:
    paths (list): The list of paths. Note that this will contain the result
    (i.e., the method works in-place). It is allowed that this be empty.

  Returns:
    bool: True on success, False on failure.
  """

  if len(paths) == 0:
    # when no path is supplied, use current dir
    paths.append('.')

  for i in range(len(paths)):
    # use abstract paths for more robust traversal and file opreations
    paths[i] = os.path.abspath(paths[i])

    if not os.path.isdir(paths[i]):
      # only directories are accepted
      return False

  return True


def select(file_path, selectors):
  """Tests if a file is "selected" by the given selectors.

  Args:
    file_path (str): The absolute path of the file.

    selectors (dict): The dictionary of the usual, supported selectors.

  Returns:
    bool: True if the file is selected, False otherwise.
  """

  file_name = os.path.basename(file_path)
  file_stats = os.stat(file_path)
  modif_datetime = datetime.fromtimestamp(file_stats.st_mtime)

  # date only version the modification datetime
  modif_date = modif_datetime.replace(hour = 0, minute = 0, second = 0,
                                      microsecond = 0)

  if selectors[CMD_OPT_MATCH] != False and \
     not selectors[CMD_OPT_MATCH].match(file_name):
    # name did not match
    return False

  if selectors[CMD_OPT_BEFORE] != False:
    lower_lim = selectors[CMD_OPT_BEFORE][0]

    if selectors[CMD_OPT_BEFORE][1]:
      modif_val = modif_datetime
    else:
      # option argument does not contain time-of-day
      modif_val = modif_date

    if not lower_lim >= modif_val:
      return False

  if selectors[CMD_OPT_AFTER] != False:
    upper_lim = selectors[CMD_OPT_AFTER][0]

    if selectors[CMD_OPT_AFTER][1]:
      modif_val = modif_datetime
    else:
      # option argument does not contain time-of-day
      modif_val = modif_date

    if not upper_lim <= modif_val:
      return False

  if selectors[CMD_OPT_SMALLER] != False and \
     not selectors[CMD_OPT_SMALLER] >= file_stats.st_size:
    # size too big
    return False

  if selectors[CMD_OPT_BIGGER] != False and \
     not selectors[CMD_OPT_BIGGER] <= file_stats.st_size:
    # size too small
    return False

  # yay, passed!
  return True


def traverse(path, visit_table, selected, stats, selectors, output_modes):
  """Traverses the file system in breadth-first manner.

  Args:
    path (str): The absolute path of the traversal root.

    visit_table (dict): A dictionary which marks which files and directories
    has already been seen. This will modified during the traversal.

    selected (set): The set of "selected" files according to the given
    selectors.

    stats (dict): The traversal statistics. This will be modified. Also,
    this is not reset here. So, if you have any prior statistics in it,
    the new statistics will be build upon on that.

    selectors (dict): The selectors which are to be used for selecting which
    files should be selected (and printed if the output mode allows).

    output_modes (dict): The output modes which dictates whether the selected
    files should be printed or not. Note that only option this method cares
    about is CMD_OPT_NOFILELIST.

  Returns:
    None.
  """

  q = deque([path])

  # although the name may suggest otherwise, the value here is not important
  # all existing keys are visited, and the value True/False just implies
  # whether it is a file or a directory, respectively
  visit_table[path] = True # root is visited and is a dir

  # BFS
  while q:
    cur_dir = q.popleft() # deque
    dir_cont = os.listdir(cur_dir)

    for name in dir_cont:
      cur_item = os.path.join(cur_dir, name)

      if cur_item in visit_table:
        continue

      if os.path.isdir(cur_item):
        if os.path.islink(cur_item):
          cur_item = os.path.realpath(cur_item) # eliminate symbolic links

        q.append(cur_item) # enqueue

        # mark visited and file/dir type
        visit_table[cur_item] = True # a directory
      elif os.path.isfile(cur_item):
        file_size = os.path.getsize(cur_item)

        # being visited does not
        stats['visit_count'] += 1
        stats['visit_size'] += file_size

        # mark visited and file/dir type
        visit_table[cur_item] = False # not a directory

        if select(cur_item, selectors):
          selected.add(cur_item)

          if not output_modes[CMD_OPT_NOFILELIST]:
            stats['list_count'] += 1
            stats['list_size'] += file_size
            print(cur_item)


def file_shasum(file_path):
  """Calculates the SHA1 hash of the content of a file.

  Args:
    file_path (str): Path of the file.

  Returns:
    The SHA1 hash.
  """
  CHUNKSIZE = 32768
  sha1 = hashlib.sha1()
  file = open(file_path, 'rb')

  while True:
    data = file.read(CHUNKSIZE)

    if not data:
      break

    sha1.update(data)

  file.close()
  return sha1.hexdigest()


def print_dupl(selected, duplname, stats):
  """Prints the duplicate files.

  Args:
    selected (set): The set of selected files to be written.

    duplname (bool): If True, the duplication grouping will be done by the
    file names. If not, it will be done by file contents.

    stats (dict): The usual statistics object. Will be updated.

  Returns:
    None.
  """

  DUPL_BUCKET_SEPARATOR = '------'

  # for grouping the duplicates, we put them in buckets
  # since the dictionary types is very efficent, we can use it for this aim
  # by making the "duplication criterion" the key and use lists as the values
  buckets = {}

  for visited_item in selected:
    # choose the key according to the "duplication criterion"
    if duplname:
      bucket_key = os.path.basename(visited_item)
    else:
      bucket_key = file_shasum(visited_item)

    if not bucket_key in buckets:
      # create the bucket
      buckets[bucket_key] = []

    buckets[bucket_key].append(visited_item)

  for name, bucket in buckets.iteritems():
    # print sorted
    bucket.sort()

    for path in bucket:
      stats['list_count'] += 1
      stats['list_size'] += os.path.getsize(path)

      print(path)

    print(DUPL_BUCKET_SEPARATOR)


def print_stats(stats):
  """Prints the usual statistics object in a beatiful way.

  Args:
    stats (dict): The usual statistics object.

  Returns:
    None.
  """
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
  """Deletes the files whose paths are given.

  Args:
    file (list): The paths of the files to be deleted

  Returns:
    None.
  """
  for file in files:
    os.remove(file)


def zip_files(files, zip_path):
  """Zips the files whose paths are given.

  The files are zipped so that all of them will be in the archive root
  regardless of their current full path. Also, the name collisions will
  be resolved by adding a number inside paranthesis to the beginning of
  the names of the files.

  Args:
    files (list): The paths of the files to be zipped
    zip_path (str): The desired path of the output archive file

  Return:
    True on success, False otherwise.
  """

  if os.path.exists(zip_path):
    # we do not want to override
    return False

  zip_file = zipfile.ZipFile(zip_path, 'w')

  # this is for name collision check, since ZipFile class does not
  # warn about the collisions and it rather overrides the current content
  written_set = set()

  for file in files:
    orig_file_name = os.path.basename(file)
    no_collision_name = orig_file_name

    counter = 0

    while no_collision_name in written_set:
      counter += 1

      # example: (13) myfile
      no_collision_name = '({}) {}'.format(counter, no_collision_name)

    zip_file.write(file, no_collision_name)
    written_set.add(no_collision_name)

  zip_file.close()

  return True


def main():
  """The actual entry point of the program.

  Returns:
    None.
  """

  ERR_MSG_ILLEGAL_OPT = 'Illegal or conflicting command line option(s) was specified.'
  ERR_MSG_ILLEGAL_ARG = 'An illegal argument was supplied to one of the options.'
  ERR_MSG_PATH_NOT_DIR = 'One of the following supplied paths is non-existent or is not a directory:'
  ERR_MSG_ZIP_FAILED = 'The zipping operation failed.'

  parsed = parse_args(sys.argv)

  if parsed == False:
    print(ERR_MSG_ILLEGAL_OPT)
    return

  (selectors, operations, output_modes, paths) = parsed

  # process the arguments
  if not (resolve_datetime_selectors(selectors) and
          resolve_size_selectors(selectors) and
          resolve_match_selector(selectors)):
    print(ERR_MSG_ILLEGAL_ARG)
    return

  # verify the traversal roots
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
    # actually duplcont and/or duplname means there WILL be output, but we have
    # a special format for it which the method traverse cannot handle; hence we
    # are tricking traverse to silence it
    output_modes[CMD_OPT_NOFILELIST] = True

  for path in paths:
    traverse(path, visit_table, selected, stats, selectors, output_modes)

  if output_modes[CMD_OPT_DUPLNAME] or output_modes[CMD_OPT_DUPLCONT]:
    # print the duplicates in sorted order
    print_dupl(sorted(selected) if output_modes[CMD_OPT_DUPLNAME] else selected,
               output_modes[CMD_OPT_DUPLNAME],
               stats)

  if output_modes[CMD_OPT_STATS]:
    print_stats(stats)

  # first zip then delete, obviously
  if operations[CMD_OPT_ZIP]:
    if not zip_files(selected, operations[CMD_OPT_ZIP]):
      print(ERR_MSG_ZIP_FAILED)

  if operations[CMD_OPT_DELETE]:
    delete_files(selected)


def safe_main_wrapper():
  """A simple wrapper around the actual entry point.

  This is a simple wrapper around the method main. This method is exception
  safe and just prints out the exception in case of an exception being thrown
  from main. This is used in order to "protect" user from the complicated
  error/exception message of the Pyton interpreter.

  Returns:
    None.
  """

  ERR_MSG_UNC_EXC = 'An uncaught exception occured: {}'

  try:
    main()
  except Exception as e:
    print(ERR_MSG_UNC_EXC.format(e.message))


safe_main_wrapper()
