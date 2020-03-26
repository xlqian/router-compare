Jormungandr Bench Tool
==============

Compare the performance between senario new_default and experimental.

## Dependencies

To install the dependencies use `pip3`:

```bash
pip3 install -r requirements.txt
````

## Usage

* Setup the configuration in `config.py`
* generate a `benchmark.csv` with `benchmark` in navitia project

Then do :

```bash
NAVITIA_API_URL=http://api.navitia.io TOKEN="3b036afe-0110-4202-b9ed-99718476c2e0" python3 bench.py bench -i ./benchmark_example.csv -c 6
```

This command will generate two files containing url and collapsed time.

You can use `replot` command to redraw the result:

```bash
./bench.py replot
```



