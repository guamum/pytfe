import pytfe
import textwrap


from pytfe import Raw
from pytfe import Quote
from unittest import TestCase


class TestFormatLocals(TestCase):

    def test_format_locals(self):

        local = pytfe.Locals(service_name=Quote('forum'))
        expected = pytfe.TFBlock("""
        locals {
          service_name = "forum"
        }""")
        self.assertEqual(local.format(), expected)

    def test_format_locals_with_map(self):

        local = pytfe.Locals(local_map={'hello': Quote('world')})
        expected = pytfe.TFBlock("""
        locals {
          local_map = {
            hello = "world"
          }
        }""")
        self.assertEqual(local.format(), expected)

    def test_format_locals_with_list(self):

        local = pytfe.Locals(local_list=[Quote('string'), '"string2"'])
        expected = pytfe.TFBlock("""
        locals {
          local_list = [
            "string",
            "string2"
          ]
        }""")
        self.assertEqual(local.format(), expected)


class TestFormatFunction(TestCase):

    def test_simple_function(self):
        function = pytfe.Function(
            'concat', "aws_instance.blue.*.id", "aws_instance.green.*.id"
        )
        expected = pytfe.TFBlock(
            """concat(aws_instance.blue.*.id, aws_instance.green.*.id)"""
        )
        self.assertEqual(function.format(), expected)


class TestFormatResource(TestCase):

    def test_simple_resource(self):
        function = pytfe.Resource(
            'docker_container', "redis", image=Quote('redis'), name=Quote('foo')
        )
        expected = pytfe.TFBlock("""
        resource "docker_container" "redis" {
          image = "redis"
          name = "foo"
        }""")
        self.assertEqual(function.format(), expected)


class TestFunctionGenerator(TestCase):

    def test_simple(self):
        func = pytfe.f.list()

        expected = textwrap.dedent("""list()""")
        self.assertEqual(func.format(), expected)

    def test_simple_two_nested_function(self):
        func = pytfe.f.list(pytfe.f.object(hello='"world"'))

        expected = pytfe.TFBlock("""
        list(object({
          hello = "world"
        }))""")
        self.assertEqual(func.format(), expected)


class TestFormatVariable(TestCase):

    def test_simple_resource(self):
        variable = pytfe.Variable(
            'redis_image', type=Quote("string"), default=Quote('v1.2')
        )
        expected = pytfe.TFBlock("""
        variable "redis_image" {
          type = "string"
          default = "v1.2"
        }""")
        self.assertEqual(variable.format(), expected)

    def test_complex_variable(self):
        """
        source: https://www.terraform.io/docs/language/values/variables.html#declaring-an-input-variable
        """
        variable = pytfe.variable(
            'docker_ports',
            type=pytfe.function(
                'list',
                pytfe.function(
                    'object',
                    internal='number',
                    external='number',
                    protocol='string'
                )
            ),
            default=[
                dict(
                    internal=8300,
                    external=8300,
                    protocol=Quote("tcp")
                )
            ]
        )

        expected = pytfe.TFBlock("""
        variable "docker_ports" {
          type = list(object({
            internal = number
            external = number
            protocol = string
          }))
          default = [
            {
              internal = 8300
              external = 8300
              protocol = "tcp"
            }
          ]
        }""")
        self.assertEqual(variable.format(), expected)

    def test_complex_variable_using_function_generator(self):
        """
        source: https://www.terraform.io/docs/language/values/variables.html#declaring-an-input-variable
        """
        variable = pytfe.variable(
            'docker_ports',
            type=pytfe.f.list(pytfe.f.object(
                internal='number',
                external='number',
                protocol='string'
            )),
            default=[
                dict(
                    internal=8300,
                    external=8300,
                    protocol=Quote("tcp")
                )
            ]
        )

        expected = pytfe.TFBlock("""
        variable "docker_ports" {
          type = list(object({
            internal = number
            external = number
            protocol = string
          }))
          default = [
            {
              internal = 8300
              external = 8300
              protocol = "tcp"
            }
          ]
        }""")

        self.assertEqual(variable.format(), expected)

    def test_complex_variable_with_type_using_string(self):
        """
        source: https://www.terraform.io/docs/language/values/variables.html#declaring-an-input-variable
        """
        variable = pytfe.variable(
            'docker_ports',
            type=pytfe.TFBlock("""
            list(object({
              internal = number
              external = number
              protocol = string
            }))"""),
            default=pytfe.TFBlock("""
            [
              {
                internal = 8300
                external = 8300
                protocol = "tcp"
              }
            ]""")
        )

        expected = pytfe.TFBlock("""
        variable "docker_ports" {
          type = list(object({
            internal = number
            external = number
            protocol = string
          }))
          default = [
            {
              internal = 8300
              external = 8300
              protocol = "tcp"
            }
          ]
        }""")
        self.assertEqual(variable.format(), expected)

    def test_variable_reference_on_docker_provider(self):
        plan = pytfe.Plan()
        docker_image = plan.add(pytfe.variable(
            "docker_image", type="string", default=pytfe.Quote(''),
        ))

        plan += pytfe.provider("docker", host='"unix:///var/run/docker.sock"')
        plan += pytfe.resource(
            "docker_container", "foo",
            image=docker_image, name='"foo"'
        )

        expected = pytfe.TFBlock("""
        provider "docker" {
          host = "unix:///var/run/docker.sock"
        }

        resource "docker_container" "foo" {
          image = var.docker_image
          name = "foo"
        }""")
        self.assertEqual(plan.format(), expected)


class TestFormatProvider(TestCase):

    def test_simple(self):
        function = pytfe.Provider(
            'kubernetes', load_config_file=True
        )
        expected = pytfe.TFBlock("""
        provider "kubernetes" {
          load_config_file = true
        }""")
        self.assertEqual(function.format(), expected)


class TestFormatOutput(TestCase):

    def test_simple(self):
        obj = pytfe.Output(
            'my_output', value=True, description='"My output value"'
        )
        expected = pytfe.TFBlock("""
        output "my_output" {
          value = true
          description = "My output value"
        }""")
        self.assertEqual(obj.format(), expected)


class TestFormatProvisioner(TestCase):

    def test_simple(self):
        obj = pytfe.Provisioner(
            'local-exec',
            command=Quote("echo The server's IP address is ${self.private_ip}"),
            on_failure="continue"
        )
        expected = pytfe.TFBlock("""
        provisioner "local-exec" {
          command = "echo The server's IP address is ${self.private_ip}"
          on_failure = continue
        }""")
        self.assertEqual(obj.format(), expected)

    def test_provisioner_with_connection(self):
        obj = pytfe.Provisioner(
            'local-exec',
            command=Quote("echo The server's IP address is ${self.private_ip}"),
            on_failure=Raw("continue"),
            connection=pytfe.Connection(
                type=Quote("winrm"),
                user=Quote("Administrator"),
            )
        )
        expected = pytfe.TFBlock("""
        provisioner "local-exec" {
          command = "echo The server's IP address is ${self.private_ip}"
          on_failure = continue
          connection {
            type = "winrm"
            user = "Administrator"
          }
        }""")
        self.assertEqual(obj.format(), expected)

    def test_provisioner_with_variable_and_connection(self):
        plan = pytfe.Plan()
        variable = plan.add(pytfe.variable('user_name', type='string'))
        provisioner = pytfe.provisioner(
            'file',
            source=Quote("conf/myapp.conf"),
            destination=Quote("/etc/myapp.conf"),
            connection=pytfe.Connection(
                type=Quote("ssh"),
                user=Quote("root"),
                password=variable.user_name,
                host="var.host"
            )
        )
        plan += provisioner

        expected = pytfe.TFBlock("""
        provisioner "file" {
          source = "conf/myapp.conf"
          destination = "/etc/myapp.conf"
          connection {
            type = "ssh"
            user = "root"
            password = var.user_name
            host = var.host
          }
        }""")
        self.assertEqual(plan.format(), expected)


class TestFormatConnection(TestCase):

    def test_simple(self):
        obj = pytfe.Connection(
            type=Quote("winrm"),
            user=Quote("Administrator"),
        )
        expected = pytfe.TFBlock("""
        connection {
          type = "winrm"
          user = "Administrator"
        }""")
        self.assertEqual(obj.format(), expected)


class TestFormatModule(TestCase):

    def test_simple(self):
        module = pytfe.Module(
            'consul',
            source=Quote("hashicorp/consul/aws"),
            version=Quote("0.0.5"),
            servers=3
        )
        expected = pytfe.TFBlock("""
        module "consul" {
          source = "hashicorp/consul/aws"
          version = "0.0.5"
          servers = 3
        }""")
        self.assertEqual(module.format(), expected)


class TestFormatData(TestCase):

    def test_simple(self):
        data = pytfe.data(
            'digitalocean_kubernetes_cluster',
            'example',
            name="prod-cluster-01"
        )
        expected = pytfe.TFBlock("""
        data "digitalocean_kubernetes_cluster" "example" {
          name = prod-cluster-01
        }""")
        self.assertEqual(data.format(), expected)

    def test_reference_data_in_a_resouce(self):
        plan = pytfe.Plan()
        data = plan.add(pytfe.data(
            'digitalocean_kubernetes_cluster',
            'example',
            name="prod-cluster-01"
        ))

        plan.add(pytfe.resource(
            "local_file", "kubeconfig_primary",
            content=data.kube_config,
            filename='"${path.module}/primary-k8s-config.yaml"',
            sensitive_content=True
        ))

        expected = pytfe.TFBlock("""
        data "digitalocean_kubernetes_cluster" "example" {
          name = prod-cluster-01
        }

        resource "local_file" "kubeconfig_primary" {
          content = data.digitalocean_kubernetes_cluster.example.kube_config
          filename = "${path.module}/primary-k8s-config.yaml"
          sensitive_content = true
        }""")

        self.assertEqual(plan.format(), expected)


class TestFormatTerraform(TestCase):

    def test_simple(self):
        module = pytfe.terraform(
            pytfe.backend(
                'consul',
                address='"demo.consul.io"',
                scheme='"https"',
                path='"example_app/terraform_state"'
            ),
            source=Quote("hashicorp/consul/aws"),
            version=Quote("0.0.5")
        )
        expected = pytfe.TFBlock("""
        terraform {
          backend "consul" {
            address = "demo.consul.io"
            scheme = "https"
            path = "example_app/terraform_state"
          }
          source = "hashicorp/consul/aws"
          version = "0.0.5"
        }""")
        self.assertEqual(module.format(), expected)


class TestFormatTFBlock(TestCase):

    def test_tfblock_passed_to_terraform(self):
        obj = pytfe.terraform(
            pytfe.TFBlock("""
            required_providers {
              github     = "~> 2.9.0"
              helm       = "~> 1.2.4"
              kubernetes = "~> 1.11.0"
              local      = "~> 1.4.0"
              tls        = "~> 3.1.0"
            }"""),
            required_version='">= 0.13"'
        )
        expected = pytfe.TFBlock("""
        terraform {
          required_providers {
            github     = "~> 2.9.0"
            helm       = "~> 1.2.4"
            kubernetes = "~> 1.11.0"
            local      = "~> 1.4.0"
            tls        = "~> 3.1.0"
          }
          required_version = ">= 0.13"
        }""")
        self.assertEqual(obj.format(), expected)

    def test_tfblock_passed_to_item(self):
        obj = pytfe.Item(
            "terraform",
            pytfe.TFBlock("""
            required_version = ">= 0.13"
            required_providers {
              github     = "~> 2.9.0"
              helm       = "~> 1.2.4"
              kubernetes = "~> 1.11.0"
              local      = "~> 1.4.0"
              tls        = "~> 3.1.0"
            }"""),
        )
        expected = pytfe.TFBlock("""
        terraform {
          required_version = ">= 0.13"
          required_providers {
            github     = "~> 2.9.0"
            helm       = "~> 1.2.4"
            kubernetes = "~> 1.11.0"
            local      = "~> 1.4.0"
            tls        = "~> 3.1.0"
          }
        }""")
        self.assertEqual(obj.format(), expected)
