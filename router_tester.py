# encoding: utf-8

import csv
import logging
import connectors as router
import export_results as export


logging.basicConfig(level='DEBUG', format = '%(asctime)s :: %(levelname)s :: %(message)s')
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

def get_test_cases_from_csv_file(csv_file) :
    with open(csv_file,'r') as f:
        csv_reader = csv.DictReader(f, delimiter=';')
        for row in csv_reader:
            #test_case = {"to" : (45.77316,3.06115), "from": (45.77090,3.08228), "mode": "bicycling"}
            test_case = {}
            test_case["from"] = row['origin'].split('/')
            test_case["to"] = row['destination'].split('/')
            test_case["mode"] = row['mode']
            test_case["id"] = row['id']
            yield test_case

def _add_field_to_test_results(result_list, key_to_add, function, key_source, key_reference):
    return [dict({key_to_add : function(a_test_result[key_source], a_test_result[key_reference])}, **a_test_result) for a_test_result in result_list]

def add_deviation_to_google(result_list) :
    logger.info("Compute duration & distance deviations to Google")
    _compute_deviation = lambda source,reference : 100 * (source - reference) /reference
    result_list = _add_field_to_test_results(result_list, 'kraken_distance_deviation_with_google', _compute_deviation, 'kraken_distance', 'google_distance')
    result_list = _add_field_to_test_results(result_list, 'kraken_duration_deviation_with_google', _compute_deviation, 'kraken_duration', 'google_duration')
    result_list = _add_field_to_test_results(result_list, 'valhalla_distance_deviation_with_google', _compute_deviation, 'valhalla_distance', 'google_distance')
    result_list = _add_field_to_test_results(result_list, 'valhalla_duration_deviation_with_google', _compute_deviation, 'valhalla_duration', 'google_duration')
    return result_list

def remove_not_consistent_test_results(result_list) :
    logger.info("Remove non consistent test results")
    result_list = [res for res in result_list if all(d in res for d in ("kraken_duration", "valhalla_duration", "google_duration"))]
    return result_list

def order_test_results(result_list, order_criteria) :
    logger.info("Sort results")
    return sorted(result_list, key=lambda result: float(result[order_criteria]))

def update_test_result_with_router_results(test_results, router, router_name):
    if router:
        test_results["{}_distance".format(router_name)] = router['distance']
        test_results["{}_duration".format(router_name)] = router['duration']

def router_compare(test_case_file):
    test_result_list = []

    for a_test_case in get_test_cases_from_csv_file(test_case_file):
        test_result = dict(a_test_case)
        logger.info("Testing element " + a_test_case['id'])
        test_router_kraken = router.get_distance_and_duration_from_navitia(a_test_case["from"], a_test_case["to"], a_test_case["mode"])
        test_router_valhalla = router.get_distance_and_duration_from_navitia(a_test_case["from"], a_test_case["to"], a_test_case["mode"], additionnal_params={"_override_scenario": "experimental"})
        test_router_google = router.get_distance_and_duration_from_google_directions(a_test_case["from"], a_test_case["to"], a_test_case["mode"])
        test_router_superman = router.get_crow_fly_distance(a_test_case["from"], a_test_case["to"])

        update_test_result_with_router_results(test_result, test_router_kraken, "kraken")
        update_test_result_with_router_results(test_result, test_router_valhalla, "valhalla")
        update_test_result_with_router_results(test_result, test_router_google, "google")

        test_result["superman_distance"] = test_router_superman['distance']

        test_result_list.append(test_result)


    test_result_list = order_test_results(test_result_list, "superman_distance")

    for mode in ('walking', 'driving', 'bicycling'):
        export.get_results_as_csv_for_a_mode(test_result_list, mode)

    test_result_list = remove_not_consistent_test_results(test_result_list)
    test_result_list = add_deviation_to_google(test_result_list)

    for mode in ('walking', 'driving', 'bicycling'):
        export.get_results_as_box_for_a_mode(test_result_list, mode)


if __name__ == '__main__':
    router_compare("./test_cases/auvergne.csv")
