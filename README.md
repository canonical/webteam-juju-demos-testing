# Webteam demos testing

This repository contains a simple charm and workflow to test that webteam demos can be deployed via Juju and Terraform.

## How to adopt this in another project

The demo deployment system automatically deploys a PR preview whenever a PR is opened/updated, and cleans it up when the PR is closed. To adopt it in another project:

### 1. Copy the GitHub workflows and actions

Copy these files into your repository, preserving the directory structure:

```
.github/
  workflows/
    demo.yml
    demo-cleanup.yml
  actions/
    deploy-demo/action.yml
    cleanup-demo/action.yml
    demo-comment/action.yml
```

### 2. Create `terraform/demo/demo.tf`

Define your demo's Juju resources. The action generates a base config at runtime that exposes:
- `var.demo_id` — unique ID for this demo (e.g. `my-repo-pr42`)
- `data.juju_model.demos` — the shared Juju model

Example for a Flask app with Traefik ingress:

```hcl
resource "juju_application" "demo" {
  name       = var.demo_id
  model_uuid = data.juju_model.demos.uuid

  charm {
    name = "flask-app"  # replace with your charm name
  }
}

resource "juju_integration" "demo_traefik" {
  model_uuid = data.juju_model.demos.uuid

  application {
    name     = juju_application.demo.name
    endpoint = "ingress"
  }

  application {
    name     = "traefik"
    endpoint = "ingress"
  }
}
```

For demos that need additional services (e.g. a database), add more resources and name them using the demo ID prefix so they're identifiable in `juju status`:

```hcl
resource "juju_application" "db" {
  name       = "${var.demo_id}-db"
  model_uuid = data.juju_model.demos.uuid
  charm { name = "postgresql-k8s" }
}
```

### 3. Create `terraform/demo/juju_imports.sh`

This script imports Juju applications into Terraform state before `terraform apply` runs. The action provides `DEMO_ID` and `MODEL_UUID` as environment variables.

```bash
#!/bin/bash
# Import the charm deployed by the action via juju CLI
terraform -chdir=terraform/demo import juju_application.demo "${MODEL_UUID}:${DEMO_ID}"

# Import any additional apps you created above
# terraform -chdir=terraform/demo import juju_application.db "${MODEL_UUID}:${DEMO_ID}-db"
```

Make the script executable:
```bash
chmod +x terraform/demo/juju_imports.sh
```

### 4. Update `.gitignore`

Add the action-generated and runtime Terraform files:

```
terraform/demo/_base.tf
terraform/demo/.terraform/
terraform/demo/.terraform.lock.hcl
terraform/demo/terraform.tfstate
terraform/demo/terraform.tfstate.backup
```

### 5. Configure secrets

Add these secrets to your GitHub repository (`Settings → Secrets and variables → Actions`):

| Secret | Description |
|---|---|
| `DEMOS_JUJU_CLIENT_ID` | JAAS service account client ID |
| `DEMOS_JUJU_CLIENT_SECRET` | JAAS service account client secret |

`GITHUB_TOKEN` is provided automatically by GitHub Actions.

### How it works

1. On PR open/update: rock is built and pushed to GHCR, charm is deployed via `juju deploy`, then `juju_imports.sh` imports apps into Terraform state, and `terraform apply` wires up relations.
2. On PR close: `terraform destroy` tears down all resources, and the GHCR image is deleted.
3. Terraform state is persisted between deploy and cleanup as a GitHub Actions artifact (`tfstate-{demo-id}`, 90-day retention).

