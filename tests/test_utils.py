import pytest
from olaf.utils import toposort_modules

def test_toposort_modules():

    # A disordered list of modules with dependencies
    # on each other.
    modules = {
        "mod_d": {"depends": ["mod_c"]},
        "mod_a": {"depends": []},
        "mod_e": {"depends": ["mod_b"]},
        "mod_g": {"depends": ["mod_f"]},
        "mod_h": {"depends": ["mod_f", "mod_a"]},
        "mod_b": {"depends": ["mod_a"]},
        "mod_c": {"depends": ["mod_a", "mod_b"]},
        "mod_f": {"depends": []},
    }

    # Test Topological Sort
    sorted_mods = toposort_modules(modules)
    assert(sorted_mods == ['mod_a', 'mod_f', 'mod_b', 'mod_g', 'mod_h', 'mod_e', 'mod_c', 'mod_d'])

    # Test dependency loop
    modules["mod_i"] = {"depends": ["mod_j"]}
    modules["mod_j"] = {"depends": ["mod_i"]}

    with pytest.raises(RuntimeError):
        toposort_modules(modules)