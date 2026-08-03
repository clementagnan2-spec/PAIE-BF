# -*- coding: utf-8 -*-
"""
storage.py
----------
Sauvegarde locale des données (paramètres, employés, comptes) dans un
fichier JSON situé dans le dossier utilisateur -- pas à côté du .exe, pour
que ça fonctionne même si le logiciel est installé dans "Program Files"
(dossier en lecture seule pour un utilisateur normal).

Emplacement Windows typique :
    C:\\Users\\<utilisateur>\\PaieBurkinaData\\donnees.json
"""

import json
import os
import copy

from payroll_engine import DEFAULT_PARAMS
import auth

APP_DIR_NAME = "PaieBurkinaData"
DATA_FILE_NAME = "donnees.json"


def get_data_dir() -> str:
    home = os.path.expanduser("~")
    path = os.path.join(home, APP_DIR_NAME)
    os.makedirs(path, exist_ok=True)
    return path


def get_data_path() -> str:
    return os.path.join(get_data_dir(), DATA_FILE_NAME)


def _default_config() -> dict:
    admin_salt, admin_hash = auth.hash_password("admin123")
    return {
        "entreprise": "Mon Entreprise",
        "admin_salt": admin_salt,
        "admin_hash": admin_hash,
        "secret_key": auth.new_secret_key(),
        "user_password_overrides": {},   # {"2026-08": "MOTDEPASSEFORCE"}
        "params": copy.deepcopy(DEFAULT_PARAMS),
        "employees": [],
        "next_numero": 1,
    }


def load() -> dict:
    path = get_data_path()
    if not os.path.exists(path):
        cfg = _default_config()
        save(cfg)
        return cfg
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # complète les clés manquantes si le fichier vient d'une version antérieure
    default = _default_config()
    for k, v in default.items():
        cfg.setdefault(k, v)
    return cfg


def save(config: dict) -> None:
    path = get_data_path()
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path)
