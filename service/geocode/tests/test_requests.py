import json
import os
import unittest
import unittest.mock as mock
from urllib.parse import urlparse, parse_qs

from geocode import requests


def load_google_sample():
    fname = os.path.join(os.path.dirname(__file__), "sample.google.json")
    with open(fname, "rb") as fp:
        return fp.read()


def load_HERE_sample():
    fname = os.path.join(os.path.dirname(__file__), "sample.here.json")
    with open(fname, "rb") as fp:
        return fp.read()


class GoogleGeocodeServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = requests.GoogleGeocodeService()

    def test_prepare(self):
        url = self.service.prepare({"APP_KEY": "foo"},
                                   "1+Way+There+Some+Place")
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        self.assertEqual(qs, {"address": ["1+Way+There+Some+Place"],
                              "key": ["foo"]})
        result_url, rest = url.split("?", 1)
        self.assertEqual(result_url, self.service.url)

    def test_process_response_ok(self):
        data = load_google_sample().decode()
        result = self.service.process_response(data)
        self.assertEqual(result, {"lat": '37.4224082',
                                  "lng": '-122.0856086'})

        # Verify unexpected data is dropped
        result = self.service.process_response('{"results": [{"geometry": {"location": {"lat": 37.4224082, "lng": -122.0856086, "other": "extra"}}}] }')
        self.assertEqual(result, {"lat": '37.4224082',
                                  "lng": '-122.0856086'})

        # Location is not found. Not an error.
        self.assertEqual({}, self.service.process_response('{"results": [] }'))


    def test_process_response_fail(self):
        with self.assertRaises(requests.DataProcessingError):
            self.service.process_response('{"results": [{"geometry": {}}] }')

        with self.assertRaises(requests.DataProcessingError):
            self.service.process_response('{"results": [{"geometry": {"location": {}}}] }')

        with self.assertRaises(requests.DataProcessingError):
            self.service.process_response('{"results": [{"geometry": {"location": {"lat": 37.4224082}}}] }')

        with self.assertRaises(requests.DataProcessingError):
            self.service.process_response('{"results": [{"geometry": {"location": {"lng": -122.0856086}}}] }')


class HEREGeocodeServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = requests.HEREGeocodeService()

    def test_prepare(self):
        url = self.service.prepare({"APP_ID": "foo", "APP_CODE": "bar"},
                                   "1+Way+There+Some+Place")
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        self.assertEqual(qs, {"searchtext": ["1+Way+There+Some+Place"],
                              "app_id": ["foo"],
                              "app_code": ["bar"]})
        result_url, rest = url.split("?", 1)
        self.assertEqual(result_url, self.service.url)

    def test_process_response_ok(self):
        data = load_HERE_sample().decode()
        result = self.service.process_response(data)
        self.assertEqual(result, {"lat": '41.88449',
                                  "lng": '-87.6387699'})

        # Verify unexpected data is dropped
        result = self.service.process_response('{"Response": {"View": [{"Result": [{"Location": {"NavigationPosition": [{"Latitude": 37.4224082, "Longitude": -122.0856086, "other": "extra"}]}}] }]}}')
        self.assertEqual(result, {"lat": '37.4224082',
                                  "lng": '-122.0856086'})

        # Location not found. Not an error.
        self.assertEqual({}, self.service.process_response('{"Response": {"View": []} }'))

    def test_process_response_fail(self):
        with self.assertRaises(requests.DataProcessingError):
            self.service.process_response('{"Response": {} }')

        with self.assertRaises(requests.DataProcessingError):
            self.service.process_response('{"Response": {"View": [{"Result": []}]} }')

        with self.assertRaises(requests.DataProcessingError):
            self.service.process_response('{"Response": {"View": [{"Result": [{"Location": {}}]}]} }')

        with self.assertRaises(requests.DataProcessingError):
            self.service.process_response('{"Response": {"View": [{"Result": [{"Location": {"NavigationPosition": []}}]}]} }')

        with self.assertRaises(requests.DataProcessingError):
            self.service.process_response('{"Response": {"View": [{"Result": [{"Location": {"NavigationPosition": [{"Latitude": 123}]}}]}]} }')

        with self.assertRaises(requests.DataProcessingError):
            self.service.process_response('{"Response": {"View": [{"Result": [{"Location": {"NavigationPosition": [{"Longitude": -678}]}}]}]} }')


class GeocodeLookupTests(unittest.TestCase):
    def test_init(self):
        with self.assertRaises(requests.GeocodeLookup.ConfigError):
            requests.GeocodeLookup({}, {})

        with self.assertRaises(requests.GeocodeLookup.ConfigError):
            requests.GeocodeLookup({"services": []}, {})

        # Unknown services
        with self.assertRaises(requests.GeocodeLookup.ConfigError):
            requests.GeocodeLookup({"services": ["foo", "bar"]}, {})

        # Known but no credentials
        with self.assertRaises(requests.GeocodeLookup.ConfigError):
            requests.GeocodeLookup({"services": ["HERE", "google"]}, {})

        # Known but wrong credentials
        with self.assertRaises(requests.GeocodeLookup.ConfigError):
            requests.GeocodeLookup({"services": ["HERE", "google"]},
                                  {"HERE": {"user": "alice", "password": "bob"},
                                   "google": {"user": "alice", "password": "bob"}})

        obj = requests.GeocodeLookup({"services": ["HERE", "google"],
                                     "HERE": {"url": "https://geocoder.cit.api.here.com/6.2/geocode.json"}},
                                    {"HERE": {"APP_ID": "foo", "APP_CODE": "bar"},
                                     "google": {"APP_KEY": "thing1"}})
        self.assertEqual(obj._services["HERE"].url, "https://geocoder.cit.api.here.com/6.2/geocode.json")

    @mock.patch('urllib.request.urlopen')
    def test_request_success_google(self, urlopen):
        request = mock.MagicMock(code=200)
        request.read.return_value = load_google_sample()
        urlopen.return_value = request

        obj = requests.GeocodeLookup({"services": ["google"]},
                                    {"google": {"APP_KEY": "thing1"}})
        result = obj.request("1600+Amphitheatre+Parkway+Mountain+View+CA")
        self.assertEqual(result, {"location": {"lat": "37.4224082", "lng": "-122.0856086"},
                                  "served_by": "google"})

    @mock.patch('urllib.request.urlopen')
    def test_request_success_HERE(self, urlopen):
        request = mock.MagicMock(code=200)
        request.read.return_value = load_HERE_sample()
        urlopen.return_value = request

        obj = requests.GeocodeLookup({"services": ["HERE"]},
                                    {"HERE": {"APP_ID": "thing1",
                                                "APP_CODE": "thing2"}})
        result = obj.request("425+W+Randolph+Chicago")
        self.assertEqual(result, {"location": {"lat": "41.88449", "lng": "-87.6387699"},
                                  "served_by": "HERE"})

    @mock.patch('urllib.request.urlopen')
    def test_request_success_fallback(self, urlopen):
        fail_request = mock.MagicMock()
        fail_request.code = 404
        success_request = mock.MagicMock()
        success_request.read.return_value = load_HERE_sample()
        success_request.code = 200
        urlopen.side_effect = [fail_request, success_request]

        obj = requests.GeocodeLookup({"services": ["google", "HERE"]},
                                    {"google": {"APP_KEY": "foo"},
                                     "HERE": {"APP_ID": "thing1",
                                              "APP_CODE": "thing2"}})
        result = obj.request("425+W+Randolph+Chicago")
        self.assertEqual(result, {"location": {"lat": "41.88449", "lng": "-87.6387699"},
                                  "served_by": "HERE"})

    @mock.patch('urllib.request.urlopen')
    def test_request_success_not_found(self, urlopen):
        request = mock.MagicMock()
        request.read.return_value = b'{"Response": {"View": []} }'
        request.code = 200
        urlopen.return_value = request

        obj = requests.GeocodeLookup({"services": ["HERE"]},
                                     {"HERE": {"APP_ID": "thing1",
                                              "APP_CODE": "thing2"}})
        result = obj.request("This%20Old%20House")
        self.assertEqual(result, {})

    @mock.patch('urllib.request.urlopen')
    def test_request_failure(self, urlopen):
        request = mock.MagicMock(code=403)
        urlopen.return_value = request

        with self.assertRaises(requests.GeocodeLookup.Error):
            obj = requests.GeocodeLookup({"services": ["HERE"]},
                                        {"HERE": {"APP_ID": "thing1",
                                                  "APP_CODE": "thing2"}})
            result = obj.request("425+W+Randolph+Chicago")
            self.assertEqual(result, None)
