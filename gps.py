#!/usr/bin/env python

from __future__ import division
import simplejson as json
from PIL import Image
from dateutil import parser
from optparse import OptionParser
from subprocess import call
from datetime import datetime, timedelta
import dateutil

def get_date_taken(path):
    return Image.open(path)._getexif()[36867]

def parse_date(str):
    return datetime.strptime(str, "%Y:%m:%d %H:%M:%S")


def get_gps_google(gps, date, hours_shift = None):
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


def parse_csv_row(x):
    time = dateutil.parser.parse(x['date time'])
    result = dict((k,x[k]) for k in ('latitude','longitude','altitude(m)', 'date time') if k in x)
    result['time'] = time
    return result
    
from os import listdir
from os.path import isfile, join
from io import StringIO
from datetime import datetime
import time


def get_files(dirname):
    files = []
    for f in listdir(dirname):
        path = join(dirname, f)
        if isfile(path):
            files.append(path)
    return files

def get_combo_file(dirname):
    output = []
    for filename in get_files(dirname):
        with open(filename) as f:
          content = f.readlines()
          if len(output) == 0:
              output.append(content[0])
          output = output + content[1:]
    return StringIO("\n".join(output))
          
    
def parse_csv(csvfile):
    reader = csv.DictReader(csvfile)
    return [ parse_csv_row(row) for row in reader ]

def time_diff(d1, d2):
    d1_ts = time.mktime(d1.timetuple())
    d2_ts = time.mktime(d2.timetuple())
    return abs(int(d2_ts-d1_ts)) / 60 / 60



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
    if (options.location is None and options.directory is None) or len(args) != 1:
        print("This script can be used to add GPS coordinate from google takeout")
        print("or csv file from GPS logger android app to image")
        print()
        print("usage %s [--format google | csv] [--shift <hours shift>] [--ref refence image] --location [History JSON File] <IMAGE FILE>" % argv[0])
        print("--shift daytime saving -1 for summer use in quotes")
        print("--ref image used as reference that is located in GPS file for " +
              "cases when you have image in same place but different day that" +
              " don't have location file")
    else:
        if options.ref is not None:
            input_file = options.ref
        else:
            input_file = args[0]
        date = parse_date(get_date_taken(input_file))
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
                    args[0]
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
                diff = time_diff(dateutil.parser.parse(loc['date time']), date)
                diff = diff - shift
            else:
                loc = get_gps_csv(csv_data, date)
                diff = time_diff(dateutil.parser.parse(loc['date time']), date)
            if False and diff > 1:
                print(args[0])
                print("diff %.2f hours" % diff)
                print("SKIP")
            elif options.display:
                print(args[0])
                print("diff %.2f hours" % diff)
                print('date: %s\nlat: %s\nlong: %s\nalt: %s' % (loc['date time'], loc['latitude'], loc['longitude'], loc['altitude(m)']))
                print('wiki: {{location|%s|%s}}' % (loc['latitude'], loc['longitude']))
                print('-' * 30)
            else:
                call([
                    'exiftool',
                    '-m',
                    '-GPSLatitude*=%s' % loc['latitude'],
                    '-GPSLongitude*=%s' % loc['longitude'],
                    '-GPSAltitude*=%s' % loc['altitude(m)'],
                    args[0]
                ])
