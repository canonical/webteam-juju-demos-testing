# Copilot Instructions

## GitHub Workflows: Demo Deployment Pipeline

This repository uses a **simple demo deployment system** for PR testing via Juju K8s. A demo is **automatically deployed whenever a PR is opened, reopened, or updated**, and automatically cleaned up when the PR is closed.

### Architecture Overview

The demo system has three layers:

1. **Main Workflow** ([demo.yml](.github/workflows/demo.yml)): Orchestrates the entire pipeline
2. **Composite Actions** ([.github/actions/](.github/actions/)): Reusable building blocks for specific tasks
3. **External Services**: JAAS (Juju), GHCR (container registry), K8s cluster

**Data Flow**: PR event → Generate Demo ID → Build (rock + charm) → Deploy to Juju K8s → Post comment with link

### Key Workflows & Actions

#### [demo.yml](.github/workflows/demo.yml) - Main Entry Point
- **Trigger**: PR open/reopen/synchronize (deploy) + PR closed (cleanup)
- **Concurrency**: Single demo per ref (cancels in-progress runs)
- **Jobs**:
  - `setup`: Generates unique `demo-id` (format: `{repo-name}-pr{number}`)
  - `build-rock`: Caches based on `rockcraft.yaml`, `app.py`, `requirements.txt` hash
  - `build-charm`: Caches based on `charm/**` directory hash
  - `deploy`: Pushes rock to GHCR, deploys charm to Juju model `795798e4-922f-49c7-9169-004ffc17df90@serviceaccount/k8s-webteam-demos-default`
  - `cleanup`: Runs on PR closed, removes charm and GHCR image

#### [deploy-demo action](.github/actions/deploy-demo/action.yml) - Core Deployment
Handles rock→OCI, charm→K8s with Juju. Key steps:
- **Caching**: Separate caches for rock and charm to speed rebuilds
- **Image Push**: Uses `skopeo` with GHCR credentials
- **Juju Login**: JAAS authentication via `DEMOS_JUJU_CLIENT_ID` and `DEMOS_JUJU_CLIENT_SECRET`
- **Deployment**: Passes rock image URL as `flask-app-image` resource to charm

#### [demo-comment action](.github/actions/demo-comment/action.yml) - User Interface
Posts a single bot comment with demo link (marked with `<!-- demo_service -->` to avoid duplicates).

#### [cleanup-demo action](.github/actions/cleanup-demo/action.yml) - Teardown
Removes Juju charm deployment and deletes GHCR package version on PR close.

### Critical Conventions

1. **Demo ID Format**: Always `{repository-name}-pr{number}` - used for Juju resource naming and GHCR image tagging
2. **Bot Comments**: Marked with `<!-- demo_service -->` HTML comment to prevent duplicate comments
3. **Caching Strategy**: 
   - Rock cache key: hash of `rockcraft.yaml`, `app.py`, `requirements.txt`
   - Charm cache key: hash of entire `charm/` directory
   - Cache misses trigger rebuilds; ensure only these files change the cache key
4. **Secrets**: `DEMOS_JUJU_CLIENT_ID` and `DEMOS_JUJU_CLIENT_SECRET` needed for JAAS. `GITHUB_TOKEN` (automatic) for GHCR login and API calls
5. **Juju Model ID**: Hardcoded to `795798e4-922f-49c7-9169-004ffc17df90@serviceaccount/k8s-webteam-demos-default` - changes require Juju infrastructure coordination

### Common Modifications

**Adding a build step**: Modify `deploy-demo` action's `runs.steps` and `demo.yml` `build-*` jobs together.

**Changing cache keys**: Update hash inputs in `cache` steps - mismatches between `demo.yml` and `deploy-demo` action will cause inconsistent caching.

**Adding inputs**: Actions expose `charm-root` and `charm-path` for flexibility. Remember to propagate inputs through all calling actions if changing.

**Extending cleanup**: Add steps to `cleanup-demo` action (e.g., database cleanup) - runs on PR close for all closed demos.

### Debugging Tips

- **Cache misses**: If builds are slow, verify cache key files match actual build inputs (check `hashFiles()` outputs)
- **Juju auth failures**: Confirm `DEMOS_JUJU_CLIENT_ID` and `DEMOS_JUJU_CLIENT_SECRET` are set in GitHub secrets; test with `juju status` command
- **Image push failures**: Verify GHCR login succeeds before `skopeo` call; check image URL format (must be lowercase)
- **Demo not deploying**: Check workflow ran on PR open/reopen/synchronize event; verify no errors in build-rock, build-charm jobs
