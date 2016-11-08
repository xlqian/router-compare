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
./bench.py bench --input=benchmark_example.csv -a 'first_section_mode[]=car&last_section_mode[]=car'
```

This command will generate two files containing url and collapsed time.

You can use `replot` command to redraw the result:

```bash
./bench.py replot
```



