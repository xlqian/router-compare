#! /usr/bin/python
"""Bench Jormungandr

Usage:
  bench.py (-h | --help)
  bench.py --version
  bench.py bench [-i FILE | --input=FILE] [-a ARGS | --extra-args=ARGS] [-c CONCURRENT | --concurrent=CONCURRENT]
  bench.py replot [<file> <file>]
  bench.py plot-latest N
   
Options:
  -h --help                                 Show this screen.
  --version                                 Show version.
  -i <FILE>, --input=<FILE>                 Input csv (or stdin if missing)
  -a <ARGS>, --extra-args=<ARGS>            Extra args for the request
  -c <CONCURRENT>, --concurrent=CONCURRENT  Concurrent request number

Example:
  bench.py bench --input=benchmark.csv -a 'first_section_mode[]=car&last_section_mode[]=car'
  bench.py replot new_default.csv experimental.csv
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
import csv
from config import logger
import config
import sys
import sortedcontainers
from glob import glob
from concurrent.futures import ThreadPoolExecutor, as_completed

NAVITIA_API_URL = os.getenv('NAVITIA_API_URL', config.NAVITIA_API_URL)
COVERAGE = os.getenv('COVERAGE', config.COVERAGE)
TOKEN = os.getenv('TOKEN', config.TOKEN)
DISTANT_BENCH_OUTPUT = os.getenv('DISTANT_BENCH_OUTPUT', config.DISTANT_BENCH_OUTPUT)
OUTPUT_DIR = os.getenv('OUTPUT_DIR', config.OUTPUT_DIR)

def get_coverage_start_production_date():
    r = requests.get("{}/coverage/{}".format(NAVITIA_API_URL, COVERAGE), headers={'Authorization': TOKEN})
    j = r.json()
    return datetime.datetime.strptime(j['regions'][0]['start_production_date'], '%Y%m%d')


def get_request_datetime(start_prod_date, days_shift, seconds):
    return start_prod_date + datetime.timedelta(days=days_shift, seconds=seconds)

def _call_jormun(url):
    import time
    time1 = time.time()
    r = requests.get(url, headers={'Authorization': TOKEN})
    time2 = time.time()
    elapsed_time = (time2-time1)*1000.0
    return r, elapsed_time

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

def call_jormun(server, path, parameters, scenarios_name, extra_args):
    url = "{}{}?{}&_override_scenario={}&{}".format(server, path, parameters, scenarios_name, extra_args)
    ret, t = _call_jormun(url)
    return scenarios_name, url, t, ret.status_code

def call_jormun_scenarios(i, server, path, parameters, extra_args, scenarios):
    return i, [call_jormun(server, path, parameters, scenarios_name, extra_args) for scenarios_name in scenarios]

class Scenario(object):
    def __init__(self, name, output_dir):
        self.name = name
        self.times = sortedcontainers.SortedDict()
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        self.output = open(os.path.join(output_dir, "{}.csv".format(name)), 'w')
        print("No,url,elapsed time,status_code", file=self.output)

    def __del__(self):
        self.output.close()

def submit_work(pool, input_file, scenarios, extra_args):
    for i, req in enumerate(line for line in csv.DictReader(input_file)):
        params = [i, NAVITIA_API_URL, req['path'], req['parameters'], extra_args, scenarios]
        yield pool.submit(call_jormun_scenarios, *params)

def get_file_lines_num(input_file):
    position = input_file.tell()
    num_lines = sum(1 for line in input_file) - 1 # size minus header file

    input_file.seek(position)
    return num_lines
    
def bench(args):
    extra_args = args['--extra-args'] or ''
    concurrent = int(args['--concurrent'] or 1)

    input_file_name = args['--input'] or None
    input_file = sys.stdin
    args = {}

    scenarios = { s : Scenario(s, OUTPUT_DIR) for s in ['new_default', 'experimental'] }

    if input_file_name:
        input_file = open(input_file_name)
        args['total'] = get_file_lines_num(input_file)

    with ThreadPoolExecutor(concurrent) as pool:   
        futures = (f for f in submit_work(pool, input_file, scenarios, extra_args))

        for i in tqdm.tqdm(as_completed(futures), **args):
            idx, requests = i.result()
           
            if any(status_code >=300 for _, _, _, status_code in requests ):
                continue

            #import pdb;pdb.set_trace()
            for scenario_name, url, time, code in requests:
                print("{},{},{},{}".format(idx, url, time, code), file=scenarios[scenario_name].output)
                scenarios[scenario_name].times[idx] = time


    input_file.close()
    
    new_default_times = scenarios['new_default'].times.values();
    experimental_times = scenarios['experimental'].times.values();
    
    plot_per_request(new_default_times, experimental_times, 'new_default', 'experimental')
    plot_normalized_box(new_default_times, experimental_times, 'new_default', 'experimental')
    
def get_times(csv_path):
    times = []
    try:
        import csv
        with open(csv_path, 'rb') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                times.append(float(row['elapsed time']))
        logger.info('Finish parsing: {}'.format(csv_path))       
    except Exception as e:
        import sys
        logger.error('Error occurred when parsing csv: ' + str(e))
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
        coverage_name = cov.split('/')[-2]
        box.title = coverage_name
        for output in latest_bench_outputs[::-1]:
            time_array1 = get_times(os.path.join(output, "{}.csv".format('experimental')))
            time_array2 = get_times(os.path.join(output, "{}.csv".format('new_default')))
            if len(time_array1) == len(time_array2):
                box.add(output.split('/')[-2], numpy.array(time_array1) / numpy.array(time_array2))
        box.render_to_file(os.path.join(DISTANT_BENCH_OUTPUT, 'rendering', '{}.svg'.format(coverage_name)))


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
