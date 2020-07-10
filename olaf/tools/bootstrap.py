import yaml
import os
import logging
import importlib
import click
import sys
import csv
import bson
from . import config
from olaf.db import Connection
from olaf.http import route
from olaf.tools.environ import Environment

logger = logging.getLogger(__name__)
file_name = "manifest.yml"
root_uid = bson.ObjectId("000000000000000000000000")


def initialize():
    """
    Olaf Bootstraping Function
    """

    def load_deletion_constraints():
        """
        Routine for populating deletion constraints
        """
        from olaf import registry
        from olaf.fields import Many2one
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

    def load_module_data(module_name, module_data):
        """
        Routine for loading data from a given module into database
        """
        def load_data(env, fname, security=False):
            """
            Imports data from a file.
            - If file is in CSV format, then guess the model from the filename.
            First row represents columns, remaining rows represent the data matrix.
            """
            # Get filename from abs path
            base = os.path.basename(fname)
            # Split basename in (name, extension)
            split = os.path.splitext(base)

            fields = list()
            data = list()

            model = split[0] if not security else "base.model.access"
            with open(fname) as csv_file:
                csv_reader = csv.reader(csv_file, delimiter=",")
                first_line = True
                for row in csv_reader:
                    if first_line:
                        first_line = False
                        fields = [*row]
                    else:
                        data.append([*row])
                env[model].load(fields, data)


        def load_file_data(env, module_name, module_data):
            """
            Parses module data, gets filenames and calls loader function
            """
            # Get module status
            module = env.conn.db["base.module"].find_one({"name": module_name})

            if not module:
                result = env.conn.db["base.module"].insert_one(
                    {"name": module_name, "status": "pending"})
                module = env.conn.db["base.module"].find_one(
                    {"_id": result.inserted_id})

            if module["status"] == "pending":
                if "data" in module_data["manifest"]:
                    for _file in module_data["manifest"]["data"]:
                        fname = os.path.join(
                            module_data["path"], module_name, _file)
                        logger.debug(
                            "Loading data file '{}' for module '{}'".format(_file, module_name))
                        load_data(env, fname)
                if "security" in module_data["manifest"]:
                    for _file in module_data["manifest"]["security"]:
                        fname = os.path.join(
                            module_data["path"], module_name, _file)
                        logger.debug(
                            "Loading security file '{}' for module '{}'".format(_file, module_name))
                        load_data(env, fname, True)

                # Flag module as installed
                env.conn.db["base.module"].update_one(
                    {"name": module_name}, {"$set": {"status": "installed"}})

        conn = Connection()
        client = conn.cl

        if config.DB_REPLICASET_ENABLE:
            with client.start_session() as session:
                with session.start_transaction():
                    # Create environment with session
                    env = Environment(root_uid, session)
                    load_file_data(env, module_name, module_data)
        else:
            # Create environment without session (MongoDB transactions disabled)
            env = Environment(root_uid)
            load_file_data(env, module_name, module_data)

    # Read All Modules
    color = click.style
    logger.info(color("Initializing Olaf", fg="white", bold=True))
    # Ensure root user exists
    ensure_root_user()
    modules = manifest_parser()
    sorted_modules = toposort_modules(modules)
    logger.info("Importing Modules")
    for module_name in sorted_modules:
        if modules[module_name]["base"]:
            importlib.import_module("olaf.addons.{}".format(module_name))
        else:
            sys.path.append(modules[module_name]["path"])
            importlib.import_module(module_name)
        # Import Module Data
        load_module_data(module_name, modules[module_name])
    # At this point, all model classes should be loaded in the registry
    load_deletion_constraints()
    # Generate route map
    route.build_url_map()
    logger.info(color("System Ready", fg="white", bold=True))


def manifest_parser():
    """
    Parses all manifest files in the base dir,
    then all manifest files in the extra addons
    dirs passed by the EXTRA_ADDONS setting.
    """
    logger.info("Parsing Manifests")

    modules = dict()
    # Search for modules in olaf/addons first
    base_dir = os.path.join(os.path.dirname(
        os.path.abspath("olaf.py")), "olaf/addons")

    scan_addons_dir(base_dir, modules, base=True)

    # Search for modules in each EXTRA_ADDONS folder
    from . import config
    extra_addons_dirs = config.EXTRA_ADDONS.split(",")
    for extra_addons_dir in extra_addons_dirs:
        scan_addons_dir(extra_addons_dir, modules)

    return modules


def scan_addons_dir(addons_dir, modules_dict, base=False):
    """
    Search for manifest files in the root of
    each directory inside the provided addons directory.
    If a manifest file is found, load its contents into the
    provided dictionary.
    """
    for root, dirs, _ in os.walk(addons_dir):
        for _dir in dirs:
            path = os.path.basename(_dir)
            for file in os.listdir(os.path.join(root, _dir)):
                if file == file_name:
                    # Absolute path to directory
                    cur_dir = os.path.join(root, _dir)
                    logger.debug(
                        "Parsing Manifest File at {}".format(cur_dir))
                    manifest = yaml.safe_load(
                        open(os.path.join(cur_dir, file)))
                    modules_dict[path] = {
                        "manifest": manifest,
                        "path": addons_dir,
                        "base": base}


def toposort_modules(modules):
    """ 
    Given a dictionary of type 
    {"module_name": (str_path, dict_manifest)}
    return list of modules sorted according to their 
    dependency on each other.
    """
    logger.info("Building Dependency Tree")

    result = list()  # Contains sorted modules for installation
    indeps = list()  # Contains independent modules
    R = set()        # Contains all relations between modules

    # Build a set of each module relation (directed graph)
    for module_name, data in modules.items():
        manifest = data["manifest"]
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


def ensure_root_user():
    """ Create root user if it doesn't exist,
    or ensure its password matches the one
    specified through the environment variables.
    """
    from olaf.tools import config
    from olaf.db import Connection
    from bson import ObjectId
    from werkzeug.security import generate_password_hash

    # Generate hashed password
    passwd = generate_password_hash(config.ROOT_PASSWORD)

    conn = Connection()
    root = conn.db["base.user"].find_one({"_id": root_uid})

    if not root:
        # Create root user
        logger.warning("Root user is not present, creating...")
        conn.db["base.user"].insert_one(
            {"_id": root_uid, "name": "root", "email": "root", "password": passwd})
    else:
        # Update root user's password
        logger.info("Overwriting root user password")
        conn.db["base.user"].update_one({"_id": root_uid}, {
                                        "$set": {"name": "root", "email": "root", "password": passwd}})
