# Olaf

Olaf (**O**penObject-**L**ike **A**bstract **F**ramework) is a project inspired by Odoo's OpenObject framework.

Its key features are (WIP):
* Modularity
* Odoo-like syntax
* Built-in ODM (in replacement of Odoo's ORM)
* Users, groups and security access rules
* Native JSON-RPC support

## Requirements

- MongoDB (default parameters in `olaf/db.py`)

## Setup

Clone this repository and `cd` into it.
Then create a virtual environment like this:
```
python3 -m venv venv
```

Activate the virtual environment like this:
```
source venv/bin/activate
```

And then install the dependencies like this:
```
pip install -r requirements.txt
```