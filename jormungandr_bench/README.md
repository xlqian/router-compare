Jormungandr Bench Tool
==============

Compare the performance between senario new_default and experimental.

## Dependencies

To install the dependencies use `pip3`:

```bash
pip3 install -r requirements.txt
````


## Installation

Duplicate the auth_params_template folder and rename to auth_params.

Put your api keys in `auth_params/__init__.py` file:

```python
google_api_key = "<Your Google Maps API key>"

navitia_api_key = "<Your Navitia API key>"
navitia_base_url = "https://api.navitia.io/v1"
```


## Usage

To generate a performance comparison chart:

```bash
./bench.py --input=benchmark.csv -a 'first_section_mode[]=car&last_section_mode[]=car'
```
