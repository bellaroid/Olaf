import yaml
import os
import logging
import importlib

_logger = logging.getLogger(__name__)



def initialize():
    """
    Olaf Bootstraping Function
    """
    # TODO: Shouldn't all of this be in the registry?
    # Read All Modules
    modules = manifest_parser()
    sorted_modules = toposort_modules(modules)
    for module_name in sorted_modules:
        importlib.import_module(module_name)
    # At this point, all model classes should be loaded in the registry
    from olaf import registry
    from olaf.fields import Many2one
    # Populate Deletion Constraints
    for model, cls in registry.__models__.items():
        for attr_name in dir(cls):
            attr = getattr(cls, attr_name)
            if isinstance(attr, Many2one):
                comodel = attr._comodel_name
                constraint = attr._ondelete
                if comodel not in registry.__deletion_constraints__:
                    registry.__deletion_constraints__[comodel] = list()
                registry.__deletion_constraints__[comodel].append(
                    (model, attr_name, constraint))


def manifest_parser():
    """
    Parses all manifests files
    """

    file_name = "manifest.yml"
    mod_dir = os.path.join(os.path.dirname(
        os.path.abspath("olaf.py")), "olaf/addons")
    modules = dict()

    for root, dirs, _ in os.walk(mod_dir):
        for _dir in dirs:
            for file in os.listdir(os.path.join(root, _dir)):
                if file == file_name:
                    cur_dir = os.path.join(root, _dir)
                    _logger.debug(
                        "Parsing manifest file at {}".format(cur_dir))
                    manifest = yaml.safe_load(
                        open(os.path.join(cur_dir, file)))
                    modules["olaf.addons.{}".format(_dir)] = manifest
    return modules


def toposort_modules(modules):
    """ 
    Given a dictionary of type 
    {"module_name": (str_path, dict_manifest)}
    return list of modules sorted according to their 
    dependency on each other.
    """
    result = list()  # Contains sorted modules for installation
    indeps = list()  # Contains independent modules
    R = set()       # Contains all relations between modules

    # Build a set of each module relation (directed graph)
    for module_name, manifest in modules.items():
        if len(manifest["depends"]) == 0:
            indeps.append(module_name)
        else:
            for dep in manifest["depends"]:
                R.add((dep, module_name))

    while len(indeps) > 0:
        indep = indeps.pop(0)  # Get an element from indeps
        result.append(indep)
        for module_name, _ in modules.items():
            if module_name == indep:
                continue
            rels = [r for r in R if r[0] == indep and r[1] == module_name]
            if len(rels) > 0:
                for rel in rels:
                    R.remove(rel)
                if len([r for r in R if r[1] == module_name]) == 0:
                    indeps.append(module_name)

    if len(R) > 0:
        raise RuntimeError(
            "Denpendency loop detected - Involved modules: {}".format(", ".join([r[1] for r in R])))

    return result
