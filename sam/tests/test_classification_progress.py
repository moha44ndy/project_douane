"""Tests du reporter de progression classification."""

from __future__ import annotations

import unittest

from sam.classification_progress import ClassificationProgressReporter


class TestClassificationProgressReporter(unittest.TestCase):
    def test_emits_step_updates(self) -> None:
        events: list[dict] = []
        reporter = ClassificationProgressReporter(emit=events.append)
        reporter.start("merchandise")
        reporter.complete("merchandise")
        reporter.start("identification")
        reporter.complete("identification")

        self.assertEqual(len(events), 4)
        self.assertEqual(events[0]["type"], "step")
        self.assertEqual(events[0]["step"], "merchandise")
        self.assertEqual(events[0]["status"], "active")
        self.assertEqual(events[1]["status"], "done")


if __name__ == "__main__":
    unittest.main()
