#!/usr/bin/env python3
import os
import yaml


def load_config(config, version):
    if not os.path.exists(config):
        local_path = os.path.join(os.path.expanduser('~'), 'Sviluppo', 'srvmngt',
                                  'openupgrader_config', config)
        if not os.path.exists(local_path):
            raise Exception('Unable to find configuration file: %s' % config)
        else:
            config = local_path

    with open(config, "r") as stream:
        try:
            repos = yaml.safe_load(stream) or {}
        except yaml.YAMLError as exc:
            print(exc)
    res = {}
    for repo in repos.get('repositories'):
        if repo.get('version') == version:
            res = repo.get('remotes')
    return res


def load_receipts(config):
    if not os.path.exists(config):
        local_path = os.path.join(os.path.expanduser('~'), 'Sviluppo', 'srvmngt',
                                  'openupgrader_config', config)
        if not os.path.exists(local_path):
            raise Exception('Unable to find receipts file: %s' % config)
        else:
            config = local_path

    with open(config, "r") as stream:
        try:
            repos = yaml.safe_load(stream) or {}
        except yaml.YAMLError as exc:
            print(exc)
    return repos

