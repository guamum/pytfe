import argparse
import importlib
import inspect
import logging
import os
import subprocess
import sys
import textwrap

from importlib import util as importlib_util

from . import __version__


logging.basicConfig(format="[%(levelname)1.1s] %(message)s", level=logging.INFO)


CURDIR = os.path.abspath(os.path.curdir)
HEADER = "# This is an autogenerated file. Do not edit this file directly."

IDENTATION = "  "


class Attribute(str):
    """An `Attribute` handles access to not yet known attributes.
    This called by `Block.__getattr__` to deal with
    In the example below the ``aws_instance`` does not have attributes
    ``.server`` and in turn ``.server.private_ip``. To prevent Python
    from raising an `AttributeError` the `Attribute.__getattr__()` method
    creates a new string by appending the attribute name.
    Python:
        config = terrascript.Terrascript()
        config += terrascript.aws.aws(version='~> 2.0', region='us-east-1')
        aws_instance = terrascript.aws.r.aws_instance('web', ...)
        config += aws_instance
        config += terrascript.Output('instance_ip_addr',
                                      value=aws_instance.server.private_ip)
                                                        ^^^^^^^^^^^^^^^^^^
    JSON:
    """

    def __getattr__(self, name):
        return Attribute(f'{self}.{name}')


def format_function(value):
    lines = []
    lines.append(value.args[0])
    lines.append('(')
    lines_inside = []
    for arg in value.all_args[1:]:
        if isinstance(arg, Function):
            result = format_function(arg)
        elif isinstance(arg, str):
            result = str(arg)
        elif isinstance(arg, dict):
            result = format_dict(arg)
        elif isinstance(arg, list):
            result = format_list(arg)
        elif isinstance(arg, Item):
            result = arg.format()
        lines_inside.append(result)

    if isinstance(value, Function) and value.kwds:
        lines_inside.append(format_dict(value.kwds))

    fn_args = ', '.join(lines_inside)
    return ''.join(lines) + fn_args + ')'


def format_any_obj(key: str, value: object, indent: int = 0):
    temp_value = None
    return_as_map = True

    if any(isinstance(value, x) for x in [Connection, Backend]):
        return_as_map = False
        temp_value = value.format()
    elif isinstance(value, Function):
        temp_value = value.format()
    elif isinstance(value, Variable):
        var_path = '.'.join(value.args)
        temp_value = f'var.{var_path}'
    elif isinstance(value, Resource):
        _path = '.'.join(value.args)
        temp_value = f'{_path}'
    elif isinstance(value, Locals):
        _path = '.'.join(value.args)
        temp_value = f'local.{_path}'
    elif isinstance(value, Data):
        _path = '.'.join(value.args)
        temp_value = f'data.{_path}'
    elif isinstance(value, dict):
        temp_value = format_dict(value, indent=indent)
    elif isinstance(value, list):
        temp_value = format_list(value, indent=indent)
    elif isinstance(value, Raw):
        temp_value = value
    elif isinstance(value, Quote):
        temp_value = str(value)
    elif isinstance(value, bool):
        temp_value = 'true' if value else 'false'
    else:
        temp_value = value

    if key and return_as_map:
        return textwrap.indent(f'{key} = {temp_value}', '')

    return textwrap.indent(f'{temp_value}', '')


def format_dict(dct: dict, indent: int = 0) -> str:
    lines = []
    lines.append("{")
    for k, v in dct.items():
        v = format_any_obj(k, v, indent=indent)
        lines.append(textwrap.indent(f"{v}", IDENTATION))
    lines.append("}")
    return textwrap.indent("\n".join(lines), '')


def format_list(lst: list, indent: int = 0) -> str:
    lines = []
    lines.append("[")
    inside_lines = []
    for item in lst:
        item = format_any_obj('', item, indent=indent)
        inside_lines.append(textwrap.indent(f'{item}', IDENTATION))
    lines.append(',\n'.join(inside_lines))
    lines.append("]")
    return textwrap.indent("\n".join(lines), '')


def evaluate_attribute(cls, attr):
    if isinstance(cls, Resource):
        _path = '.'.join(cls.args)
        return Attribute(f"{_path}.{attr}")
    if isinstance(cls, Module):
        return Attribute(f"module.{attr}")
    if isinstance(cls, Variable):
        return Attribute(f"var.{cls.args[0]}")
    # elif isinstance(cls, Locals):
    #     return Attribute(f"local.{attr}")
    elif isinstance(cls, Data):
        # data.google_compute_image.NAME.ATTR]
        data_path = ".".join(cls.args)
        return Attribute(f"data.{data_path}.{attr}")
    else:
        raise AttributeError(attr)


class Item:

    def __init__(self, item_type: str, *args, **kwds):
        self.type = item_type
        self.args = tuple(arg for arg in args if not isinstance(arg, (Item, TFBlock)))
        self.all_args = tuple(arg for arg in args)
        self.kwds = dict(**kwds)
        self.items = tuple(item for item in args if isinstance(item, (Item, TFBlock)))

    def format(self) -> str:
        lines = []
        start_block = self.type + "".join(' "{}"'.format(arg) for arg in self.args)
        lines.append(start_block + " {")
        for item in self.items:
            lines.append(textwrap.indent(item.format(), IDENTATION))
        for k, v in self.kwds.items():
            v = format_any_obj(k, v)
            lines.append(textwrap.indent(f'{v}', IDENTATION))
        lines.append("}")
        return "\n".join(lines)

    def __getattr__(self, attr):
        """Special handling for accessing attributes,
        If ``Block.attr`` does not exist, try to return Block[attr]. If that
        does not exists either, return `attr` as a string, prefixed
        by the name (and type) of the Block that is referenced.
        This is for example necessary for referencing an attribute of a
        Terraform resource which only becomes available after the resource
        has been created.
        Example:
           instance = terrascript.resources.aws_instance("server", ...)
           output = terrascript.Output("instance_ip_addr",
                                       value=instance.private_ip)
                                                    ^^^^^^^^^^
        Where ``instance.private_ip`` does not (yet) exist.
        """
        # Try to return the entry in the dictionary. Otherwise return a string
        # which must be formatted differently depending on what is referenced.

        if attr in self.kwds:
            return self.kwds[attr]
        elif attr.startswith("__"):
            raise AttributeError
        else:
            return evaluate_attribute(self, attr)

    def __str__(self):
        return Attribute(repr(self))

    def __repr__(self):
        return Attribute(format_any_obj('', self))


class MetaClassTF(type):
    """docstring for MetaClassTF"""

    def __getattr__(cls, attr):
        # Handle class methods
        def wrap(*args, **kwargs):
            return cls(attr, *args, **kwargs)
        return wrap


class BaseItem(Item, metaclass=MetaClassTF):

    def __init__(self, *args, **kwds):
        super().__init__(self.type, *args, **kwds)


class Provider(BaseItem):
    type = 'provider'


class Resource(BaseItem):
    type = 'resource'

    def asterisk(self):
        pass


class Output(BaseItem):
    type = 'output'


class Locals(BaseItem):
    type = 'locals'

    def __getattr__(self, attr):
        return Attribute(f"local.{attr}")


class Module(BaseItem):
    type = 'module'


class Provisioner(BaseItem):
    type = 'provisioner'


class Function(BaseItem):
    type = 'function'

    def format(self):
        return format_function(self)


class Variable(BaseItem):
    type = 'variable'

    # def format(self):
    #     return f'var.{self.args[0]}'


class Connection(BaseItem):
    """docs: https://www.terraform.io/docs/language/resources/provisioners/connection.html"""
    type = 'connection'


class Backend(BaseItem):
    type = 'backend'


class Data(BaseItem):
    type = 'data'


class Terraform(BaseItem):
    type = 'terraform'


class TFVar(Item, metaclass=MetaClassTF):

    def __init__(self, *args, **kwds):
        if len(args[1:]) > 1:
            raise Exception('Can receive only one arg value')
        super().__init__(args[0], *args[1:], **kwds)

    def format(self):
        lines = []
        if self.kwds:
            return format_any_obj(self.type, self.kwds)
        else:
            lines.append(self.type + ' = ')
            for arg in self.all_args:
                lines.append(format_any_obj('', arg))
            return ''.join(lines)


class TFBlock:
    """docstring for TFBlock"""

    def __init__(self, value: str='', **kwargs):
        self.value = value
        self.kwargs = kwargs

    def format(self):
        formatted = textwrap.dedent(self.value)
        for k, v in self.kwargs.items():
            replace = '{' + k + '}'
            formatted_value = format_any_obj('', v)
            formatted = formatted.replace(replace, formatted_value)
        if self.value.startswith('\n'):
            formatted = formatted.replace('\n', '', 1)
        return formatted

    def __str__(self):
        return self.format()

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        if isinstance(other, str):
            return str(self) == other
        return False


class Raw:

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return self.value

    def __repr__(self):
        return str(self)

    def __eq__(self, other):
        """Overrides the default implementation"""
        if isinstance(other, str):
            return str(self) == other
        return False


class Quote:

    def __init__(self, value):
        self.value = value

    def __str__(self):
        return f'"{self.value}"'

    def __repr__(self):
        return str(self)


class Plan:

    def __init__(self):
        # self.items = []
        self.kwds = dict()

    @property
    def modules(self):
        return [item for item in self.items if item.type == "module"]

    def add(self, item: Item):
        self += item
        return item

    def __iadd__(self, item: Item):
        if not isinstance(item, Item):
            raise ValueError

        if item.type not in self.kwds:
            if not item.args:
                self.kwds[item.type] = []
            else:
                self.kwds[item.type] = dict()

        if item.args:
            args_path = '.'.join(item.args)
            self.kwds[item.type][args_path] = item
        else:
            self.kwds[item.type].append(item)
        return self

    @property
    def items(self):
        """
            {'locals': [item, item]}
        """
        from itertools import chain

        def _unpack(obj):
            if isinstance(obj, dict):
                return obj.values()
            return obj

        nested_items = [_unpack(v) for v in self.kwds.values()]
        _items = list(chain(*nested_items))

        return _items

    # fmt: off
    def format_old(self):
        ignore_types = ("variable", "output", "data")
        return "\n\n".join(
            map(
                lambda item: item.format(),
                filter(lambda item: item.type not in ignore_types, self.items),
            )
        ).strip("\n")

    def format(self):
        items = self.items
        content = []
        content.append(self.format_by_item_type(items, 'terraform'))
        content.append(self.format_by_item_type(items, 'provider'))
        content.append(self.format_by_item_type(items, 'locals'))
        content.append(self.format_by_item_type(items, 'resource'))
        content.append(self.format_by_item_type(items, 'module'))
        return '\n\n'.join(x for x in content if x)

    def format_full(self):
        return "\n\n".join(
            map(lambda item: item.format(), self.items)
        ).strip("\n")

    def format_by_item_type(self, items, *args):
        return "\n\n".join(
            map(
                lambda item: item.format(),
                filter(lambda item: item.type in tuple(arg for arg in args), self.items))
        ).strip("\n")

    def format_datas(self):
        return self.format_by_item_type(self.items, 'data')

    def format_vars(self):
        return self.format_by_item_type(self.items, 'variable')

    def format_outs(self):
        return self.format_by_item_type(self.items, 'output')
    # fmt: on

    def update(self, plan):
        if isinstance(plan, Plan):
            for k, v in plan.kwds.items():
                if isinstance(v, dict):
                    if k in self.kwds:
                        self.kwds[k].update(**plan.kwds[k])
                    else:
                        self.kwds[k] = plan.kwds[k]
                if isinstance(v, list):
                    if v2 in self.kwds:
                        for x in v2:
                            self.kwds[k].append(v2)
                    else:
                        self.kwds[k] = plan.kwds[k]
            return
        raise Exception(f'{plan} must be a Plan instance.')


def clear_dir(odir: str):
    ans = input(
        (
            "All autogenerated '*.tf' and '*.tfvars' files and empty folders\n"
            f"inside {odir} directory will be deleted.\n"
            "Continue [y/n]: "
        )
    )
    if ans != "y":
        logging.info("Aborted by user")
        sys.exit(-1)

    def clear(odir):
        for filename in filter(lambda item: item.endswith(".tf") or item.endswith(".tfvar"), os.listdir(odir)):
            with open(filename, "r") as f:
                if f.readline() != HEADER:
                    continue
            os.remove(filename)

        for dirname in [item for item in os.listdir(odir) if os.path.isdir(item)]:
            if not os.listdir(dirname):
                os.rmdir(dirname)
            else:
                clear(dirname)
                if not os.listdir(dirname):
                    os.rmdir(dirname)

    clear(odir)


def load_main_module(moddir: str):
    curdir = os.path.abspath(os.path.curdir)

    try:
        os.chdir(moddir)
        if moddir not in set(sys.path):
            sys.path.append(moddir)

        modpath = os.path.join(moddir, "main.py")
        spec = importlib_util.spec_from_file_location("main", modpath)
        module = importlib_util.module_from_spec(spec)

        try:
            spec.loader.exec_module(module)
        except FileNotFoundError:
            logging.error(f"Module main.py not found in directory {moddir}")
            sys.exit(-1)

        if not hasattr(module, "plan") or not isinstance(module.plan, Plan):
            logging.error(f"Valid plan object not found in module {modpath}")
            sys.exit(-1)

        return module

    finally:
        os.chdir(curdir)


def write(odir: str, module: object):
    def write_file(content, file_name):
        file_path = os.path.join(odir, file_name)
        with open(file_path, "w") as f:
            f.write("\n\n".join((HEADER, content)))

    os.makedirs(odir, exist_ok=True)

    body = module.plan.format()
    if body:
        write_file(body, "main.tf")

    variables = module.plan.format_vars()
    write_file(variables, "variables.tf")

    outputs = module.plan.format_outs()
    write_file(outputs, "outputs.tf")

    datas = module.plan.format_datas()
    write_file(datas, "data.tf")

    for item in module.plan.modules:
        source = item.kwds.get("source", "").strip('"')
        if source and (source.startswith(".") or source.startswith("..")):
            module = load_main_module(os.path.abspath(source))
            moddir = os.path.join(odir, source)
            curdir = os.path.abspath(os.path.curdir)
            try:
                os.chdir(os.path.join(curdir, source))
                write(moddir, module)
            finally:
                os.chdir(curdir)


def generate(idir: str, odir: str):
    # if os.path.exists(odir):
    #     clear_dir(odir)

    os.chdir(idir)

    module = load_main_module(idir)
    write(odir, module)

    try:
        subprocess.run(["terraform", "fmt"], cwd=odir, check=True)
    except subprocess.CalledProcessError as e:
        logging.error(e)
        sys.exit(-1)


def upgrade(odir: str):
    items = os.listdir(odir)

    if any(filter(lambda item: item.endswith(".tf"), items)):
        try:
            subprocess.run(["terraform", "0.13upgrade", "-yes"], cwd=odir, check=True)
        except subprocess.CalledProcessError as e:
            logging.error(e)
            sys.exit(-1)

    for item in items:
        item = os.path.join(odir, item)
        if os.path.isdir(item):
            upgrade(item)


def generate_cmd(args):
    generate(args.idir, args.idir)
    if args.upgrade:
        upgrade(args.idir)


def main():
    parser = argparse.ArgumentParser(description="Python to Terraform converter utility")
    parser.add_argument("-V", "--version", action="version",
                        version="%(prog)s {}".format(__version__))

    subparsers = parser.add_subparsers(title="subcommands")

    parser_generate_cmd = subparsers.add_parser(
        "generate", description="Generate terraform plans", help="generate terraform plans"
    )
    parser_generate_cmd.add_argument(
        "-u", "--upgrade", action="store_true", help="run 'terraform 0.13upgrade' command for each module"
    )
    parser_generate_cmd.add_argument(
        "idir",
        metavar="DIR",
        default=CURDIR,
        nargs="?",
        help="directory with root main.py (default: current directory)",
    )
    parser_generate_cmd.set_defaults(func=generate_cmd)

    args = parser.parse_args()
    args.func(args)


function = Function
provisioner = Provisioner
variable = Variable
terraform = Terraform
backend = Backend
output = Output
provider = Provider
locals = Locals
resource = Resource
connection = Connection
module = Module
data = Data
plan = Plan
block = Item
tfvar = TFVar

__all__ = [
    "Plan",
    "plan",
    'block',
    "TFBlock",
    "backend",
    "connection",
    "data",
    "function",
    "locals",
    "module",
    "output",
    "provider",
    "provisioner",
    "resource",
    "terraform",
    "variable",
    "Quote",
    "tfvar",
]

if __name__ == "__main__":
    main()
