"""Run with: python -m unittest discover -s browser-toolset/python -p 'test_*.py'."""

import subprocess
import unittest
from unittest.mock import Mock, call, patch

from cdp_browser import CdpBrowser


class CdpBrowserCloseTests(unittest.TestCase):
    def test_close_waits_for_process_before_removing_profile(self):
        for times_out in (False, True):
            with self.subTest(times_out=times_out):
                with (
                    patch.object(CdpBrowser, "_launch", return_value="ws://unused"),
                    patch.object(CdpBrowser, "_connect"),
                    patch("cdp_browser.shutil.rmtree") as remove_profile,
                ):
                    browser = CdpBrowser()
                    process = Mock()
                    if times_out:
                        process.wait.side_effect = [
                            subprocess.TimeoutExpired("chromium", 5),
                            0,
                        ]
                    browser._process = process
                    browser._profile_dir = "test-profile"
                    cleanup = Mock()
                    cleanup.attach_mock(process, "process")
                    cleanup.attach_mock(remove_profile, "remove_profile")

                    browser.close()

                    expected = [call.process.terminate(), call.process.wait(timeout=5)]
                    if times_out:
                        expected.extend([call.process.kill(), call.process.wait()])
                    expected.append(
                        call.remove_profile("test-profile", ignore_errors=True)
                    )
                    self.assertEqual(cleanup.mock_calls, expected)
                    self.assertIsNone(browser._process)
                    self.assertIsNone(browser._profile_dir)

                    browser.close()
                    self.assertEqual(cleanup.mock_calls, expected)


if __name__ == "__main__":
    unittest.main()
