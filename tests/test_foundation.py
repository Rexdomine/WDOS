import json
import os
import subprocess
import sys
import time
import unittest
import urllib.error
import urllib.request


class FoundationHealthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.port = "8766"
        cls.proc = subprocess.Popen(
            [sys.executable, "app.py"],
            env={**os.environ, "PORT": cls.port, "WDOS_ENVIRONMENT": "test"},
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for _ in range(30):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{cls.port}/health", timeout=0.2)
                return
            except Exception:
                time.sleep(0.1)
        raise RuntimeError("health server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)

    def test_health_route(self):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/health") as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(json.load(response)["status"], "ok")

    def test_unknown_route_is_bounded(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/missing")
        self.assertEqual(error.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
