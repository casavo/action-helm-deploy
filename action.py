import os
import shlex
import signal
import subprocess
import sys
import tempfile

from functools import partial
from pathlib import Path

from yaml import safe_load_all as ymlload

HELM_PATH = f"{os.environ.get('HOME', '')}/.local/action-helm/bin"


def load_inputs():
    rv = {}
    for key in [
        "atomic",
        "chart-version",
        "chart",
        "dry-run",
        "helm-version",
        "mode",
        "namespace",
        "release",
        "repo-name",
        "repo",
        "timeout",
        "values-files",
        "values"
    ]:
        rv[key] = os.environ.get(f"GHINPUT_{key.upper().replace('-', '_')}")
    return rv


def load_values(wrkdir, specs):
    if not specs["values"]:
        return None
    dst = wrkdir / "values.yaml"
    try:
        ymlload(specs["values"])
    except Exception:
        print("Unable to parse `values`.")
        sys.exit(1)
    with (wrkdir / "values.yaml").open("w") as f:
        f.write(specs["values"])
    return str(dst)


def load_values_files(specs):
    if not specs["values-files"]:
        return []
    return list(filter(None, specs["values-files"].splitlines()))


def load_repo(specs):
    if specs["repo"]:
        run_helm(
            "repo add --force-update",
            [
                specs["repo-name"] or "charts",
                specs["repo"]
            ],
            exit=False
        )
        run_helm("repo update", exit=False)


def load_chart(specs):
    return specs["chart"] if (
        not specs["repo"] or (
            specs["repo"] and specs["repo-name"]
        )
    ) else f"charts/{specs['chart']}"


def kill_helm(proc):
    proc.send_signal(signal.SIGINT)


def run_helm(cmd, params=None, cwd=None, exit=True, **env):
    params = params or []
    helm_cmd = " ".join(["helm", cmd] + params)
    proc = subprocess.Popen(
        shlex.split(helm_cmd),
        shell=False,
        cwd=cwd,
        env={**dict(os.environ), **env, "PATH": HELM_PATH}
    )
    proc_sig = partial(kill_helm, proc)
    signal.signal(signal.SIGINT, proc_sig)
    signal.signal(signal.SIGTERM, proc_sig)
    proc.wait()
    if exit:
        sys.exit(proc.returncode)


def helm_install(wrkdir, specs):
    load_repo(specs)
    chart = load_chart(specs)
    values_target = load_values(wrkdir, specs)
    values_files = load_values_files(specs)
    params = [
        specs["release"],
        chart,
        "--namespace",
        specs["namespace"]
    ]
    if specs["atomic"] == "true":
        params.append("--atomic")
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
    run_helm("install", params)


def helm_upgrade(wrkdir, specs):
    load_repo(specs)
    chart = load_chart(specs)
    values_target = load_values(wrkdir, specs)
    values_files = load_values_files(specs)
    params = [
        specs["release"],
        chart,
        "--install",
        "--namespace",
        specs["namespace"]
    ]
    if specs["atomic"] == "true":
        params.append("--atomic")
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


def helm_template(wrkdir, specs):
    load_repo(specs)
    chart = load_chart(specs)
    values_target = load_values(wrkdir, specs)
    values_files = load_values_files(specs)
    params = [
        specs["release"],
        chart,
        "--namespace",
        specs["namespace"]
    ]
    for values_file in values_files:
        params.extend(["-f", values_file])
    if values_target:
        params.extend(["-f", values_target])
    if specs["chart-version"]:
        params.extend(["--version", specs["chart-version"]])
    run_helm("template", params)


def helm_uninstall(wrkdir, specs):
    run_helm(
        "uninstall",
        [
            specs["release"],
            "--namespace",
            specs["namespace"]
        ]
    )


def run():
    specs = load_inputs()
    cmd = {
        "install": helm_install,
        "upgrade": helm_upgrade,
        "uninstall": helm_uninstall,
        "template": helm_template
    }.get(specs["mode"])
    if not cmd:
        print("Unknown `mode` specified.")
        sys.exit(1)
    wrkdir = Path(tempfile.mkdtemp()).resolve()
    cmd(wrkdir, specs)


if __name__ == "__main__":
    run()
