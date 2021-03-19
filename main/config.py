#!/usr/bin/env python3
import os
import kaptan


def load_config(config, version):
    if not os.path.exists(config):
        local_path = os.path.join(os.path.expanduser('~'), 'Sviluppo', 'srvmngt',
                                  'openupgrader_config', config)
        if not os.path.exists(local_path):
            raise Exception('Unable to find configuration file: %s' % config)
        else:
            config = local_path

    file_extension = os.path.splitext(config)[1][1:]
    conf = kaptan.Kaptan(handler=kaptan.HANDLER_EXT.get(file_extension))

    conf.import_config(config)
    repos = conf.export('dict') or {}
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

    file_extension = os.path.splitext(config)[1][1:]
    conf = kaptan.Kaptan(handler=kaptan.HANDLER_EXT.get(file_extension))

    conf.import_config(config)
    repos = conf.export('dict') or {}
    return repos
