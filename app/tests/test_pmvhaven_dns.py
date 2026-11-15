"""PMV Haven name lookup when the system DNS has no address for the site."""
import socket
import unittest
from unittest import mock

from ae_sources import pmvhaven_dns as dns


class PublicDnsFallback(unittest.TestCase):
    def setUp(self):
        dns.install()
        dns._cache.clear()
        dns.take_notice()

    def test_only_this_site_is_looked_up_again(self):
        asked = []

        def system(host, port, *a, **k):
            raise socket.gaierror(11004, "getaddrinfo failed")

        def public(host):
            asked.append(host)
            return ["9.9.9.9"] if host.endswith("pmvhaven.com") else []

        with mock.patch.object(dns, "_system", system), mock.patch.object(dns, "_public", public):
            got = socket.getaddrinfo("cdn.pmvhaven.com", 443)
            self.assertEqual(got[0][4], ("9.9.9.9", 443))
            with self.assertRaises(socket.gaierror):
                socket.getaddrinfo("other.example", 80)
            socket.getaddrinfo("pmvhaven.com", "https")   # service name, not a port number
        self.assertEqual(asked, ["cdn.pmvhaven.com", "pmvhaven.com"])
        self.assertIn("public DNS", dns.take_notice())
        self.assertIsNone(dns.take_notice())

    def test_a_working_system_lookup_is_left_alone(self):
        sentinel = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("1.2.3.4", 443))]

        def system(host, port, *a, **k):
            return sentinel

        with mock.patch.object(dns, "_system", system), mock.patch.object(dns, "_public") as public:
            self.assertIs(socket.getaddrinfo("pmvhaven.com", 443), sentinel)
        public.assert_not_called()

    def test_empty_public_answer_still_fails(self):
        def system(host, port, *a, **k):
            raise socket.gaierror(11004, "getaddrinfo failed")

        with mock.patch.object(dns, "_system", system), mock.patch.object(dns, "_public", lambda host: []):
            with self.assertRaises(socket.gaierror):
                socket.getaddrinfo("pmvhaven.com", 443)
        self.assertIsNone(dns.take_notice())


if __name__ == "__main__":
    unittest.main()
