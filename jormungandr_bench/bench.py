#! /usr/bin/python
"""Bench Jormungandr

Usage:
  bench.py (-h | --help)
  bench.py --version
  bench.py bench (-i FILE | --input=FILE) [-a ARGS | --extra-args=ARGS]
  bench.py replot [<file> <file>]
   
Options:
  -h --help                             Show this screen.
  --version                             Show version.
  -i <FILE>, --input=<FILE>             input csv
  -a <ARGS>, --extra-args=<ARGS>        Extra args for the request

Example:
  ./bench.py bench --input=benchmark.csv -a 'first_section_mode[]=car&last_section_mode[]=car'
  ./bench replot new_default.csv experimental.csv
  ./bench replot 
"""
from __future__ import print_function
import requests
import json
import datetime
import numpy
import tqdm
from config import JORMUN_URL, COVERAGE


class bcolors:
    INFO = '\033[95m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_info(string):
    print(bcolors.INFO+string+bcolors.ENDC)

def print_ok(string):
    print(bcolors.OKGREEN+string+bcolors.ENDC)

def print_err(string):
    print(bcolors.FAIL+string+bcolors.ENDC)

def parse_request_csv(csv_path):
    print_ok('Start parsing csv: {}'.format(csv_path))
    import csv
    import string
    requests = []
    try:
        with open(csv_path, 'rb') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row[' arrival'] != '-1':
                    requests.append((string.strip(row['Start'], ' '), 
                                string.strip(row[' Target'], ' '), 
                                row[' Day'], 
                                row[' Hour']))
        print_ok('Finish parsing: {} requests'.format(len(requests)))       
    except Exception as e:
        import sys
        print_err('Error occurred when parsing csv: ' + str(e))
    return requests

def get_coverage_start_production_date():
    r = requests.get("{}/coverage/{}".format(JORMUN_URL, COVERAGE))
    j = json.loads(r.content)
    return datetime.datetime.strptime(j['regions'][0]['start_production_date'], '%Y%m%d')

def get_request_datetime(start_prod_date, days_shift, seconds):
    return start_prod_date + datetime.timedelta(days=days_shift, seconds=seconds)

def _call_jormun(url, times=1):
    import time
    time1 = time.time()
    for _ in range(times): 
        r = requests.get(url)
    time2 = time.time()
    collapsed_time = (time2-time1)*1000.0/times    
    return r, collapsed_time

def call_jormun(reqs, scenario, extra_args):
    start_prod_date = get_coverage_start_production_date()
    print_info("calling scenario: " + scenario)
    collapsed_time = []
    with open("{}.csv".format(scenario), 'w') as f:
        print("No,url,collapsed time", file=f)
        for i, r in tqdm.tqdm(list(enumerate(reqs))):
            req_datetime = get_request_datetime(start_prod_date, int(r[2]), int(r[3]))
            req_url = "{}/coverage/{}/journeys?from={}&to={}&datetime={}&_override_scenario={}&{}".format(
                JORMUN_URL, COVERAGE, r[0], r[1], req_datetime.strftime('%Y%m%dT%H%M%S'), scenario, extra_args)
            _, t = _call_jormun(req_url, 1)
            print("{},{},{}".format(i, req_url, t), file=f)
            collapsed_time.append(t)
    return collapsed_time    

def plot(array1, array2):
    import numpy
    import matplotlib.pyplot as plt
    array1_np = numpy.array(array1)
    array2_np = numpy.array(array2)
    plt.plot(array1_np, 'r--')
    plt.plot(array2_np, 'b--')
    plt.show()

def bench(args):
    reqs = parse_request_csv(args['--input'])
    extra_args = args['--extra-args'] or ''
    collapsed_time_new_default = call_jormun(reqs, 'new_default', extra_args)
    collapsed_time_experimental = call_jormun(reqs, 'experimental', extra_args)
    plot(collapsed_time_new_default, collapsed_time_experimental)

def get_times(csv_path):
    times = []
    try:
        import csv
        with open(csv_path, 'rb') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                times.append(float(row['collapsed time']))
        print_ok('Finish parsing: {}'.format(csv_path))       
    except Exception as e:
        import sys
        print_err('Error occurred when parsing csv: ' + str(e))
    return times
    
def replot(args):
    files = args.get('<file>') or ['new_default.csv', 'experimental.csv']
    file1 = files[0]
    file2 = files[1]
    time_arry1 = get_times(file1)
    time_arry2 = get_times(file2)
    plot(time_arry1, time_arry2)    

def parse_args():
    from docopt import docopt
    return docopt(__doc__, version='Jormungandr Bench V0.0.1')

def main():
    args = parse_args()
    if args.get('bench'):
        bench(args)
    if args.get('replot'):
        replot(args)
        
if __name__ == '__main__':
    main()
