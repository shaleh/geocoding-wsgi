import json
import os
import unittest
from urllib.parse import urlparse, parse_qs

from geocode import geocode


class GoogleGeocodeServiceTest(unittest.TestCase):
    def setUp(self):
        self.service = geocode.GoogleGeocodeService()

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
        json_file = os.path.join(os.path.dirname(__file__), "sample.google.json")
        with open(json_file, "rb") as fp:
            data = fp.read().decode()
            result = self.service.process_response(data)
            self.assertEqual(result, {"lat": '37.4224082',
                                      "lng": '-122.0856086'})

        # Verify unexpected data is dropped
        result = self.service.process_response('{"results": [{"geometry": {"location": {"lat": 37.4224082, "lng": -122.0856086, "other": "extra"}}}] }')
        self.assertEqual(result, {"lat": '37.4224082',
                                  "lng": '-122.0856086'})

    def test_process_response_fail(self):
        with self.assertRaises(geocode.DataProcessingError):
            self.service.process_response('{"results": [] }')

        with self.assertRaises(geocode.DataProcessingError):
            self.service.process_response('{"results": [{"geometry": {}}] }')

        with self.assertRaises(geocode.DataProcessingError):
            self.service.process_response('{"results": [{"geometry": {"location": {}}}] }')

        with self.assertRaises(geocode.DataProcessingError):
            self.service.process_response('{"results": [{"geometry": {"location": {"lat": 37.4224082}}}] }')

        with self.assertRaises(geocode.DataProcessingError):
            self.service.process_response('{"results": [{"geometry": {"location": {"lng": -122.0856086}}}] }')
