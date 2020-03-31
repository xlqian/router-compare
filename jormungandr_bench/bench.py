#! /usr/bin/python
"""Bench Jormungandr

Usage:
  bench.py (-h | --help)
  bench.py --version
  bench.py bench (-i FILE | --input=FILE) [-a ARGS | --extra-args=ARGS] [-c CONCURRENT | --concurrent=CONCURRENT]
  bench.py sampling_bench <min_lon> <max_lon> <min_lat> <max_lat> [-n=SAMPLING_NUMBER | --sampling=SAMPLING_NUMBER] [-a ARGS | --extra-args=ARGS] [-c CONCURRENT | --concurrent=CONCURRENT]
  bench.py replot [<file> <file>]
  bench.py plot-latest N
   
Options:
  -h --help                                         Show this screen.
  --version                                         Show version.
  -i FILE, --input=FILE                             Input csv
  -a ARGS, --extra-args=ARGS                        Extra args for the request
  -n SAMPLING_NUMBER, --sampling SAMPLING_NUMBER    Sampling number [default: 1000]
  -c CONCURRENT, --concurrent=CONCURRENT            Concurrent request number [default: 1]

Example:
  bench.py bench --input=benchmark.csv -a 'first_section_mode[]=car&last_section_mode[]=car'
  bench.py replot new_default.csv experimental.csv
  bench.py sampling_bench 2.298255 2.411574 48.821590 48.898004 -n 1000  -c 4 -a 'datetime=20200320T100000'
  bench.py plot-latest 30
   
"""
from __future__ import print_function
import requests
import datetime
import numpy
import tqdm
import pygal
import os
from config import logger
import config
from glob import glob
import random

random.seed(42)

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


def parallel_process(array, function, n_workers=4, use_kwargs=False):
    """
        A parallel version of the map function with a progress bar.

        Args:
            array (array-like): An array to iterate over.
            function (function): A python function to apply to the elements of array
            n_jobs (int, default=16): The number of cores to use
            use_kwargs (boolean, default=False): Whether to consider the elements of array as dictionaries of
                keyword arguments to function
        Returns:
            [function(array[0]), function(array[1]), ...]
    """
    # If we set n_jobs to 1, just run a list comprehension. This is useful for benchmarking and debugging.
    from concurrent.futures import as_completed, ThreadPoolExecutor
    if n_workers == 1:
        return [function(**a) if use_kwargs else function(a) for a in tqdm.tqdm(array)]

    # Assemble the workers
    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        # Pass the elements of array into function
        if use_kwargs:
            futures = [pool.submit(function, **a) for a in array]
        else:
            futures = [pool.submit(function, a) for a in array]
        kwargs = {
            'total': len(array),
            'unit': 'it',
            'unit_scale': True,
            'leave': True
        }
        # Print out the progress as tasks complete
        for _ in tqdm.tqdm(as_completed(futures), **kwargs):
            pass
    out = []
    # Get the results from the futures.
    for i, future in enumerate(futures):
        try:
            out.append(future.result())
        except Exception as e:
            out.append(e)
    return out


def parse_request_csv(csv_path):
    logger.info('Start parsing csv: {}'.format(csv_path))
    import csv
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


def _call_jormun(i, url):
    import time
    time1 = time.time()
    r = requests.get(url, headers={'Authorization': TOKEN})
    time2 = time.time()
    if r.status_code != 200:
        print('error occurred on the url: ', url)
        return i, url, -1
    collapsed_time = (time2-time1)*1000.0
    return i, url, collapsed_time


def call_jormun(args, scenario, concurrent):
    logger.info("calling scenario: " + scenario)
    collapsed_time = []

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    out = parallel_process(args, _call_jormun, n_workers=concurrent, use_kwargs=True)
    out.sort(key=lambda x: x[0])

    with open(os.path.join(OUTPUT_DIR, "{}.csv".format(scenario)), 'w') as f:
        print("No,url,collapsed time", file=f)
        for i, req_url, t in out:
            print("{},{},{}".format(i, req_url, t), file=f)
            collapsed_time.append(t)
    return collapsed_time    


def plot_per_request(array1, array2, label1='', label2=''):
    line_chart = pygal.Line(show_x_labels=False, disable_xml_declaration=True)
    line_chart.title = 'Jormun Bench (in ms)'
    line_chart.x_labels = map(str, range(0, len(array1)))
    line_chart.add(label1, array1)
    line_chart.add(label2, array2)
    line_chart.render_to_file('output_per_request.svg')


def plot_scenario_box(array1, array2, label1='', label2=''):
    import numpy as np
    box = pygal.Box()
    box.title = 'Jormun Bench Per ScenarioBox (in ms)'
    box.add(label1, array1)
    box.add(label2, array2)
    box.render_to_file('output_per_scenario_box.svg')


def plot_normalized_box(array1, array2, label1='', label2=''):
    import numpy as np
    box = pygal.Box()
    box.title = 'Jormun Bench Box Comparaison (in ms)'
    box.add('Time Ratio: {}/{}'.format(label2, label1), np.array(array2) / np.array(array1))
    box.render_to_file('output_box.svg')


def bench(args):
    reqs = parse_request_csv(args['--input'])
    extra_args = args['--extra-args'] or ''
    concurrent = int(args['--concurrent'] or 1)

    def make_navitia_requests(reqs, scenario, extra_args):
        res = []
        start_prod_date = get_coverage_start_production_date()
        for i, r in enumerate(reqs):
            req_datetime = get_request_datetime(start_prod_date, int(r[2]), int(r[3]))
            res.append({"i": i,
                         "url": "{}/coverage/{}/journeys?from={}&to={}&datetime={}&_override_scenario={}&{}".format(
                             NAVITIA_API_URL, COVERAGE, r[0], r[1], req_datetime.strftime('%Y%m%dT%H%M%S'), scenario,
                             extra_args)})
        return res

    scenario = 'new_default'
    collapsed_time_new_default = call_jormun(make_navitia_requests(reqs, scenario, extra_args), scenario, concurrent)
    scenario = 'experimental'
    collapsed_time_experimental = call_jormun(make_navitia_requests(reqs, scenario, extra_args), scenario, concurrent)

    plot_per_request(collapsed_time_new_default, collapsed_time_experimental, 'new_default', 'experimental')
    plot_normalized_box(collapsed_time_new_default, collapsed_time_experimental, 'new_default', 'experimental')
    plot_scenario_box(collapsed_time_new_default, collapsed_time_experimental, 'new_default', 'experimental')

def sampling_bench(args):

    min_lon = float(args['<min_lon>'])
    max_lon = float(args['<max_lon>'])
    min_lat = float(args['<min_lat>'])
    max_lat = float(args['<max_lat>'])
    n = int(args['--sampling'])

    coords = []
    for i in range(n):
        from_coord = "{};{}".format(random.uniform(min_lon, max_lon),
                                    random.uniform(min_lat, max_lat))
        to_coord = "{};{}".format(random.uniform(min_lon, max_lon),
                                  random.uniform(min_lat, max_lat))
        coords.append((i, from_coord, to_coord))

    def make_navitia_requests(coords, scenario, extra_args):
        res = []
        for c in coords:
            i, f_coord, t_coord = c
            res.append({"i": i,
                        "url": "{}/coverage/{}/journeys?from={}&to={}&_override_scenario={}&{}".format(
                               NAVITIA_API_URL, COVERAGE, f_coord, t_coord, scenario, extra_args)})
        return res

    extra_args = args['--extra-args'] or ''
    concurrent = int(args['--concurrent'] or 1)
    scenario = "new_default"
    collapsed_time_new_default = call_jormun(make_navitia_requests(coords, scenario, extra_args),
                                             scenario,
                                             concurrent)

    scenario = "experimental"
    collapsed_time_experimental = call_jormun(make_navitia_requests(coords, scenario, extra_args),
                                              scenario,
                                              concurrent)

    plot_per_request(collapsed_time_new_default, collapsed_time_experimental, 'new_default', 'experimental')
    plot_normalized_box(collapsed_time_new_default, collapsed_time_experimental, 'new_default', 'experimental')
    plot_scenario_box(collapsed_time_new_default, collapsed_time_experimental, 'new_default', 'experimental')


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
        logger.error('Error occurred when parsing csv: ' + str(e))
    return times


def replot(args):
    files = args.get('<file>') or ['new_default.csv', 'experimental.csv']
    file1 = files[0]
    file2 = files[1]
    time_arry1 = get_times(file1)
    time_arry2 = get_times(file2)
    plot_per_request(time_arry1, time_arry2, file1, file2)
    plot_normalized_box(time_arry1, time_arry2, file1, file2)


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
    if args.get('sampling_bench'):
        sampling_bench(args)
    if args.get('replot'):
        replot(args)
    if args.get('plot-latest'):
        plot_latest(args)


if __name__ == '__main__':
    main()
