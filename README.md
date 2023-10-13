# ZvgPortal Scraper

This is Python-based code able to scrape data from https://www.zvg-portal.de/.

## Installation

Even though dependencies of this application are minimal, it is recommended to run it in a virtual environment:

```bash
$ cd /path/to/ZvgPortal/
$ git clone 'https://github.com/larsborn/ZvgPortalScraper.git' .
$ python3 -m venv .venv
$ source .venv/bin/activate
$ pip install -U pip
$ pip install -r requirements.txt
```

## Usage

Set the `PYTHONPATH` environment variable and then you can execute `app.py`:

```bash
$ export PYTHONPATH=/path/to/ZvgPortal/  # the directory _containing_ the "zvg_portal" directory

$ python zvg_portal/app.py --help
usage: app.py [-h] [--debug] 
              [--print-stats] [--print-entries]
              [--base-url BASE_URL] [--raw-data-directory RAW_DATA_DIRECTORY] [--user-agent USER_AGENT]
              [--nsqd-address NSQD_ADDRESS] [--nsqd-port NSQD_PORT]
              [--client-side-crt CLIENT_SIDE_CRT] [--client-side-key CLIENT_SIDE_KEY]

optional arguments:
  -h, --help            show this help message and exit
  --debug
  --print-stats
  --print-entries
  --base-url BASE_URL
  --nsqd-address NSQD_ADDRESS
  --nsqd-port NSQD_PORT
  --client-side-crt CLIENT_SIDE_CRT
  --client-side-key CLIENT_SIDE_KEY
  --raw-data-directory RAW_DATA_DIRECTORY
  --user-agent USER_AGENT

```

For example like so:

```bash
$ python zvg_portal/app.py --nsqd-address nsqd.example.com --nsqd-port 4151
```
