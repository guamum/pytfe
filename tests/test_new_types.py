import textwrap
import pytfe

from pytfe import block
from pytfe import Plan


def test_item():
    item = block("provider")
    assert item.type == "provider"
    assert item.args == ()
    assert item.kwds == {}
    assert item.items == ()
    assert item.format() == pytfe.TFBlock("""
    provider {
    }""")

    item = block("provider", "docker")
    assert item.type == "provider"
    assert item.args == ("docker",)
    assert item.kwds == {}
    assert item.items == ()
    assert item.format() == 'provider "docker" {\n}'

    item = block("provider", "docker", host='"unix:///var/run/docker.sock"')
    assert item.type == "provider"
    assert item.args == ("docker",)
    assert item.kwds == {"host": '"unix:///var/run/docker.sock"'}
    assert item.items == ()
    assert item.format() == pytfe.TFBlock("""
    provider "docker" {
      host = "unix:///var/run/docker.sock"
    }""")

    backend_item = block(
        "backend", "consul",
        address='"demo.consul.io"',
        scheme='"https"',
        path='"example_app/terraform_state"'
    )
    item = block(
        "terraform",
        backend_item,
        required_version='">= 0.13"',
    )
    assert item.type == "terraform"
    assert item.args == ()
    assert item.kwds == {"required_version": '">= 0.13"'}
    assert item.items == (backend_item,)
    assert item.format() == pytfe.TFBlock("""
    terraform {
      backend "consul" {
        address = "demo.consul.io"
        scheme = "https"
        path = "example_app/terraform_state"
      }
      required_version = ">= 0.13"
    }""")


def test_plan():
    plan = Plan()
    assert plan.items == []
    assert plan.modules == []
    assert plan.format() == ""

    plan = Plan()
    provider = block("provider", "docker", host='"unix:///var/run/docker.sock"')
    resource = block("resource", "docker_container", "foo",
                     image='"redis:latest"', name='"foo"')
    module = block("module", "module_a", source='"./module_a"')

    plan += provider
    assert plan.items == [provider]
    assert plan.modules == []

    plan += resource
    assert plan.items == [provider, resource]
    assert plan.modules == []

    plan += module
    assert plan.items == [provider, resource, module]
    assert plan.modules == [module]

    assert plan.format() == pytfe.TFBlock("""
    provider "docker" {
      host = "unix:///var/run/docker.sock"
    }

    resource "docker_container" "foo" {
      image = "redis:latest"
      name = "foo"
    }

    module "module_a" {
      source = "./module_a"
    }""")
