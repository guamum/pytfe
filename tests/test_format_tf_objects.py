import pytfe
import textwrap


from pytfe import Quote
from pytfe.app import Raw
from unittest import TestCase


class TestFormatLocals(TestCase):

    def test_format_locals(self):

        local = pytfe.locals(service_name=Quote('forum'))
        expected = pytfe.TFBlock("""
        locals {
          service_name = "forum"
        }""")
        self.assertEqual(local.format(), expected)

    def test_format_locals_with_map(self):
        plan = pytfe.plan()
        plan += pytfe.locals(local_map={'hello': Quote('world')})
        expected = pytfe.TFBlock("""
        locals {
          local_map = {
            hello = "world"
          }
        }""")
        self.assertEqual(plan.format(), expected)

    def test_format_locals_with_list(self):

        local = pytfe.locals(local_list=[Quote('string'), '"string2"'])
        expected = pytfe.TFBlock("""
        locals {
          local_list = [
            "string",
            "string2"
          ]
        }""")
        self.assertEqual(local.format(), expected)

    def test_refernce_to_local_resorce(self):
        plan = pytfe.plan()
        local = plan.add(pytfe.locals(local_map={'hello': Quote('world')}))
        plan += pytfe.output.local_output(
            value_level_1=local.local_map,
            value_level_2=local.local_map.hello,
            value_not_exist_attr=local.not_exist_attr
        )
        expected = pytfe.TFBlock("""
        locals {
          local_map = {
            hello = "world"
          }
        }

        output "local_output" {
          value_level_1 = local.local_map
          value_level_2 = local.local_map.hello
          value_not_exist_attr = local.not_exist_attr
        }""")

        self.assertEqual(plan.format_full(), expected)


class TestFormatFunction(TestCase):

    def test_simple_function(self):
        function = pytfe.function(
            'concat', "aws_instance.blue.*.id", "aws_instance.green.*.id"
        )
        dot_syntax = pytfe.function.concat(
            "aws_instance.blue.*.id", "aws_instance.green.*.id"
        )

        expected = pytfe.TFBlock(
            """concat(aws_instance.blue.*.id, aws_instance.green.*.id)"""
        )
        self.assertEqual(function.format(), expected)
        self.assertEqual(dot_syntax.format(), expected)


class TestFormatResource(TestCase):

    def test_simple_resource(self):
        function = pytfe.resource(
            'docker_container', "redis", image=Quote('redis'), name=Quote('foo')
        )
        expected = pytfe.TFBlock("""
        resource "docker_container" "redis" {
          image = "redis"
          name = "foo"
        }""")
        self.assertEqual(function.format(), expected)

    def test_simple_resource_new_syntax(self):
        function = pytfe.resource.docker_container(
            "redis", image=Quote('redis'), name=Quote('foo')
        )
        expected = pytfe.TFBlock("""
        resource "docker_container" "redis" {
          image = "redis"
          name = "foo"
        }""")
        self.assertEqual(function.format(), expected)

    def test_reference_to_local_file_resource(self):
        plan = pytfe.Plan()
        local_file = plan.add(pytfe.resource.local_file(
            "my_local_file",
            filename='"${path.module}/kubeconfig.yaml"',
            content='"Hello World"',
        ))

        plan += pytfe.output.localfile_output(
            value=local_file,
            value_exist_attr=local_file.filename,
            value_not_exist_attr=local_file.not_exist_attr
        )

        expected = pytfe.TFBlock("""
        resource "local_file" "my_local_file" {
          filename = "${path.module}/kubeconfig.yaml"
          content = "Hello World"
        }

        output "localfile_output" {
          value = local_file.my_local_file
          value_exist_attr = "${path.module}/kubeconfig.yaml"
          value_not_exist_attr = local_file.my_local_file.not_exist_attr
        }""")

        self.assertEqual(plan.format_full(), expected)

    def test_reference_to_local_file_resource(self):
        plan = pytfe.Plan()
        plan.add(pytfe.resource.local_file(
            "my_local_file",
            filename='"${path.module}/kubeconfig.yaml"',
            content='"Hello World"',
        ))
        plan.add(pytfe.resource.local_file(
            "my_local_file_v2",
            filename='"${path.module}/kubeconfig.yaml"',
            content='"Hello World v2"',
        ))
        expected = pytfe.TFBlock("""
        resource "local_file" "my_local_file" {
          filename = "${path.module}/kubeconfig.yaml"
          content = "Hello World"
        }

        resource "local_file" "my_local_file_v2" {
          filename = "${path.module}/kubeconfig.yaml"
          content = "Hello World v2"
        }""")

        self.assertEqual(plan.format_full(), expected)


class TestFunctionGenerator(TestCase):

    def test_simple(self):
        func = pytfe.function.list()

        expected = textwrap.dedent("""list()""")
        self.assertEqual(func.format(), expected)

    def test_simple_two_nested_function(self):
        func = pytfe.function.list(pytfe.function.object(hello='"world"'))

        expected = pytfe.TFBlock("""
        list(object({
          hello = "world"
        }))""")
        self.assertEqual(func.format(), expected)


class TestFormatVariable(TestCase):

    def test_simple_resource(self):
        variable = pytfe.variable(
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
            type=pytfe.function.list(pytfe.function.object(
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

    def test_complex_variable_reference(self):
        plan = pytfe.Plan()
        variable = plan.add(pytfe.variable(
            "extra_vars",
            type="map(string)",
            default=pytfe.TFBlock("""{hello = "world }"""),
        ))

        plan += pytfe.provider("docker", host='"unix:///var/run/docker.sock"')
        plan += pytfe.resource(
            "docker_container", "foo",
            image=variable,
            image1=variable.extra_vars,
            image2=variable.extra_vars.hello,
            name='"foo"'
        )

        expected = pytfe.TFBlock("""
        variable "extra_vars" {
          type = map(string)
          default = {hello = "world }
        }

        provider "docker" {
          host = "unix:///var/run/docker.sock"
        }

        resource "docker_container" "foo" {
          image = var.extra_vars
          image1 = var.extra_vars
          image2 = var.extra_vars.hello
          name = "foo"
        }""")
        self.assertEqual(plan.format_full(), expected)


class TestFormatProvider(TestCase):

    def test_simple(self):
        function = pytfe.provider(
            'kubernetes', load_config_file=True
        )
        expected = pytfe.TFBlock("""
        provider "kubernetes" {
          load_config_file = true
        }""")
        self.assertEqual(function.format(), expected)


class TestFormatOutput(TestCase):

    def test_simple(self):
        obj = pytfe.output(
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
        obj = pytfe.provisioner(
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
        obj = pytfe.provisioner(
            'local-exec',
            command=Quote("echo The server's IP address is ${self.private_ip}"),
            on_failure=Raw("continue"),
            connection=pytfe.connection(
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
            connection=pytfe.connection(
                type=Quote("ssh"),
                user=Quote("root"),
                password=variable.user_name,
                host="var.host"
            )
        )
        plan += provisioner

        expected = pytfe.TFBlock("""
        variable "user_name" {
          type = string
        }

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
        self.assertEqual(plan.format_full(), expected)


class TestFormatConnection(TestCase):

    def test_simple(self):
        obj = pytfe.connection(
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
        module = pytfe.module.consul(
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

    def test_reference_data_in_a_local(self):
        plan = pytfe.Plan()
        data = plan.add(pytfe.data(
            'digitalocean_kubernetes_cluster',
            'example',
            name="prod-cluster-01"
        ))

        plan.add(pytfe.locals(
            value=data,
            value_level_1=data.extra_vars,
        ))

        expected = pytfe.TFBlock("""
        data "digitalocean_kubernetes_cluster" "example" {
          name = prod-cluster-01
        }

        locals {
          value = data.digitalocean_kubernetes_cluster.example
          value_level_1 = data.digitalocean_kubernetes_cluster.example.extra_vars
        }""")

        self.assertEqual(plan.format_full(), expected)

        expected_data = pytfe.TFBlock("""
        data "digitalocean_kubernetes_cluster" "example" {
          name = prod-cluster-01
        }""")
        self.assertEqual(plan.format_datas(), expected_data)

        self.assertIsInstance(data, pytfe.data)
        self.assertEqual(str(data), 'data.digitalocean_kubernetes_cluster.example')
        self.assertEqual(repr(data), 'data.digitalocean_kubernetes_cluster.example')


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

    def test_tfblock_passed_to_block(self):
        obj = pytfe.terraform(
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

    def test_tfblock_with_parameters(self):
        obj = pytfe.terraform(pytfe.TFBlock(
            """
            required_version = ">= 0.13"
            required_providers {
              github     = "{github_version}"
              helm       = "{helm_version}"
              kubernetes = "{kubernetes_version}"
              local      = "{local_version}"
              tls        = "{tls_version}"
            }""",
            github_version="~> 2.9.0",
            helm_version="~> 1.2.4",
            kubernetes_version="~> 1.11.0",
            tls_version="~> 3.1.0",
            local_version="~> 1.4.0"
        ))

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


class TestFormatPlan(TestCase):

    def test_join_two_empthy_plans(self):
        plan1 = pytfe.Plan()
        plan2 = pytfe.Plan()

        plan1.update(plan2)

        self.assertEqual(plan1.format(), '')

    def test_join_two_plans_first_empthy_and_second_with_one_variable(self):
        plan1 = pytfe.Plan()
        plan2 = pytfe.Plan()
        plan2 += pytfe.variable('my_variable', type='"string"', default='""')

        self.assertEqual(plan1.format_vars(), '')
        plan1.update(plan2)

        expected = pytfe.TFBlock("""
        variable "my_variable" {
          type = "string"
          default = ""
        }""")
        self.assertEqual(plan1.format_vars(), expected)


class TestFormatTFVars(TestCase):

    def test_format_simple_empthy_tfvar(self):
        plan = pytfe.Plan()

        # TODO: assert expecific exception
        with self.assertRaises(Exception):
            var = pytfe.tfvar(
                "empty_tfvar"
            )
            plan += var

    def test_format_simple_empthy_list(self):
        plan = pytfe.Plan()
        tfvar = pytfe.tfvar(
            "var_list",
            []
        )

        expected = pytfe.TFBlock("""
        var_list = [

        ]""")
        plan += tfvar

        self.assertEqual(plan.format_full(), expected)

    def test_format_simple_ftvars_dict(self):
        plan = pytfe.Plan()
        plan += pytfe.tfvar(
            "vars",
            k8s_primary='"k8s-staging"',
            do_region='"nyc3"',
        )

        expected = pytfe.TFBlock("""
        vars = {
          k8s_primary = "k8s-staging"
          do_region = "nyc3"
        }""")

        self.assertEqual(plan.format_full(), expected)

    def test_format_simple_ftvars_list(self):
        tfvar = pytfe.tfvar(
            "var_list",
            [1, 2, 3]
        )

        expected = pytfe.TFBlock("""
        var_list = [
          1,
          2,
          3
        ]""")
        self.assertEqual(tfvar.format(), expected)

    def test_format_add_tfvar_to_plan(self):
        plan = pytfe.Plan()
        plan += pytfe.tfvar(
            "vars",
            k8s_primary='"k8s-staging"',
            do_region='"nyc3"',
        )

        expected = pytfe.TFBlock("""
        vars = {
          k8s_primary = "k8s-staging"
          do_region = "nyc3"
        }""")
        self.assertEqual(plan.format_full(), expected)
