# -*- coding: utf-8 -*-
# Copyright 2019 Sergio Corato <https://github.com/sergiocorato>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
import os
import subprocess


def create_pip_requirements(self, version):
    self.start_odoo(version)
    modules = self.client.env['ir.module.module'].search_read([
        ('state', '=', 'installed')
    ], ['name'])
    self.modules = [x['name'] for x in modules]
    requirements = []
    for module in self.modules:
        odoo_modules = get_modules(self.venv_path, version)
        if module in odoo_modules:
            print('%s module in Odoo core' % module)
        else:
            if module not in requirements:
                requirements.append(module)
    file_new = False
    receipt = os.path.join(self.venv_path, 'requirements-%s.txt' % version)
    for req in requirements:
        if not file_new:
            subprocess.Popen(
                ['echo odoo%s-addon-%s > %s' % (
                     version.split('.')[0], req, receipt
                 )], shell=True)
            file_new = True
        else:
            subprocess.Popen(
                ['echo odoo%s-addon-%s >> %s' % (
                    version.split('.')[0], req, receipt
                 )], shell=True)
    self.stop_odoo()


def get_modules(venv_path, version):
    dir_path = '%s/openupgrade%s/odoo/addons/' % (venv_path, version)
    modules = list()
    for root, dirs, files in os.walk(dir_path, topdown=False):
        modules = dirs
        modules.append('base')
    return modules
