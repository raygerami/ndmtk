#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import (absolute_import, division, print_function)

__author__ = "Paul Greenberg @greenpau"
__version__ = "1.0"
__maintainer__ = "Paul Greenberg"
__email__ = "greenpau@outlook.com"
__status__ = "Alpha"

import os
import sys
import argparse
import traceback;
import yaml;
import logging;
import mimetypes;
import re;
import time;
import pickle;
from datetime import datetime;

class ToolkitError:
    def __init__(self, err):
        if isinstance(err, str):
            self.error_message = "%s" % err;
            return
        self.error_type = "%s" % str(err[0]);
        self.error_message = "%s" % err[1];
        if len(err) < 3:
            return
        if err[2] is None:
            return
        self.error_details = []
        for traceback_line in traceback.format_tb(err[2]):
            self.error_details.append("%s" % (traceback_line))
        return

    def __repr__(self):
        err = self.error_message
        if hasattr(self, "error_type"):
            err = "%s: %s" % (self.error_type, err);
        if hasattr(self, "error_details"):
            err += "\n%s" %  ('\n'.join(self.error_details));
        return err

class ToolkitDatabase(object):
    def __init__(self, data_dir=None):
        self.log = logging.getLogger(self.__class__.__name__);
        self.data_dir = None;
        if not data_dir:
            self.log.error("no data directory specified");
            sys.exit(1);
        if not self._is_dir_exists(data_dir):
            self.log.error("data directory does not exist: %s" % (data_dir));
            sys.exit(1);
        if not self._is_dir_empty(data_dir):
            self.log.error("data directory is empty: %s" % (data_dir));
        self.data_dir = data_dir;
        self.log.info("data directory: %s" % (data_dir));
        self.cache_dir = os.path.join(self.data_dir, '.ndmtk');
        self.cache_file = os.path.join(self.cache_dir, 'cache');
        self.log.info("cache file: %s" % (self.cache_file));
        if self._is_cache_exists():
            self._load_cache();
        else:
            self._construct_inventory();
            self._save_cache();
        return;


    def _load_cache(self):
        epoch = time.time();
        try:
            with open(self.cache_file, 'rb') as f:
                self.data = pickle.load(f);
        except:
            err = ToolkitError(sys.exc_info());
            self.log.error(err);
            return;
        self.log.info("restored cached data at '" + str(datetime.now()) + "', took " + str(time.time() - epoch) + "s");


    def _save_cache(self):
        epoch = time.time();
        if not self._is_dir_exists(self.cache_dir):
            try:
                os.mkdir(self.cache_dir);
            except:
                err = ToolkitError(sys.exc_info());
                self.log.error(err);
                return;
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.data, f, pickle.HIGHEST_PROTOCOL);
        self.log.info("saved data to cache at '" + str(datetime.now()) + "', took " + str(time.time() - epoch) + "s");


    def _is_cache_exists(self):
        if not self._is_file_exists(self.cache_file):
            return False;
        return True;


    @staticmethod
    def _is_file_exists(fn):
        if not os.path.exists(fn):
            ''' path does not exist '''
            return False;
        if not os.path.isfile(fn):
            ''' not a file '''
            return False;
        if not os.access(fn, os.R_OK):
            ''' not readable '''
            return False;
        return True;

    @staticmethod
    def _is_dir_empty(fn):
        for dirpath, dirnames, files in os.walk(os.path.expanduser(fn)):
            if len(files) > 0:
                return False;
            else:
                return True;
        return True;

    @staticmethod
    def _is_dir_exists(fn):
        if not os.path.exists(fn):
            ''' path does not exist '''
            return False;
        if not os.path.isdir(fn):
            ''' not a directory '''
            return False;
        if not os.access(fn, os.R_OK):
            ''' not readable '''
            return False;
        return True;


    @staticmethod
    def _is_file_empty(fn):
        try:
            fn_info = os.stat(fn);
            if fn_info.st_size == 0:
                return True
        except:
            pass;
        return False;

    @staticmethod
    def _has_required_field(fields, d):
        if len(d) == 0:
            return False;
        for f in fields:
            if f not in d:
                return False
        return True

    def _construct_inventory(self):
        '''
        Browse the files in the input directory directory, identify relevant
        meta, and construct file tree.
        '''
        self.data = {};
        try:
            for dirName, subDirList, fileList in os.walk(self.data_dir):
                for fileName in fileList:
                    origFilePath = os.path.join(dirName, fileName);
                    filePath = re.sub(self.data_dir, '', origFilePath);
                    fileName = os.path.basename(filePath);
                    fileDir = re.sub(fileName, '', origFilePath)
                    if not fileName.endswith('meta.yml'):
                        continue;
                    fc = None;
                    with open(origFilePath, "r") as f:
                        try:
                            fc = yaml.load(f);
                        except:
                            err = ToolkitError(sys.exc_info());
                            self.log.error(err);
                            continue
                    fields = ['conf', 'cli'];
                    if not self._has_required_field(fields, fc):
                        continue
                    fields = ['host', 'os'];
                    if not self._has_required_field(fields, fc['conf']):
                        continue;
                    h = fc['conf']['host'];
                    for c in fc['cli']:
                        fields = ['_seq', 'cli', 'status', 'path', 'lines'];
                        if not self._has_required_field(fields, c):
                            continue
                        if c['status'] != 'ok':
                            continue;
                        cc = {
                            'seq': c['_seq'],
                            'input': c['cli'],
                            'file': os.path.basename(c['path']),
                            'lines': int(c['lines']),
                        };
                        try:
                            f = self.data[h];
                        except:
                            self.data[h] = {
                                'data_dir': fileDir,
                                'os': fc['conf']['os'],
                            };
                        try:
                            f = self.data[h]['cli'];
                        except:
                            self.data[h]['cli'] = [];
                        self.data[h]['cli'].append(cc)
                    self.log.info("host: %s" % (fc['conf']['host']));
        except:
            err = ToolkitError(sys.exc_info());
            self.log.error(err);
        return

            
if __name__ == '__main__':
    raise Exception('This is not a script. Direct access is not suppported.');
