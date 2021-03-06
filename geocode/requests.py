#!/usr/bin/env python3

from collections import OrderedDict
import json
import logging
from urllib.parse import urlencode
import urllib.request as request


logger = logging.getLogger("")


class DataProcessingError(Exception):
    """Raised for failure to parse REST response data.

    Args:
        msg: The data that failed to be processed.
    """
    pass


class GoogleGeocodeService(object):
    """Google Geocode Service implementation."""
    url = "https://maps.googleapis.com/maps/api/geocode/json"
    required_credentials = ("APP_KEY", )

    def prepare(self, credentials, location):
        """Return the URL for this request."""
        params = {"address": location,
                  "key": credentials["APP_KEY"]}
        return "?".join((self.url, urlencode(params)))

    def process_response(self, data):
        """Process the response.

        Returns the latitude and longitude as a dict with keys 'lat'
        and 'lng'.

        Raises `DataProcessingError` on error.
        """
        try:
            js = json.loads(data, parse_float=str)
            results = js['results']
            if not results:
                return {}
            location = results[0]['geometry']['location']
            return {"lat": location['lat'], "lng": location['lng']}
        except (json.decoder.JSONDecodeError, IndexError, KeyError, TypeError):
            raise DataProcessingError(data)

    def update_url(self, new_url):
        """Change the default URL."""
        self.url = new_url


class HEREGeocodeService(object):
    """HERE Geocode Service implementation."""
    url = "https://geocoder.api.here.com/6.2/geocode.json"
    required_credentials = ("APP_ID", "APP_CODE")

    def prepare(self, credentials, location):
        """Return the URL for this request."""
        params = {"searchtext": location,
                  "app_id": credentials["APP_ID"],
                  "app_code": credentials["APP_CODE"]}
        return "{}?{}".format(self.url, urlencode(params))

    def process_response(self, data):
        """Process the response.

        Returns the latitude and longitude as a dict with keys 'lat'
        and 'lng'.

        Raises `DataProcessingError` on error.
        """
        try:
            data = json.loads(data, parse_float=str)
            view = data['Response']['View']
            if not view:
                return {}
            # The choice of NavigationPosition over DisplayPosition is an arbitrary one.
            location = view[0]['Result'][0]['Location']['NavigationPosition'][0]
            return {'lat': location['Latitude'], 'lng': location['Longitude']}
        except (json.decoder.JSONDecodeError, IndexError, KeyError, TypeError):
            raise DataProcessingError(data)

    def update_url(self, new_url):
        """Change the default URL."""
        self.url = new_url


class GeocodeLookup(object):
    """Lookup geo location via services."""
    # Yes, we could use introspection to generate this list.
    known_services = {
        "google": GoogleGeocodeService,
        "HERE": HEREGeocodeService,
    }

    class Error(Exception):
        """Represents a failure during execution."""
        pass

    class ConfigError(Exception):
        """Represents an error in the configuration."""
        pass

    def __init__(self, config, credentials):
        self._services = OrderedDict()

        if "services" not in config:
            raise GeocodeLookup.ConfigError("no services defined")

        for name in config["services"]:
            if name not in self.known_services:
                raise GeocodeLookup.ConfigError("unknown service: {}".format(name))
            elif name not in credentials:
                raise GeocodeLookup.ConfigError("{} is not in credentials file".format(name))
            service = self.known_services[name]
            for item in service.required_credentials:
                if item not in credentials[name]:
                    raise GeocodeLookup.ConfigError("{} service requires {} credential.".format(name, item))
            self._services[name] = service()
            url = config.get(name, {}).get("url", None)
            if url is not None:
                self._services[name].update_url(url)
        if not self._services:
            raise GeocodeLookup.ConfigError("no services provided")

        self._credentials = credentials

    def request(self, location):
        """Perform the HTTP request for the `location` data.

        Returns a dict containing Latitude and Logitude as 'lat' and 'lng' keys.
        Raises GeocodeLookup.Error if no service succeeds.
        """
        location = location.replace(" ", "+")

        missing = False  # is the location not in the services or where there errors

        for name, service in self._services.items():
            outbound = service.prepare(self._credentials[name], location)
            response = request.urlopen(outbound)
            if response.code == 200:
                try:
                    result = service.process_response(response.read().decode())
                    if result:
                        return {"location": result, "served_by": name}
                    missing = True
                except UnicodeError:
                    logger.error("Failed to parse input as UTF8")
                except DataProcessingError as e:
                    logger.info("Failed to read from %s: %s", name, e)
            else:
                logger.info("Request to %s did not succeed. %s".format(name, response.code))

        if missing:
            return {}

        raise GeocodeLookup.Error("All services exhausted!")


def main(argv):
    try:
        config = json.load(open(argv[0]))
        credentials = json.load(open(argv[1]))
    except OSError as e:
        print("Failed to read file:", e)
    except json.decoder.JSONDecodeError as e:
        print("Failed to parse file:", e)

    try:
        lookup = GeocodeLookup(config, credentials)
    except GeocodeLookup.ConfigError as e:
        print("Failed to setup lookup object:", e)

    try:
        result = lookup.request(" ".join(argv[2:]))
        print(json.dumps(result))
    except GeocodeLookup.Error as e:
        print("Failed to retrieve data:", e)


if __name__ == '__main__':
    import sys
    main(sys.argv[1:])
