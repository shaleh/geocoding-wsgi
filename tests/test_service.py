import http
import json
import unittest
import unittest.mock as mock

from .context import requests
from .context import service


def dummy_handler(request):
    response = request.response
    response.as_json(json.dumps({"foo": 1}))
    return response
dummy_handler.supported_methods = ("POST", )


class GeocodeAppTest(unittest.TestCase):
    def test_missing_route(self):
        app = service.GeocodeApp(mock.MagicMock())
        response = app({"PATH_INFO": "/foo"}, mock.MagicMock())
        self.assertEqual(http.HTTPStatus.NOT_FOUND, response._status)
        self.assertEqual([("Content-type", "text/plain; charset=utf-8")],
                         response._headers)

    def test_incorrect_request_method(self):
        app = service.GeocodeApp(mock.MagicMock())
        app.add_routes({"/dummy": dummy_handler})

        response = app({"PATH_INFO": "/dummy"}, mock.MagicMock())
        self.assertEqual(http.HTTPStatus.METHOD_NOT_ALLOWED, response._status)
        self.assertEqual([("Content-type", "text/plain; charset=utf-8")],
                         response._headers)

        response = app({"PATH_INFO": "/dummy", "REQUEST_METHOD": "HEAD"}, mock.MagicMock())
        self.assertEqual(http.HTTPStatus.METHOD_NOT_ALLOWED, response._status)
        self.assertEqual([("Content-type", "text/plain; charset=utf-8")],
                         response._headers)

    def test_valid_method(self):
        app = service.GeocodeApp(mock.MagicMock())
        app.add_routes({"/dummy": dummy_handler})

        response = app({"PATH_INFO": "/dummy", "REQUEST_METHOD": "POST"}, mock.MagicMock())
        # should be CREATED but we do not need that support yet
        self.assertEqual(http.HTTPStatus.OK, response._status)
        self.assertEqual([('Content-type', 'application/json; charset=utf-8')],
                         response._headers)
        self.assertEqual([json.dumps({"foo": 1}).encode()], list(response))


class HandleLocationTest(unittest.TestCase):
    def test_success(self):
        data = {"location": {"lat": "111", "lng": "222"},
                "served_by": "mock code"}
        request = service.Request(mock.MagicMock(), service.Response(mock.MagicMock()),
                                  mock.MagicMock(), mock.MagicMock(), mock.MagicMock(),
                                  "where=This+Old+House")
        request.app.lookup.return_value = data

        response = service.handle_location(request)
        self.assertEqual(http.HTTPStatus.OK, response._status)
        self.assertEqual([('Content-type', 'application/json; charset=utf-8')],
                         response._headers)
        self.assertEqual([json.dumps({"response": data}).encode()], list(response))

    def test_success_empty(self):
        data = {}
        request = service.Request(mock.MagicMock(), service.Response(mock.MagicMock()),
                                  mock.MagicMock(), mock.MagicMock(), mock.MagicMock(),
                                  "where=This+Old+House")
        request.app.lookup.return_value = data

        response = service.handle_location(request)
        self.assertEqual(http.HTTPStatus.OK, response._status)
        self.assertEqual([("Content-type", "application/json; charset=utf-8")],
                         response._headers)
        self.assertEqual([json.dumps({"response": data}).encode()], list(response))

    def test_failure(self):
        lookup = mock.MagicMock()
        lookup.__class__.Error = requests.GeocodeLookup.Error
        request = service.Request(service.GeocodeApp(lookup), service.Response(mock.MagicMock()),
                                  mock.MagicMock(), mock.MagicMock(), mock.MagicMock(),
                                  "where=This+Old+House")
        lookup.request.side_effect = requests.GeocodeLookup.Error("all fail!")

        response = service.handle_location(request)
        self.assertEqual(http.HTTPStatus.SERVICE_UNAVAILABLE, response._status)
        self.assertEqual([("Content-type", "text/plain; charset=utf-8")],
                         response._headers)

    def test_poor_input(self):
        request = mock.MagicMock()
        request.app = service.GeocodeApp(mock.MagicMock())
        request.query_string = {"blah": 1}
        request.response = service.Response(mock.MagicMock())

        response = service.handle_location(request)
        self.assertEqual(http.HTTPStatus.BAD_REQUEST, response._status)
        self.assertEqual([("Content-type", "text/plain; charset=utf-8")],
                         response._headers)
