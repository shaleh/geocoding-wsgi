## Geocoding Service as a WSGI app in Python

This is a simple WSGI app which contacts Geocoding services on be
chalf of the user. To run the service you can either run `setup.init`
from within the `service/` directory or you can install the package
using pip.

From service directory:

    $ cd service
    $ # Sample config is in this directory
    $ ./service.init --config ./config.json \
                     --credentials ./credentials.json
    $ # In another shell. 8001 is specified in the service/config.json
    $ # otherwise 8000 is used.
    $ http http://localhost:8001/location?where=1600+Pennsylvania+Ave+Washingon+DC

Using virtualenv:

    $ virtualenv sandbox
    $ source sandbox/bin/activate
    $ cd sandbox  # ensures the correct python modules are used
    $ pip install /path/to/checkout
    $ # Sample config is in the service directory
    $ bin/geocode_service.py --config /path/to/config.json \
                             --credentials /path/to/credentials.json
    $ # In another shell. 8001 is specified in the service/config.json
    $ # otherwise 8000 is used.
    $ http http://localhost:8001/location?where=Palace%20of%20Fine%20Arts

A log file is placed in the directory in which you start the
service. This can of course be changed by the command line or
configuration file.

## CLI

You can use a tool like `httpie` or `curl` to make request as shown
above. Or you can use the `requests` module of `geocode` as a CLI
directly.

    $ geocode/requests.py service/config.json \
                          service/credentials.json \
                          This Old House

After the config and credentials everything else provided is joined
into the location request.

The output is JSON to allow it to be used in a pipeline with say `jq`.

## Geocoding module

The `geocode` module is the driver of the system. Each supported
service is represented by a Python class. These services are called by
`GeocodeLookup` based on configuration provided when the object is
created. This configuration consists of the list of services in the
order that you prefer them to be called and a dictionary containing
the credential information needed to call each service.

The lookup object has only one main method and that is `request`. This
method takes the location to search for and returns a dictionary
containing the results. If the location is not found an empty
dictionary is returned. If all of the services fail then `Error` is
raised.

### Service classes

Each service class is expected to supply the following items.

`required_credentials` representing whatever is needed to call the
external service such as an API key.

`prepare` method which returns a URL to satisfy the request.

`process_response` method which parses the response data and returns a
dictionary containing the latitude and longitude as
`{ "lat": "123", "lng": "456" }`.

`update_url` method so the user can adjust the externally called URL
as needed.
