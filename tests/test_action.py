import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import action


def make_specs(**overrides):
    specs = {
        "chart-version": None,
        "chart": "mychart",
        "dry-run": "false",
        "helm-version": "latest",
        "mode": None,
        "namespace": "default",
        "release": "myrelease",
        "rollback-on-failure": "true",
        "repo-name": None,
        "repo": None,
        "timeout": None,
        "values-files": None,
        "values": None,
    }
    specs.update(overrides)
    return specs


class TestHelmUninstall(unittest.TestCase):
    @patch("action.run_helm")
    def test_helm_uninstall_calls_run_helm_with_expected_params(self, mock_run_helm):
        specs = make_specs(mode="uninstall")
        action.helm_uninstall(specs)
        mock_run_helm.assert_called_once_with(
            "uninstall",
            ["myrelease", "--namespace", "default", "--ignore-not-found", "--wait"],
        )


class TestHelmUpgrade(unittest.TestCase):
    @patch("action.load_repo")
    @patch("action.run_helm")
    def test_helm_upgrade_missing_chart_exits_1(self, mock_run_helm, mock_load_repo):
        specs = make_specs(chart=None)
        with self.assertRaises(SystemExit) as ctx:
            action.helm_upgrade(None, specs)
        self.assertEqual(ctx.exception.code, 1)
        mock_load_repo.assert_not_called()
        mock_run_helm.assert_not_called()


class TestRunDispatch(unittest.TestCase):
    @patch("action.helm_upgrade")
    @patch("action.load_inputs")
    def test_default_mode_calls_helm_upgrade(self, mock_load_inputs, mock_helm_upgrade):
        mock_load_inputs.return_value = make_specs(mode=None)
        action.run()
        self.assertEqual(mock_helm_upgrade.call_count, 1)

    @patch("action.helm_upgrade")
    @patch("action.load_inputs")
    def test_mode_upgrade_calls_helm_upgrade(self, mock_load_inputs, mock_helm_upgrade):
        mock_load_inputs.return_value = make_specs(mode="upgrade")
        action.run()
        self.assertEqual(mock_helm_upgrade.call_count, 1)

    @patch("action.helm_uninstall")
    @patch("action.load_inputs")
    def test_mode_uninstall_calls_helm_uninstall(self, mock_load_inputs, mock_helm_uninstall):
        specs = make_specs(mode="uninstall")
        mock_load_inputs.return_value = specs
        action.run()
        mock_helm_uninstall.assert_called_once_with(specs)

    @patch("action.load_inputs")
    def test_unknown_mode_exits_1(self, mock_load_inputs):
        mock_load_inputs.return_value = make_specs(mode="bogus")
        with self.assertRaises(SystemExit) as ctx:
            action.run()
        self.assertEqual(ctx.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
