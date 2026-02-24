# Copilot Instructions

## GitHub Workflows: Demo Deployment Pipeline

This repository uses a **simple demo deployment system** for PR testing via Juju K8s. A demo is **automatically deployed whenever a PR is opened, reopened, or updated**, and automatically cleaned up when the PR is closed.

### Architecture Overview

The demo system has three layers:

1. **Main Workflow** ([demo.yml](.github/workflows/demo.yml)): Orchestrates the entire pipeline
2. **Composite Actions** ([.github/actions/](.github/actions/)): Reusable building blocks for specific tasks
3. **External Services**: JAAS (Juju), GHCR (container registry), K8s cluster
4. **Terraform** ([terraform/demo/](terraform/demo/)): Project-defined demo topology (apps, relations, config)

**Data Flow**: PR event → Generate Demo ID → Build (rock + charm) → Deploy charm via Juju CLI → Write base Terraform config → Run `juju_imports.sh` → `terraform apply` → Post comment with link

### Key Workflows & Actions

#### [demo.yml](.github/workflows/demo.yml) - Main Entry Point
- **Trigger**: PR open/reopen/synchronize (deploy) + PR closed (cleanup via `demo-cleanup.yml`)
- **Concurrency**: Single demo per ref (cancels in-progress runs)
- **Jobs**:
  - `setup`: Generates unique `demo-id` (format: `{repo-name}-pr{number}`)
  - `build-rock`: Caches based on `rockcraft.yaml`, `app.py`, `requirements.txt` hash
  - `build-charm`: Caches based on `charm/**` directory hash
  - `deploy`: Pushes rock to GHCR, deploys charm via Juju CLI, writes `terraform/demo/_base.tf`, runs `terraform/demo/juju_imports.sh`, applies Terraform. Uploads state as `tfstate-{demo-id}` artifact (90-day retention).
  - `cleanup` (in `demo-cleanup.yml`): Downloads Terraform state artifact, writes `_base.tf`, runs `terraform destroy`, deletes GHCR image.

#### [deploy-demo action](.github/actions/deploy-demo/action.yml) - Core Deployment
Handles rock→OCI, charm→K8s with Juju CLI, then Terraform for relation management. Key steps:
- **Caching**: Separate caches for rock and charm to speed rebuilds
- **Image Push**: Uses `skopeo` with GHCR credentials
- **Juju CLI Deploy**: Authenticates with JAAS and deploys the local charm with the OCI image resource
- **Write `_base.tf`**: Generates `terraform/demo/_base.tf` with provider config, model data source, and `demo_id` variable
- **Run `juju_imports.sh`**: Executes `terraform/demo/juju_imports.sh` (if present) to import Juju apps into TF state. `DEMO_ID` and `MODEL_UUID` are available as env vars.
- **Terraform Apply**: Applies `terraform/demo/` to create relations and any other resources
- **State Upload**: Uploads `terraform/demo/terraform.tfstate` as artifact `tfstate-{demo-id}`

#### [demo-comment action](.github/actions/demo-comment/action.yml) - User Interface
Posts a single bot comment with demo link (marked with `<!-- demo_service -->` to avoid duplicates).

#### [cleanup-demo action](.github/actions/cleanup-demo/action.yml) - Teardown
Downloads the Terraform state artifact, writes `_base.tf`, runs `terraform destroy` (removes all resources in the state), then deletes the GHCR image.

### Project-Defined Demo Topology ([terraform/demo/](terraform/demo/))

Each project owns its demo infrastructure in `terraform/demo/`. The action generates `terraform/demo/_base.tf` at runtime (never committed); projects provide:

- **`terraform/demo/demo.tf`** (required): Terraform resources for the demo — applications, integrations, config. Can reference:
  - `var.demo_id` — unique demo ID (e.g. `my-repo-pr42`)
  - `data.juju_model.demos` — the shared Juju model

- **`terraform/demo/juju_imports.sh`** (required if `demo.tf` references any resources): Imports pre-existing and newly-deployed Juju apps into TF state before `terraform apply`. Env vars available: `DEMO_ID`, `MODEL_UUID`.

> **Note**: The Juju Terraform provider does not support deploying local charm files. The charm is deployed via `juju deploy` CLI then imported into Terraform state via `juju_imports.sh`.

#### Naming Convention
All per-demo Juju applications (beyond the main charm) **must be prefixed with `{demo-id}`** so they are identifiable in `juju status`:
- Main app: `my-repo-pr42` (the demo-id itself)
- Extra apps: `my-repo-pr42-db`, `my-repo-pr42-redis`, etc.

Use `"${var.demo_id}-db"` in `demo.tf` and `"${DEMO_ID}-db"` in `juju_imports.sh`.

#### Action-Generated Files
`terraform/demo/_base.tf` is written at runtime and must be in `.gitignore`. It contains:
- Juju provider (`juju/juju ~> 1.1.0`, controller: `jaas.ps7.canonical.com:443/k8s-jaas-ps7-jimm-jimm`)
- Model data source: owner `795798e4-922f-49c7-9169-004ffc17df90@serviceaccount`, name `k8s-webteam-demos-default`
- `variable "demo_id"` — set via `TF_VAR_demo_id` by the action
- **Provider auth**: `JUJU_CLIENT_ID` and `JUJU_CLIENT_SECRET` env vars (from `DEMOS_JUJU_CLIENT_ID`/`DEMOS_JUJU_CLIENT_SECRET` secrets)
- **Model UUID** (for imports): `40cad239-1fe9-497f-89a2-ce70ab3e33af`

### Critical Conventions

1. **Demo ID Format**: Always `{repository-name}-pr{number}` - used for Juju application name, GHCR image tag, and Terraform state artifact name
2. **Bot Comments**: Marked with `<!-- demo_service -->` HTML comment to prevent duplicate comments
3. **Caching Strategy**:
   - Rock cache key: hash of `rockcraft.yaml`, `app.py`, `requirements.txt`
   - Charm cache key: hash of entire `charm/` directory
   - Cache misses trigger rebuilds; ensure only these files change the cache key
4. **Secrets**: `DEMOS_JUJU_CLIENT_ID` and `DEMOS_JUJU_CLIENT_SECRET` needed for both Juju CLI and Terraform provider. `GITHUB_TOKEN` (automatic) for GHCR login and API calls.
5. **Juju Model**: `795798e4-922f-49c7-9169-004ffc17df90@serviceaccount/k8s-webteam-demos-default` (model UUID: `40cad239-1fe9-497f-89a2-ce70ab3e33af`) - changes require Juju infrastructure coordination and updates to the action's `_base.tf` template.

### Common Modifications

**Adding a build step**: Modify `deploy-demo` action's `runs.steps` and `demo.yml` `build-*` jobs together.

**Changing cache keys**: Update hash inputs in `cache` steps - mismatches between `demo.yml` and `deploy-demo` action will cause inconsistent caching.

**Adding inputs**: Actions expose `charm-root` and `charm-path` for flexibility. Remember to propagate inputs through all calling actions if changing.

**Adding a new Juju relation or app**: Add resources to `terraform/demo/demo.tf` and import them in `terraform/demo/juju_imports.sh`. They will be created on `terraform apply` during deploy and removed on `terraform destroy` during cleanup.

**Extending cleanup**: Add steps to `cleanup-demo` action (e.g., database cleanup) - runs on PR close for all closed demos.

### Debugging Tips

- **Cache misses**: If builds are slow, verify cache key files match actual build inputs (check `hashFiles()` outputs)
- **Juju auth failures**: Confirm `DEMOS_JUJU_CLIENT_ID` and `DEMOS_JUJU_CLIENT_SECRET` are set in GitHub secrets; test with `juju status` command
- **Image push failures**: Verify GHCR login succeeds before `skopeo` call; check image URL format (must be lowercase)
- **Terraform import fails**: Check that the Juju CLI deploy step succeeded first; verify import ID format is `{model-uuid}:{app-name}` (model UUID is `40cad239-1fe9-497f-89a2-ce70ab3e33af`)
- **Terraform state missing on cleanup**: The `tfstate-{demo-id}` artifact has a 90-day retention; if expired, manually remove the Juju application with `juju remove-application {demo-id} -m 795798e4-922f-49c7-9169-004ffc17df90@serviceaccount/k8s-webteam-demos-default --force`
- **Demo not deploying**: Check workflow ran on PR open/reopen/synchronize event; verify no errors in build-rock, build-charm jobs
