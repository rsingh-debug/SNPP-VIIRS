#!/usr/bin/env python

# script supports either python2 or python3. You might need to change the above
# line to "python3" depending on your installation.
#
# Attempts to do HTTP Gets with urllib2(py2) urllib.requets(py3) or subprocess
# if tlsv1.1+ isn't supported by the python ssl module
#
# Will download csv or json depending on which python module is available
#

from __future__ import (division, print_function, absolute_import, unicode_literals)

import argparse
import os
import os.path
import shutil
import sys
import time

try:
    from StringIO import StringIO   # python2
except ImportError:
    from io import StringIO         # python3


################################################################################

# you will need to replace the following line with the location of a
# python web client library that can make HTTPS requests to an IP address.
USERAGENT = 'tis/download.py_1.0--' + sys.version.replace('\n','').replace('\r','')

# this is the choice of last resort, when other attempts have failed
def getcURL(url, headers=None, out=None):
    # OS X Python 2 and 3 don't support tlsv1.1+ therefore... cURL
    import subprocess
    try:
        print('trying cURL', file=sys.stderr)
        args = ['curl', '--fail', '-sS', '-L', '-b session', '--get', url]
        for (k,v) in headers.items():
            args.extend(['-H', ': '.join([k, v])])
        if out is None:
            # python3's subprocess.check_output returns stdout as a byte string
            result = subprocess.check_output(args)
            return result.decode('utf-8') if isinstance(result, bytes) else result
        else:
            subprocess.call(args, stdout=out)
    # except subprocess.CalledProcessError as e:
    #     print('curl GET error message: %' + (e.message if hasattr(e, 'message') else e.output), file=sys.stderr)
        
    except subprocess.CalledProcessError as e:
        print(f"curl GET error message: {(e.message if hasattr(e, 'message') else e.output.decode('utf-8'))}", file=sys.stderr)

    return None
    
# read the specified URL and output to a file
def geturl(url, token=None, out=None):
    headers = { 'user-agent' : USERAGENT }
    if not token is None:
        headers['Authorization'] = 'Bearer ' + token
    try:
        import ssl
        CTX = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        if sys.version_info.major == 2:
            import urllib2
            try:
                fh = urllib2.urlopen(urllib2.Request(url, headers=headers), context=CTX)
                if out is None:
                    return fh.read()
                else:
                    shutil.copyfileobj(fh, out)
            except urllib2.HTTPError as e:
                print('TLSv1_2 sys 2 : HTTP GET error code: %d' % e.code, file=sys.stderr)
                return getcURL(url, headers, out)
            except urllib2.URLError as e:
                print('TLSv1_2 sys 2 : Failed to make request: %s, RETRYING' % e.reason, file=sys.stderr)
                return getcURL(url, headers, out)
            return None

        else:
            from urllib.request import urlopen, Request, URLError, HTTPError
            try:
                fh = urlopen(Request(url, headers=headers), context=CTX)
                if out is None:
                    return fh.read().decode('utf-8')
                else:
                    shutil.copyfileobj(fh, out)
            except HTTPError as e:
                print('TLSv1_2 : HTTP GET error code: %d' % e.code, file=sys.stderr)
                return getcURL(url, headers, out)
            except URLError as e:
                print('TLSv1_2 : Failed to make request: %s' % e.reason, file=sys.stderr)
                return getcURL(url, headers, out)
            return None

    except AttributeError:
      return getcURL(url, headers, out)


################################################################################


DESC = "This script will recursively download all files if they don't exist from a LAADS URL and will store them to the specified path"


def sync(src, dest, tok):
    '''synchronize src url with dest directory'''
    # try:
    #     import csv
    #     files = {}
    #     files['content'] = [ f for f in csv.DictReader(StringIO(geturl('%s.csv' % src, tok)), skipinitialspace=True) ]
    # except ImportError:
    #     import json
    #     files = json.loads(geturl(src + '.json', tok))
    
    try:
        import csv
        csv_url = f"{src}.csv"
        csv_data = geturl(csv_url, tok)
        if csv_data:
            files = {'content': list(csv.DictReader(StringIO(csv_data), skipinitialspace=True))}
        else:
            raise ValueError("CSV not available")
    except:
        import json
        json_url = f"{src}.json"
        json_data = geturl(json_url, tok)
        if json_data:
            files = json.loads(json_data)
        else:
            print(f"Neither CSV nor JSON index available at: {src}", file=sys.stderr)
            sys.exit(1)   
    
    
    
    # use os.path since python 2/3 both support it while pathlib is 3.4+
    for f in files['content']:
        # currently we use filesize of 0 to indicate directory
        filesize = int(f['size'])
        path = os.path.join(dest, f['name'])
        url = src + '/' + f['name']
        if filesize == 0:                 # size FROM RESPONSE
            try:
                print('creating dir:', path)
                os.mkdir(path)
                sync(src + '/' + f['name'], path, tok)
            except IOError as e:
                print("mkdir `%s': %s" % (e.filename, e.strerror), file=sys.stderr)
                sys.exit(-1)
        else:
            try:
                if not os.path.exists(path) or os.path.getsize(path) == 0:    # filesize FROM OS
                    print('\ndownloading: ' , path)
                    with open(path, 'w+b') as fh:
                        geturl(url, tok, fh)
                else:
                    print('skipping: ', path)
            except IOError as e:
                print("open `%s': %s" % (e.filename, e.strerror), file=sys.stderr)
                sys.exit(-1)
    return 0

def _main(argv):
    parser = argparse.ArgumentParser(prog=argv[0], description=DESC)
    parser.add_argument('-s', '--source', dest='source', metavar='URL', help='Recursively download files at URL', required=True)
    parser.add_argument('-d', '--destination', dest='destination', metavar='DIR', help='Store directory structure in DIR', required=True)
    parser.add_argument('-t', '--token', dest='token', metavar='TOK', help='Use app token TOK to authenticate', required=True)
    args = parser.parse_args(argv[1:])
    if not os.path.exists(args.destination):
        os.makedirs(args.destination)
    return sync(args.source, args.destination, args.token)

if __name__ == '__main__':
    try:
        # If running from an IDE like Spyder
        if len(sys.argv) == 1:
            sys.argv.extend([
                '-s', 'https://nrt3.modaps.eosdis.nasa.gov/archive/allData/',
                '-d', 'D:/FireData_27May2025/VIIRS_2024_06',
                '-t', 'eyJ0eXAiOiJKV1QiLCJvcmlnaW4iOiJFYXJ0aGRhdGEgTG9naW4iLCJzaWciOiJlZGxqd3RwdWJrZXlfb3BzIiwiYWxnIjoiUlMyNTYifQ.eyJ0eXBlIjoiVXNlciIsInVpZCI6InNpbmdocmFtLmFybWVuaWEiLCJleHAiOjE3NTQ4MjE0NTIsImlhdCI6MTc0OTYzNzQ1MiwiaXNzIjoiaHR0cHM6Ly91cnMuZWFydGhkYXRhLm5hc2EuZ292IiwiaWRlbnRpdHlfcHJvdmlkZXIiOiJlZGxfb3BzIiwiYWNyIjoiZWRsIiwiYXNzdXJhbmNlX2xldmVsIjozfQ.b8rVXsoRQpSiIoDCgALBF3tlneidMkl21Hqu7IyRaL_1RjgOoWpKOItlQArbGBcjS1MoFntGm4vOxcC2GXcoN9qRcM1UzZD3IM5lW-tTvwwTm86z0FL6jTTeue12jgRs_X8zouEvO6eFYjOhwflcoGXYdlhi6lnOPgA05Lxi49eI1ak7uEvPNLw5enCvNpOyrnPTaiMSaO3BjcftEi_ZsmkSrWgdscv9MguftD9Pz3HD6pFXm1mW4PuxIPQJS0AJmRBythSbYPdRWAQOislHWfetPObYj7fafhQ6MqvVEyNXtuT9RJas6hYZoe2M0lyrVg6HMlsolX2OcPgcYP22JQ'  # Replace with your token
             
            ])
        sys.exit(_main(sys.argv))
    except KeyboardInterrupt:
        sys.exit(-1)
        
# bearer_token = ""  # Replace with your token
# aoi_shapefile = "D:/FireData_27May2025/AdminBoundary/UK_State4326.shp"  # <-- Update
# output_folder = "D:/FireData_27May2025/outputfolder"
        
        
        
        