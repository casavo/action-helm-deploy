# Reintroduce `mode: uninstall` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore `mode: uninstall` support (removed in #15) so consumers still passing `mode: uninstall` in their preview-teardown workflows actually run `helm uninstall` instead of silently falling through to `helm upgrade --install`.

**Architecture:** Add a `mode` input (`upgrade` | `uninstall`, default `upgrade`) to `action.yml`. `action.py` gains a `helm_uninstall(specs)` function and `run()` dispatches on `specs["mode"]`, defaulting to the existing `helm_upgrade` path unchanged. Unknown modes exit 1 with a message (no silent fallback). `install`/`template` modes stay removed — out of scope, per #15's deliberate simplification.

**Tech Stack:** Python 3 (stdlib + PyYAML, already a dependency), GitHub Composite Action, pytest is NOT introduced — new tests use stdlib `unittest`/`unittest.mock` to match the "no new dependency" constraint, run via `python3 -m unittest`.

## Global Constraints

- Do not reintroduce `helm_install` or `helm_template` — only `upgrade` (existing, unchanged) and `uninstall` (new) are valid `mode` values.
- `helm uninstall` must be called with `--ignore-not-found --wait` (matches the workaround already in use at `casavo/listing-platform`).
- `mode` default must be `"upgrade"` so existing callers with no `mode` input keep today's exact behavior (this is what currently ships, so no consumer regresses).
- An unrecognized `mode` value must print an error and `sys.exit(1)` — never fall through to `helm_upgrade`.
- README must document the new `mode` input and the orphaned-TLS-secret caveat from the issue (informational only, no new flag).

---

### Task 1: Add `mode` input to `action.yml`

**Files:**
- Modify: `action.yml`

**Interfaces:**
- Produces: env var `GHINPUT_MODE` available to `action.py` (consumed by Task 2).

- [ ] **Step 1: Add the `mode` input definition**

In `action.yml`, insert this block right after the `values-files` input and before `dry-run`:

```yaml
  mode:
    description: "Helm command to execute: `upgrade` or `uninstall`. (default: upgrade)"
    required: false
    default: "upgrade"
```

- [ ] **Step 2: Export `GHINPUT_MODE` in the Deploy step**

In the `Deploy` step's `run:` block, add this line alongside the other `export GHINPUT_*` lines (keep alphabetical order, so directly after `export GHINPUT_HELM_VERSION`-equivalent position — in this file that's right after `GHINPUT_DRY_RUN` and before `GHINPUT_NAMESPACE`, matching existing alphabetical ordering):

```bash
        export GHINPUT_MODE="${{ inputs.mode }}"
```

- [ ] **Step 3: Verify YAML is well-formed**

Run: `python3 -c "import yaml; yaml.safe_load(open('action.yml'))"`
Expected: no output, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add action.yml
git commit -m "feat: add mode input to action.yml"
```

---

### Task 2: Add `helm_uninstall` and dispatch logic in `action.py`

**Files:**
- Modify: `action.py`
- Create: `tests/test_action.py`

**Interfaces:**
- Consumes: `run_helm(cmd, params=None, cwd=None, exit=True, **env)` (existing, unchanged signature).
- Produces: `helm_uninstall(specs)` — takes the same `specs` dict as `helm_upgrade`, calls `run_helm("uninstall", [...])`. `run()` reads `specs["mode"]` (default `"upgrade"` when falsy) and dispatches.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_action.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_action -v`
Expected: `AttributeError: module 'action' has no attribute 'helm_uninstall'` (or similar) — tests fail because `helm_uninstall` and the dispatch don't exist yet.

- [ ] **Step 3: Add `"mode"` to `load_inputs()`**

In `action.py`, in the `load_inputs()` key list, add `"mode"` in alphabetical order (between `"helm-version"` and `"namespace"`):

```python
def load_inputs():
    rv = {}
    for key in [
        "chart-version",
        "chart",
        "dry-run",
        "helm-version",
        "mode",
        "namespace",
        "release",
        "rollback-on-failure",
        "repo-name",
        "repo",
        "timeout",
        "values-files",
        "values",
    ]:
        rv[key] = os.environ.get(f"GHINPUT_{key.upper().replace('-', '_')}")
    return rv
```

- [ ] **Step 4: Add `helm_uninstall` and update `run()`**

Add this function right after `helm_upgrade` in `action.py`:

```python
def helm_uninstall(specs):
    run_helm(
        "uninstall",
        [
            specs["release"],
            "--namespace",
            specs["namespace"],
            "--ignore-not-found",
            "--wait",
        ],
    )
```

Replace the existing `run()` function with:

```python
def run():
    specs = load_inputs()
    mode = specs["mode"] or "upgrade"
    if mode == "upgrade":
        work_dir = Path(tempfile.mkdtemp()).resolve()
        helm_upgrade(work_dir, specs)
    elif mode == "uninstall":
        helm_uninstall(specs)
    else:
        print(f"Unknown `mode` specified: {mode}")
        sys.exit(1)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_action -v`
Expected: `OK` — all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add action.py tests/test_action.py
git commit -m "feat: reintroduce mode input with uninstall support"
```

---

### Task 3: Exercise `mode: uninstall` in the integration workflow

**Files:**
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: the `mode` input from Task 1, the `helm_uninstall` dispatch from Task 2.
- Produces: nothing consumed by later tasks — this is the last task.

- [ ] **Step 1: Add an uninstall step after the existing deploy step**

In `.github/workflows/test.yml`, append a new step to the `linux-self-hosted` job, right after the existing `uses: ./` deploy step:

```yaml
      - name: Uninstall
        uses: ./
        with:
          mode: uninstall
          release: test-self-hosted
          namespace: default
        env:
            KUBECONFIG: .kube_config.yml
```

- [ ] **Step 2: Verify YAML is well-formed**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))"`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/test.yml
git commit -m "test: exercise mode uninstall in CI integration workflow"
```

*(This step runs for real against the staging cluster once the PR is opened/updated — there is no local way to execute it before that, since it requires `self-hosted` runner + `KUBECONF_APPDEV_COMMON_STAGING` secret.)*

---

### Task 4: Document `mode` in README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing.

- [ ] **Step 1: Add a `mode` usage example and the TLS caveat**

Append this section at the end of `README.md`:

```markdown

## Uninstalling a release

Set `mode: uninstall` to run `helm uninstall` instead of `helm upgrade --install`:

```yaml
    - name: Uninstall
      uses: casavo/action-helm-deploy@v1
      with:
        mode: uninstall
        release: myapp
        namespace: default
      env:
        KUBECONFIG: .kube_config.yml
```

`mode` defaults to `upgrade`, so existing usages are unaffected.

> **Note:** `helm uninstall` removes the release's `Ingress`, and cert-manager will
> garbage-collect the associated `Certificate` (it's owned by the Ingress via
> ingress-shim). The TLS `Secret` is **not** owned by the Ingress, though, and will
> survive the uninstall unless cert-manager runs with `--enable-certificate-owner-ref`.
> If your chart provisions TLS via cert-manager, plan to clean up the leftover
> `Secret` separately (e.g. in the same workflow that calls `mode: uninstall`).
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: document mode input and TLS secret caveat"
```
