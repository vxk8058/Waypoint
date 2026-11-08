import json
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

from server import Handler


class ServerTest(unittest.TestCase):
    def test_routes(self):
        with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
            thread = Thread(target=server.serve_forever)
            thread.start()
            client = HTTPConnection(*server.server_address, timeout=2)
            try:
                client.request("GET", "/")
                response = client.getresponse()
                self.assertEqual(response.status, 200)
                self.assertEqual(response.getheader("Content-Type"), "application/json")
                self.assertEqual(json.loads(response.read()), {"status": "ok"})

                client.request("GET", "/missing")
                self.assertEqual(client.getresponse().status, 404)
            finally:
                client.close()
                server.shutdown()
                thread.join()
