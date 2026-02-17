import os
import shlex
import signal
import subprocess
import sys
import tempfile
from functools import partial
from pathlib import Path

from yaml import safe_load_all

HELM_PATH = f"{os.environ.get('HOME', '')}/.local/action-helm/bin"


def run():
    specs = load_inputs()
    work_dir = Path(tempfile.mkdtemp()).resolve()
    helm_upgrade(work_dir, specs)


def load_inputs():
    rv = {}
    for key in [
        "chart-version",
        "chart",
        "dry-run",
        "helm-version",
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


def helm_upgrade(work_dir, specs):
    load_repo(specs)
    chart = load_chart(specs)
    values_target = load_values(work_dir, specs)
    values_files = load_values_files(specs)
    params = [specs["release"], chart, "--install", "--force-conflicts", "--namespace", specs["namespace"]]
    if specs["rollback-on-failure"] == "true":
        params.append("--rollback-on-failure")
    if specs["dry-run"] == "true":
        params.append("--dry-run")
    for values_file in values_files:
        params.extend(["-f", values_file])
    if values_target:
        params.extend(["-f", values_target])
    if specs["chart-version"]:
        params.extend(["--version", specs["chart-version"]])
    if specs["timeout"]:
        params.extend(["--timeout", specs["timeout"]])
    run_helm("upgrade", params)


def load_repo(specs):
    if specs["repo"]:
        run_helm(
            "repo add --force-update",
            [specs["repo-name"] or "charts", specs["repo"]],
            exit=False,
        )
        run_helm("repo update", exit=False)


def load_values(work_dir, specs):
    if not specs["values"]:
        return None
    dst = work_dir / "values.yaml"
    try:
        safe_load_all(specs["values"])
    except Exception:
        print("Unable to parse `values`.")
        sys.exit(1)
    with (work_dir / "values.yaml").open("w") as f:
        f.write(specs["values"])
    return str(dst)


def load_values_files(specs):
    if not specs["values-files"]:
        return []
    return list(filter(None, specs["values-files"].splitlines()))


def load_chart(specs):
    return (
        specs["chart"]
        if (not specs["repo"] or (specs["repo"] and specs["repo-name"]))
        else f"charts/{specs['chart']}"
    )


def run_helm(cmd, params=None, cwd=None, exit=True, **env):
    params = params or []
    helm_cmd = " ".join(["helm", cmd] + params)
    proc = subprocess.Popen(
        shlex.split(helm_cmd),
        shell=False,
        cwd=cwd,
        env={**dict(os.environ), **env, "PATH": HELM_PATH},
    )
    proc_sig = partial(kill_helm, proc)
    signal.signal(signal.SIGINT, proc_sig)
    signal.signal(signal.SIGTERM, proc_sig)
    proc.wait()
    if exit:
        sys.exit(proc.returncode)


def kill_helm(proc, signum, frame):
    proc.send_signal(signal.SIGINT)


if __name__ == "__main__":
    run()
