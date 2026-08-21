# Helm Deploy Action

Github Action to deploy Helm charts. This action installs Helm and deploy a Chart using the specified inputs.

## Usage

Here is an example on how to use this action with a local chart:

```yaml
name: Deploy
on:
  release:
    types: [ published ]

jobs:
  deployment:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v1
    - run: |
        echo "${{ secrets.KUBECFGDATA }}" | base64 -d > .kube_config.yml
    - name: Deploy
      uses: casavo/action-helm-deploy@v1
      with:
        release: myapp
        namespace: default
        chart: helm/chart
        values: |
          var: value
        values-files: |
          helm/values.yaml
          helm/values.production.yaml
      env:
        KUBECONFIG: .kube_config.yml
```

and with a remote chart:

```yaml
name: Deploy
on:
  release:
    types: [ published ]

jobs:
  deployment:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v1
    - run: |
        echo "${{ secrets.KUBECFGDATA }}" | base64 -d > .kube_config.yml
    - name: Deploy
      uses: casavo/action-helm-deploy@v1
      with:
        release: myapp
        namespace: default
        repo: https://charts.bitnami.com/bitnami
        chart: nginx
        chart-version: 11.1.2
        values: |
          var: value
        values-files: |
          helm/values.yaml
          helm/values.production.yaml
      env:
        KUBECONFIG: .kube_config.yml
```

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
