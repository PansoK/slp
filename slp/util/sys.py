import functools
import os
import pickle
import shutil
import subprocess
import sys
import time
import urllib

import slp.util.log as log

LOGGER = log.getLogger('default')

try:
    import ujson as json
except ImportError:
    import json


def safe_mkdirs(path):
    """! Makes recursively all the directory in input path """
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except Exception as e:
            LOGGER.warning(e)
            raise IOError(
                ("Failed to create recursive directories: {}"
                 .format(path)))


def timethis(func):
    """
    Decorator that measure the time it takes for a function to complete
    Usage:
      @slp.util.sys.timethis
      def time_consuming_function(...):
    """
    @functools.wraps(func)
    def timed(*args, **kwargs):
        ts = time.time()
        result = func(*args, **kwargs)
        te = time.time()
        elapsed = '{0}'.format(te - ts)
        LOGGER.info('BENCHMARK: {f}(*{a}, **{kw}) took: {t} sec'.format(
            f=func.__name__, a=args, kw=kwargs, t=elapsed))
        return result, elapsed
    return timed


def suppress_print(func):
    @functools.wraps(func)
    def func_wrapper(*args, **kwargs):
        with open('/dev/null', 'w') as sys.stdout:
            ret = func(*args, **kwargs)
        sys.stdout = sys.__stdout__
        return ret
    return func_wrapper


def run_cmd(command):
    """
    Run given command locally
    Return a tuple with the return code, stdout, and stderr of the command
    """
    command = '{} -c "{}"'.format(os.getenv('SHELL'), command)
    pipe = subprocess.Popen(command,
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)

    stdout = ''.join([line.decode("utf-8") for line in iter(pipe.stdout.readline, b'')])
    pipe.stdout.close()
    returncode = pipe.wait()
    return returncode, stdout


def run_cmd_silent(command):
    return suppress_print(run_cmd(command))


def download_url(url, dest_path):
    """
    Download a file to a destination path given a URL
    """
    name = url.rsplit('/')[-1]
    dest = dest_path + "/" + name
    try:
        response = urllib.request.urlopen(url)
    except (urllib.error.HTTPError, urllib.error.URLError):
        return False

    with open(dest, 'wb') as fd:
        shutil.copyfileobj(response, fd)
    return True


def write_wav(byte_str, wav_file):
    '''
    Write a hex string into a wav file

    Args:
        byte_str: The hex string containing the audio data
        wav_file: The output wav file

    Returns:
    '''
    with open(wav_file, 'w') as fd:
        fd.write(byte_str)


def read_wav(wav_sample):
    '''
    Reads a wav clip into a string
    and returns the hex string.
    Args:

    Returns:
        A hex string with the audio information.
    '''
    with open(wav_sample, 'r') as wav_fd:
        clip = wav_fd.read()
    return clip


def pickle_load(fname):
    with open(fname, 'rb') as fd:
        data = pickle.load(fd)
    return data


def pickle_dump(data, fname):
    with open(fname, 'wb') as fd:
        pickle.dump(data, fd)


def json_load(fname):
    with open(fname, 'r') as fd:
        data = json.load(fd)
    return data


def json_dump(data, fname):
    with open(fname, 'w') as fd:
        json.dump(data, fd)

