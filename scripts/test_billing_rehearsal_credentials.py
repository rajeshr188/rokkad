import unittest

from scripts.billing_rehearsal_credentials import validate_rehearsal


class BillingRehearsalBoundaryTests(unittest.TestCase):
    def test_accepts_only_dedicated_local_test_runtime(self):
        validate_rehearsal("rokkad_baseline_rehearsal_billing_fixture", "127.0.0.1",
                           {"key_id": "rzp_test_fixture", "key_secret": "fixture"})

    def test_rejects_other_databases_remote_hosts_and_live_or_missing_keys(self):
        valid = ("rokkad_baseline_rehearsal_billing_fixture", "127.0.0.1",
                 {"key_id": "rzp_test_fixture", "key_secret": "fixture"})
        for index, value in ((0, "rokkad_shared_dev"), (0, "rokkad_baseline_rehearsal_fixture"),
                             (0, "rokkad_baseline_rehearsal_billing_"), (1, "db.example.com"),
                             (2, {"key_id": "rzp_live_fixture", "key_secret": "fixture"}),
                             (2, {"key_id": "rzp_test_fixture", "key_secret": ""})):
            with self.subTest(index=index, value=value):
                args = list(valid)
                args[index] = value
                with self.assertRaises(RuntimeError):
                    validate_rehearsal(*args)


if __name__ == "__main__":
    unittest.main()
