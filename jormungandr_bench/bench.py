#! /usr/bin/python
"""Bench Jormungandr

Usage:
  bench.py (-h | --help)
  bench.py --version
  bench.py bench (-i FILE | --input=FILE) [-a ARGS | --extra-args=ARGS]
  bench.py replot [<file> <file>]
  bench.py plot-latest N
   
Options:
  -h --help                             Show this screen.
  --version                             Show version.
  -i <FILE>, --input=<FILE>             input csv
  -a <ARGS>, --extra-args=<ARGS>        Extra args for the request

Example:
  bench.py bench --input=benchmark.csv -a 'first_section_mode[]=car&last_section_mode[]=car'
  bench.py replot new_default.csv experimental.csv
  bench.py replot 
  bench.py plot-latest 30
   
"""
from __future__ import print_function
import requests
import json
import datetime
import numpy
import tqdm
import logging
import pygal
import os
from config import logger
import config
from glob import glob

NAVITIA_API_URL = os.getenv('NAVITIA_API_URL') 
NAVITIA_API_URL = NAVITIA_API_URL if NAVITIA_API_URL else config.NAVITIA_API_URL 

COVERAGE = os.getenv('COVERAGE')
COVERAGE = COVERAGE if COVERAGE else config.COVERAGE 

TOKEN = os.getenv('TOKEN')
TOKEN = TOKEN if TOKEN else config.TOKEN     

DISTANT_BENCH_OUTPUT = os.getenv('DISTANT_BENCH_OUTPUT')
DISTANT_BENCH_OUTPUT = DISTANT_BENCH_OUTPUT if DISTANT_BENCH_OUTPUT else config.DISTANT_BENCH_OUTPUT    

OUTPUT_DIR = os.getenv('OUTPUT_DIR')
OUTPUT_DIR = OUTPUT_DIR if OUTPUT_DIR else config.OUTPUT_DIR    

def parse_request_csv(csv_path):
    logger.info('Start parsing csv: {}'.format(csv_path))
    import csv
    import string
    requests = []
    try:
        with open(csv_path) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row[' arrival'] != '-1':
                    requests.append((row['Start'].strip(' '), 
                                row[' Target'].strip(' '), 
                                row[' Day'], 
                                row[' Hour']))
        logger.info('Finish parsing: {} requests'.format(len(requests)))       
    except Exception as e:
        import sys
        logger.error('Error occurred when parsing csv: ' + str(e))
    return requests

def get_coverage_start_production_date():
    r = requests.get("{}/coverage/{}".format(NAVITIA_API_URL, COVERAGE), headers={'Authorization': TOKEN})
    j = r.json()
    return datetime.datetime.strptime(j['regions'][0]['start_production_date'], '%Y%m%d')

def get_request_datetime(start_prod_date, days_shift, seconds):
    return start_prod_date + datetime.timedelta(days=days_shift, seconds=seconds)

def _call_jormun(url, times=1):
    import time
    time1 = time.time()
    for _ in range(times): 
        r = requests.get(url, headers={'Authorization': TOKEN})
    time2 = time.time()
    collapsed_time = (time2-time1)*1000.0/times  
    return r, collapsed_time

def call_jormun(reqs, scenario, extra_args):
    start_prod_date = get_coverage_start_production_date()
    logger.info("calling scenario: " + scenario)
    collapsed_time = []

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    with open(os.path.join(OUTPUT_DIR, "{}.csv".format(scenario)), 'w') as f:
        print("No,url,collapsed time", file=f)
        for i, r in tqdm.tqdm(list(enumerate(reqs))):
            req_datetime = get_request_datetime(start_prod_date, int(r[2]), int(r[3]))
            req_url = "{}/coverage/{}/journeys?from={}&to={}&datetime={}&_override_scenario={}&{}".format(
                NAVITIA_API_URL, COVERAGE, r[0], r[1], req_datetime.strftime('%Y%m%dT%H%M%S'), scenario, extra_args)
            ret, t = _call_jormun(req_url, 1)
            if ret.status_code != 200:
                logger.error("calling error: {} {}".format(i, req_url))
            print("{},{},{}".format(i, req_url, t), file=f)
            collapsed_time.append(t)
    return collapsed_time    

def plot_per_request(array1, array2, label1='', label2=''):
    line_chart = pygal.Line(show_x_labels=False)
    line_chart.title = 'Jormun Bench (in ms)'
    line_chart.x_labels = map(str, range(0, len(array1)))
    line_chart.add(label1, array1)
    line_chart.add(label2, array2)
    line_chart.render_to_file('output_per_request.svg')

def plot_normalized_box(array1, array2, label1='', label2=''):
    import numpy as np
    box = pygal.Box()
    box.title = 'Jormun Bench Box Comparaison (in ms)'
    box.add('Time Ratio: {}/{}'.format(label2, label1), np.array(array2) / np.array(array1))
    box.render_to_file('output_box.svg')

def bench(args):
    reqs = parse_request_csv(args['--input'])
    extra_args = args['--extra-args'] or ''
    collapsed_time_new_default = call_jormun(reqs, 'new_default', extra_args)
    collapsed_time_experimental = call_jormun(reqs, 'experimental', extra_args)
    plot_per_request(collapsed_time_new_default, collapsed_time_experimental, 'new_default', 'experimental')
    plot_normalized_box(collapsed_time_new_default, collapsed_time_experimental, 'new_default', 'experimental')
    
def get_times(csv_path):
    times = []
    try:
        import csv
        with open(csv_path, 'rb') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                times.append(float(row['collapsed time']))
        logger.info('Finish parsing: {}'.format(csv_path))       
    except Exception as e:
        import sys
        logger.err('Error occurred when parsing csv: ' + str(e))
    return times
    
def replot(args):
    files = args.get('<file>') or ['new_default.csv', 'experimental.csv']
    file1 = files[0]
    file2 = files[1]
    time_arry1 = get_times(file1)
    time_arry2 = get_times(file2)
    plot_per_request(time_arry1, time_arry2,file1, file2)    
    plot_normalized_box(time_arry1, time_arry2,file1, file2)    

def get_benched_coverage_from_output():
    return glob(DISTANT_BENCH_OUTPUT + '/output/*/')

def get_latest_bench_output(coverage, n):
    bench_outputs = glob(coverage + '/*/')
    bench_outputs.sort(reverse=True)
    return bench_outputs[:n]

def plot_latest(args):
    n = int(args.get('N'))
    coverages = get_benched_coverage_from_output()
    if not os.path.exists(os.path.join(DISTANT_BENCH_OUTPUT, 'rendering')):
       os.makedirs(os.path.join(DISTANT_BENCH_OUTPUT, 'rendering'))  

    for cov in coverages:
        latest_bench_outputs = get_latest_bench_output(cov, n)
        box = pygal.Box(box_mode="tukey")
        box.title = cov.split('/')[2]
        for output in latest_bench_outputs:
            time_array1 = get_times(os.path.join(output, "{}.csv".format('experimental')))
            time_array2 = get_times(os.path.join(output, "{}.csv".format('new_default')))
            box.add(output.split('/')[3], numpy.array(time_array1) / numpy.array(time_array2))
        box.render_to_file(os.path.join(DISTANT_BENCH_OUTPUT, 'rendering', '{}.svg'.format(cov.split('/')[2])))
        
def parse_args():
    from docopt import docopt
    return docopt(__doc__, version='Jormungandr Bench V0.0.1')

def main():
    args = parse_args()
    logger.info('Running Benchmark on {}/{}'.format(NAVITIA_API_URL, COVERAGE))
    if args.get('bench'):
        bench(args)
    if args.get('replot'):
        replot(args)
    if args.get('plot-latest'):
        plot_latest(args)

if __name__ == '__main__':
    main()
