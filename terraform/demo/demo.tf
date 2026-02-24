# This application is deployed via juju CLI (local charm) and imported into
# Terraform state via juju_imports.sh so that Terraform can manage its lifecycle.
resource "juju_application" "demo" {
  name       = var.demo_id
  model_uuid = data.juju_model.demos.uuid

  charm {
    name = "flask-app"
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
