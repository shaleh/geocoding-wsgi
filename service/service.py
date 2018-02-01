#!/usr/bin/env python3

import argparse
import http
import json
import logging
import sys
import urllib.parse
from wsgiref.simple_server import make_server

from geocode.requests import GeocodeLookup

logger = logging.getLogger("")


class Response(object):
    """HTTP Response object."""
    def __init__(self, start):
        self._start = start
        self._status = None
        self._headers = None
        self._data = []

    def as_error(self, data, status):
        """Response is an HTTP error."""
        self._headers = [('Content-type', 'text/plain; charset=utf-8')]
        self._status = status
        self._data.append(data)

    def as_json(self, data):
        """Response is JSON data."""
        self._headers = [('Content-type', 'application/json; charset=utf-8')]
        self._status = http.HTTPStatus.OK
        self._data.append(data)

    def add_data(self, data):
        """Add data to the response."""
        self._data.append(data)

    def __call__(self, *args):
        # WSGI complains if Response is not callable. But I cannot
        # find docs for what it is supposed to do. I tried calling
        # `start_response` here but it was not invoked before the
        # iteration.
        pass

    def __iter__(self):
        """Iteration used during finalization of the response."""
        self._data.reverse()  # so pop works currently
        return self

    def __next__(self):
        """iterate over the data of the response."""
        if self._start:
            self._start("{:d} {}".format(self._status.value, self._status.name),
                        self._headers)
            self._start = None

        try:
            item = None
            while not item:
                item = self._data.pop()

            # WSGI requires bytes for the response data.
            if isinstance(item, bytes):
                return item
            else:
                # be lenient and make whatever it is a string.
                return bytes(str(item).encode())
        except IndexError:
            raise StopIteration


class Request(object):
    """HTTP Request object."""
    def __init__(self, app, response, env, method, path, qs):
        self._app = app
        self._response = response
        self._env = env
        self._method = method
        self._path = path
        self._qs = qs

    @property
    def app(self):
        return self._app

    @property
    def response(self):
        return self._response

    @property
    def env(self):
        return self._env

    @property
    def method(self):
        return self._method

    @property
    def path(self):
        self._path

    @property
    def query_string(self):
        return urllib.parse.parse_qs(self._qs)


class GeocodeApp(object):
    """WSGI App for the Geocode service.

    `lookup` is an object the can perform requests for a location string.
    """
    class LookupError(Exception):
        """Wraps underlying lookup exception."""
        # This allows the implementation of the Geocode module to be switched out.
        pass

    def __init__(self, lookup):
        self._routes = {}
        self._lookup = lookup

    def lookup(self, location):
        """Find `location` using the lookup object.

        Returns a dictionary containing the location coordinates.

        Raises LookupError if the request fails. However, if the
        location cannot be found this is not treated as a
        failure. Instead an empty response is returned.
        """
        try:
            return self._lookup.request(location)
        except self._lookup.Error as e:
            raise LookupError(str(e))

    def add_routes(self, new_routes):
        """Add new support URL routes."""
        self._routes.update(new_routes)

    def bad_request(self, response, request):
        response.as_error(request.path, status=http.HTTPStatus.BAD_REQUEST)
        return response

    def not_found(self, response, request):
        response.as_error(request.path, status=http.HTTPStatus.NOT_FOUND)
        return response

    def method_not_allowed(self, response, request):
        response.as_error("{} : {}".format(request.method, request.path_info),
                          status=http.HTTPStatus.METHOD_NOT_ALLOWED)
        return response

    def service_unavailable(self, response, request):
        response.as_error(request.path, status=http.HTTPStatus.SERVICE_UNAVAILABLE)
        return response

    def __call__(self, environ, start_response):
        """This is the heart of the WSGI app.

        Pulls the request information out of `environ`. Then the know
        routes are checked for a handler. if one is found it is
        executed. Otherwise `not_found` is called.

        Returns a `Response` object.
        """
        path_info = environ.get("PATH_INFO", "/")
        method = environ.get("REQUEST_METHOD", "GET")
        qs = environ.get("QUERY_STRING", "")
        response = Response(start_response)

        logger.debug("REQUEST_METHOD: %s", method)
        logger.debug("PATH_INFO: %s", path_info)
        logger.debug("QUERY_STRING: %s", qs)

        request = Request(self, response, environ, method, path_info, qs)
        handler = None
        try:
            # drop trailing /. It will interfere with finding the route.
            stripped = path_info.rstrip('/')
            handler = self._routes[stripped]
        except KeyError:
            return self.not_found(response, request)

        if method not in handler.supported_methods:
            return self.method_not_allowed(response, request)

        result = handler(request)
        return result


def handle_location(request):
    """Handle /location requests.

    Returns a JSON object containing the coordinates. If the location
    was not found then the response will be an empty object. Bad Request
    is returned if the WHERE parameter is not provided. If all services
    return something other than HTTP OK this function returns
    Service Unavailble.
    """
    response = request.response
    qs = request.query_string
    logger.debug("QS: %s", qs)
    app = request.app

    # this is the only parameter we need. Silently ignore the rest.
    if "where" not in qs or not qs["where"]:
        response.add_data(b"missing 'where' in query string")
        return app.bad_request(response, request)

    # Be flexible. Handle spaced input too.
    where = qs["where"][0].replace("%20", "+")

    try:
        result = app.lookup(where)
        js = {
            "response": result
        }
        response.as_json(json.dumps(js))
        return response
    except GeocodeApp.LookupError as e:
        logger.error("Failed during lookup: %s", e)
        return app.service_unavailble(response, request)
handle_location.supported_methods = ("GET",)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(description="Geocode WSGI server")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--credentials", default="credentials.json")
    parser.add_argument("--log-file", default="wsgi.log")
    parser.add_argument("--port", type=int, help="listening port. Defaults to 8000")
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args(argv)

    lh = logging.FileHandler(args.log_file)
    lh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    logger.addHandler(lh)
    if args.debug:
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    try:
        config = json.load(open(args.config))
        credentials = json.load(open(args.credentials))
    except OSError as e:
        raise SystemExit("Failed to read file: {}".format(e))
    except json.decoder.JSONDecodeError as e:
        raise SystemExit("Failed to parse file: {}".format(e))

    try:
        lookup = GeocodeLookup(config, credentials)
    except GeocodeLookup.ConfigError as e:
        logger.error("Failed to setup lookup object: %s", e)
        raise SystemExit(1)

    # Command line overrides config file
    if args.port:
        config["port"] = args.port
    elif "port" not in config:
        config["port"] = 8000

    # Should be loaded from config as well.
    # Using a routing table allows for more flexibility than introspecting
    # method names or decorators allows.
    routes = {
        "/location": handle_location,
    }
    app = GeocodeApp(lookup)
    app.add_routes(routes)

    try:
        httpd = make_server('', config.get("port"), app)
        print("Serving on port {}...".format(config["port"]))

        httpd.serve_forever()
    except PermissionError as e:
        logging.error("Failed to start service: %s", e)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
