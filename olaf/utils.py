import yaml, os, logging, importlib

_logger = logging.getLogger(__name__)

def import_modules():
    modules = manifest_parser()
    sorted_modules = toposort_modules(modules)
    for module_name in sorted_modules:
        importlib.import_module(module_name)

def manifest_parser():
    """
    Parses all manifests files
    """

    file_name = "manifest.yml"
    mod_dir = os.path.join(os.path.dirname(os.path.abspath("olaf.py")), "olaf/addons")
    modules = dict()

    for root, dirs, _ in os.walk(mod_dir):
        for _dir in dirs:
            for file in os.listdir(os.path.join(root, _dir)):
                if file == file_name:
                    cur_dir = os.path.join(root, _dir)
                    _logger.debug("Parsing manifest file at {}".format(cur_dir))
                    manifest = yaml.safe_load(open(os.path.join(cur_dir, file)))
                    modules["olaf.addons.{}".format(_dir)] = manifest
    return modules

def toposort_modules(modules):
    """ 
    Given a dictionary of type 
    {"module_name": (str_path, dict_manifest)}
    return list of modules sorted according to their 
    dependency on each other.
    """
    result = list() # Contains sorted modules for installation
    indeps = list() # Contains independent modules
    R = set()       # Contains all relations between modules

    # Build a set of each module relation (directed graph)
    for module_name, manifest in modules.items():
        if len(manifest["depends"]) == 0:
            indeps.append(module_name)
        else:
            for dep in manifest["depends"]:
                R.add((dep, module_name))

    while len(indeps) > 0:
        indep = indeps.pop(0) # Get an element from indeps
        result.append(indep)
        for module_name, data in modules.items():
            if module_name == indep:
                continue
            rels = [r for r in R if r[0] == indep and r[1] == module_name]
            if len(rels) > 0:
                for rel in rels:
                    R.remove(rel)
                if len([r for r in R if r[1] == module_name]) == 0:
                    indeps.append(module_name)

    if len(R) > 0:
        raise RuntimeError("Denpendency loop detected - Involved modules: {}".format(", ".join([r[1] for r in R])))
    
    return result


                


    
            


        
