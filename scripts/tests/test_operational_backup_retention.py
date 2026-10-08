"""Destructive retention boundaries, using fictional temporary backups only."""
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "retention", Path(__file__).resolve().parents[1] / "retain_operational_backups.py")
retention = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retention)


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.now = datetime(2026, 10, 8, 12, tzinfo=timezone.utc)

    def copy(self, stamp):
        path = self.folder / ("production-" + stamp.strftime("%Y%m%dT%H%M%SZ") + ".dump")
        path.write_bytes(b"PGDMP fictional " + path.name.encode())
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        path.with_suffix(".dump.sha256").write_text(digest + "  " + path.name + "\n")
        (self.folder / "latest.json").write_text(json.dumps(dict(
            file=str(path), sha256=digest, size_bytes=path.stat().st_size,
            archive_catalog_checked=True)))
        return path

    def plan(self, callback=lambda path: None):
        return retention.plan_retention(self.folder, self.now, callback)

    def history(self):
        for hours in range(35 * 24, -1, -1):
            self.copy(self.now - timedelta(hours=hours))

    def test_hourly_daily_union_and_date_cutoff(self):
        self.history()
        plan = self.plan()
        self.assertTrue(set(plan["copies"][-24:]) <= plan["retained"])
        for day in range(30):
            date = self.now.date() - timedelta(days=day)
            newest = max(p for p in plan["copies"] if p.name[11:19] == date.strftime("%Y%m%d"))
            self.assertIn(newest, plan["retained"])
        self.assertLessEqual(len(plan["retained"]), 54)
        self.assertNotIn(plan["copies"][0], plan["retained"])

    def test_apply_is_repeatable_and_preserves_checkpoints_partial_and_latest(self):
        self.history()
        protected = [self.folder / name for name in ("release.dump", "production-20261008T115500Z.partial")]
        for p in protected:
            p.write_bytes(b"protected")
        latest = (self.folder / "latest.json").read_bytes()
        plan = self.plan()
        retention.apply_plan(self.folder, plan)
        self.assertTrue(all(p.read_bytes() == b"protected" for p in protected))
        self.assertEqual((self.folder / "latest.json").read_bytes(), latest)
        self.assertEqual(self.plan()["removed"], [])

    def test_checksum_failure_preserves_all_copies(self):
        self.history()
        paths = sorted(self.folder.glob("*.dump"))
        paths[-2].write_bytes(b"damaged")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.plan()
        self.assertTrue(all(p.exists() for p in paths))

    def test_catalogue_failure_preserves_all_copies(self):
        self.history()
        before = set(self.folder.iterdir())
        def fail(path):
            raise ValueError("catalogue failed")
        with self.assertRaisesRegex(ValueError, "catalogue"):
            self.plan(fail)
        self.assertEqual(set(self.folder.iterdir()), before)

    def test_changed_file_refuses_deletion_before_first_unlink(self):
        self.history()
        plan = self.plan()
        plan["copies"][0].write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "changed"):
            retention.apply_plan(self.folder, plan)
        self.assertTrue(all(p.exists() for p in plan["copies"]))

    def test_missing_sidecar_refuses_expiry(self):
        self.copy(self.now)
        next(self.folder.glob("*.sha256")).unlink()
        with self.assertRaises(FileNotFoundError):
            self.plan()

    def test_stale_latest_refuses_expiry(self):
        path = self.copy(self.now - timedelta(hours=3))
        with self.assertRaisesRegex(ValueError, "Fresh"):
            self.plan()
        self.assertTrue(path.exists())

    def test_latest_metadata_mismatch_refuses_expiry(self):
        self.copy(self.now)
        metadata = self.folder / "latest.json"
        data = json.loads(metadata.read_text())
        data["sha256"] = "0" * 64
        metadata.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.plan()

    def test_symlink_cannot_target_an_outside_backup(self):
        external = tempfile.TemporaryDirectory()
        self.addCleanup(external.cleanup)
        outside = Path(external.name) / "protected-real-copy"
        outside.write_bytes(b"do not delete")
        link = self.folder / "production-20261008T120000Z.dump"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("Windows symlink privilege unavailable; also run on Linux")
        with self.assertRaisesRegex(ValueError, "path"):
            self.plan()
        self.assertEqual(outside.read_bytes(), b"do not delete")


if __name__ == "__main__":
    unittest.main()
