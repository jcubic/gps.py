#!/usr/bin/env python

from __future__ import division
import simplejson as json
from PIL import Image
from dateutil import parser
from optparse import OptionParser
from subprocess import call
from datetime import datetime, timedelta
from os import listdir
from os.path import isfile, join
from io import StringIO
from datetime import datetime

import dateutil
import time

def get_date_taken(path):
    """Return date from Photo EXIF data."""
    return parse_date(Image.open(path)._getexif()[36867])

def parse_date(str):
    """Parses string as date in EXIF format."""
    return datetime.strptime(str, "%Y:%m:%d %H:%M:%S")

def get_gps_google(gps, date, hours_shift = None):
    """Find single row in data based on Google GPS location.

    You can get GPS data for you Andorid phone in Google takeout."""
    def nearest(items, pivot):
        return min(items, key=lambda x: abs(x - pivot))
    def comparator(date, hours_shift = None):
        def compare(x):
            current = datetime.fromtimestamp(int(x['timestampMs']) / 1000.0)
            if hours_shift is not None:
                current = current + timedelta(seconds = hours_shift * 60 * 60)
            return abs(current - date)
        return compare

    def timestamp(dt, epoch=datetime(1970,1,1)):
        td = dt - epoch
        return (td.microseconds + (td.seconds + td.days * 86400) * 10**6) / 10**6

    def timezone(date, hours):
        return date - timedelta(seconds = hours * 60 * 60)
    return min(gps['locations'], key=comparator(date, hours_shift))

def get_gps_csv(data, date, hours_shift = None):
    """find single row in CSV data

    it always return row that have the minimum difference for a given date.
    hours_shift is used when camera have timezone and CSV doesn't
    The shift should take into account the time saving and modify the shift
    accordinly."""
    def comparator(date, hours_shift):
        def compare(x):
            current = x['time']
            #print '-'*20
            #print current
            if hours_shift is not None:
                current = current + timedelta(seconds = hours_shift * 60 * 60)
            #print current
            return abs(current - date)
        return compare
    return min(data, key=comparator(date, hours_shift))

def map_dict(x, d):
    """function return new dictionary based on x but keys are renamed based on d mapping"""
    return dict((d[k],x[k]) for k in d.keys() if k in x)

def parse_csv_row(x):
    """Function return proper parser for CSV row from csv.DictReader.

    it use sample row to detect what function to return."""
    def gps_logger(x):
        """Adroid GPS logger application CSV files"""
        time = dateutil.parser.parse(x['date time'])
        result = dict((k,x[k]) for k in ('latitude', 'longitude', 'altitude(m)') if k in x)
        result['time'] = time
        return result
    def gps_columbus(x):
        """Hardware GPS logger Columbus V-1000"""
        time = dateutil.parser.parse(as_date(x['DATE'], x['TIME']))
        mapping = {
            'LATITUDE N/S': 'latitude',
            'LONGITUDE E/W': 'longitude',
            'HEADING': 'direction',
            'HEIGHT': 'altitude(m)'
        }
        result = map_dict(x, mapping)
        result['time'] = time
        return result
    if 'INDEX' in x and 'TAG' in x:
        return gps_columbus
    elif 'type' in x and 'date time' in x:
        return gps_logger
    else:
        raise Exception('unrecognized CSV format')

def get_files(dirname):
    """return all filenames from directory."""
    files = []
    for f in listdir(dirname):
        path = join(dirname, f)
        if isfile(path):
            files.append(path)
    return files

def get_combo_file(dirname):
    """Create fake file with content of directory that contain text files.

    This function can be used to get all csv files as single StringIO file."""
    output = []
    for filename in get_files(dirname):
        with open(filename) as f:
          content = f.readlines()
          if len(output) == 0:
              output.append(content[0])
          output = output + content[1:]
    return StringIO("\n".join(output))

def parse_csv(csvfile):
    """detect and parse CSV file."""
    input_list = list(csv.DictReader(csvfile))
    fn = parse_csv_row(input_list[0])
    return [ fn(row) for row in input_list ]

def time_diff(d1, d2):
    """calculate time difference between two date times."""
    d1_ts = time.mktime(d1.timetuple())
    d2_ts = time.mktime(d2.timetuple())
    return abs(int(d2_ts-d1_ts)) / 60 / 60

def format_number(number, separator):
    """function convert number in CSV format of Columbus V-1000 GPS logger"""
    string = str(number)
    if len(string) % 2 != 0:
        raise Exception("Invalid number %s" % number)
    size = int(len(string) / 2)
    return separator.join([ string[x*2:(x*2)+2] for x in range(size) ])

def as_date(date, time):
    """Convert date and time into proper date-time string"""
    return " ".join(["20%s" % format_number(date, "-"), format_number(time, ":")])

if __name__ == '__main__':
    from sys import argv
    opt = OptionParser()
    opt.add_option('-l', '--location')
    opt.add_option('-r', '--ref')
    opt.add_option('-s', '--shift')
    opt.add_option('-w', '--wikipedia')
    opt.add_option('-f', '--format')
    opt.add_option('', '--directory')
    opt.add_option('-d', '--display', action="store_true")
    (options, args) = opt.parse_args()
    if (options.location is None and options.directory is None) or len(args) == 0:
        print("This script can be used to add GPS coordinate from google takeout")
        print("or csv file from GPS logger android app to image")
        print()
        print("usage %s [--format google | csv] [--shift <hours shift>] [--ref refence image] --location [History JSON or CSV File] <IMAGE FILE>" % argv[0])
        print("--shift daytime saving -1 for summer use in quotes")
        print("--ref image used as reference that is located in GPS file for " +
              "cases when you have image in same place but different day that" +
              " don't have location file")
    else:
        for filename in args:
            if options.ref is not None:
                input_file = options.ref
            else:
                input_file = filename
            date = get_date_taken(input_file)
            print(date)
            if options.format is None or options.format == 'google':
                gps_list = json.loads(open(options.location).read())

                if options.shift is not None:
                    loc = get_gps(gps_list, date, -float(options.shift))
                else:
                    loc = get_gps(gps_list, date)
                found = datetime.fromtimestamp(
                    int(loc['timestampMs']) / 1000.0
                )
                lat = str(int(loc['latitudeE7']) / 1e7)
                lng = str(int(loc['longitudeE7']) / 1e7)
                if options.location is not None:
                    print('lat: %s\nlong: %s' % (lat, lng))
                else:
                    call([
                        'exiftool',
                        '-m',
                        '-GPSLatitude=%s' % lat,
                        '-GPSLongitude=%s' % lng,
                        filename
                    ])
            elif options.format == 'csv':
                import csv
                if options.directory is not None:
                    csv_data = parse_csv(get_combo_file(options.directory))
                else:
                    with open(options.location, 'rt') as csvfile:
                        csv_data = parse_csv(csvfile)

                if options.shift is not None:
                    shift = -float(options.shift)
                    loc = get_gps_csv(csv_data, date, hours_shift = shift)
                    diff = time_diff(loc['time'], date)
                    diff = diff - shift
                else:
                    loc = get_gps_csv(csv_data, date)
                    diff = time_diff(loc['time'], date)
                if False and diff > 1:
                    print(filename)
                    print("diff %.2f hours" % diff)
                    print("SKIP")
                elif options.display: ## debug option
                    print(filename)
                    print("diff %.2f hours" % diff)
                    print('date: %s\nlat: %s\nlong: %s\nalt: %s' % (loc['time'], loc['latitude'], loc['longitude'], loc['altitude(m)']))
                    print('wiki: {{location|%s|%s}}' % (loc['latitude'], loc['longitude']))
                    print('-' * 30)
                elif loc['latitude'][-1] in ['N', 'S'] and loc['longitude'][-1] in ['W', 'E']:
                    ## Columbus have proper Ref data in CSV that indicate North/South East/West
                    lat_ref = loc['latitude'][-1]
                    long_ref = loc['longitude'][-1]
                    call([
                        'exiftool',
                        '-m',
                        '-GPSLatitude=%s' % loc['latitude'],
                        '-GPSLatitudeRef=%s' % lat_ref,
                        '-GPSLongitude=%s' % loc['longitude'],
                        '-GPSLongitudeRef=%s' % long_ref,
                        '-GPSAltitude*=%s' % loc['altitude(m)'],
                        filename
                    ])
                else:
                    call([
                        'exiftool',
                        '-m',
                        '-GPSLatitude*=%s' % loc['latitude'],
                        '-GPSLongitude*=%s' % loc['longitude'],
                        '-GPSAltitude*=%s' % loc['altitude(m)'],
                        filename
                    ])
