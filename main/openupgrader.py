#!/usr/bin/env python3
# Copyright 2019 Sergio Corato <https://github.com/sergiocorato>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import odooly
import subprocess
import time
import os
import signal
from main import config
from main import requirements


class Connection:
    def __init__(self, db, user, password, db_port='5432'):
        """
        PROCEDURA:
        copiare nella cartella ~ i file:
        database.gz [file creato con pg_dump [database] | gzip > database.gz
        e filestore.tar [file creato con tar -cvzf filestore.tar ./filestore
        e lanciare con
        import openupgrader
        mig = openupgrader.Connection('db', 'amministratore_db', 'pw_db', '5435')
        mig.do_migration(from_version=[], to_version=[])
        mig.do_migration('8.0', '9.0', restore_db_update=True, filestore=True)
        mig.do_migration('9.0', '10.0', filestore=True)
        mig.do_migration('10.0', '11.0', filestore=True)
        mig.do_migration('11.0', '12.0', filestore=True)
        n.b.: per il momento è supportata solo la migrazione di 1 versione per
        volta
        :param db: il database da migrare (il nuovo nome)
        :param user: l'utente amministrativo
        :param password: la password dell'utente amministrativo
        :param db_port: la porta del database su cui la funzione andra a
        cancellare e ripristinare il database da migrare
        xmlrpc_port: la porta su cui è accessibile il servizio - viene
        impostata come 80 + i due numeri finali della porta del db
        n.b. non deve essere in uso da altre istanze
        n.b. per comodità ho creato dei cluster di postgres 11 con le porte 5439-40-41
        in mancanza va con il postgres di default nella porta indicata
        troubleshooting:
        per correggere il problema
        can't find '__main__' module in '/usr/share/python-wheels/pep517-0.8.2-py2.py3
        -none-any.whl/pep517/_in_process.py'
        e altri, ho forzato la reinstallazione delle varie librerie
        ../bin/pip install --force-reinstall -r requirements.txt
        """
        self.db = db
        self.user = user
        self.password = password
        self.pid = False
        self.db_port = db_port
        self.xmlrpc_port = '80%s' % self.db_port[-2:]
        self.path_name = self.db
        self.path = os.path.expanduser('~')
        self.venv_path = os.path.join(self.path, 'tmp_venv')
        self.pg_bin_path = '/usr/lib/postgresql/11/bin/' if self.db_port in [
            '5439', '5440', '5441'] else ''
        self.receipts = config.load_receipts('openupgrade_config.yml')

    def odoo_connect(self):
        self.client = odooly.Client(
            server='http://localhost:%s' % self.xmlrpc_port,
            db=self.db,
            user=self.user,
            password=self.password,
        )
        time.sleep(5)

    def start_odoo(self, version, update=False, migrate=True):
        """
        :param version: odoo version to start (8.0, 9.0, 10.0, ...)
        :param update: if True odoo will be updated with -u all and stopped
        :param migrate: if True start odoo with openupgrade repo
        :return: odoo instance in self.client if not updated, else nothing
        """
        venv_path = '%s/%s%s' % (
            self.venv_path, 'openupgrade' if migrate else 'standard',
            version)
        load = 'web'
        if version == '10.0':
            load = 'web,web_kanban'
        if version in ['12.0', '13.0', '14.0']:
            load = 'base,web'
        if version == '14.0' and update:
            load = 'base,web,openupgrade_framework'
        executable = 'openerp-server' if version in ['7.0', '8.0', '9.0'] else 'odoo'
        bash_command = "bin/%s " \
                       "--db_port=%s --xmlrpc-port=%s " \
                       "--logfile=%s/migration.log " \
                       "--limit-time-cpu=600 --limit-time-real=1200 "\
                       "--addons-path=" \
                       "%s" \
                       "%s/addons-extra" \
                       "%s%s " \
                       "--load=%s " % (
                        executable,
                        self.db_port, self.xmlrpc_port,
                        venv_path,
                        ("%s/odoo/addons," % venv_path if version in [
                            '8.0', '9.0', '10.0', '11.0', '12.0', '13.0'] else ''),
                        venv_path,
                        (',%s/odoo/odoo/addons' % venv_path if version in [
                            '10.0', '11.0', '12.0', '13.0'] else ''),
                        (',%s/odoo/openupgrade_scripts,%s/odoo/openupgrade_framework'
                         % (venv_path, venv_path) if version not in [
                            '8.0', '9.0', '10.0', '11.0', '12.0', '13.0'] else ''),
                        load)
        cwd_path = '%s/' % venv_path
        if version != '7.0':
            bash_command += "--data-dir=%s/data_dir " % venv_path
        if update:
            bash_command += " -u all -d %s --stop-after-init" % self.db
        process = subprocess.Popen(
            bash_command.split(), stdout=subprocess.PIPE, cwd=cwd_path)
        self.pid = process.pid
        if update:
            process.wait()
        else:
            time.sleep(15)
            self.odoo_connect()
        time.sleep(5)

    def stop_odoo(self):
        if self.pid:
            os.kill(self.pid, signal.SIGTERM)
            time.sleep(5)

    def disable_mail(self, disable=False):
        state = 'draft' if disable else 'done'
        active = 'false' if disable else 'true'
        bash_commands = [
            'update fetchmail_server set state = \'%s\';' % state,
            'update ir_mail_server set active = %s;' % active,
        ]
        for bash_command in bash_commands:
            process = subprocess.Popen(
                ['psql -p %s -d %s -c "%s"' % (
                    self.db_port, self.db, bash_command)],
                shell=True)
            process.wait()

    def dump_database(self, version):
        pg_bin_path = self.pg_bin_path
        process = subprocess.Popen(
            ['%spg_dump -O -p %s -d %s | gzip > %s/database.%s.gz' % (
                 pg_bin_path, self.db_port, self.db, self.venv_path, version
             )], shell=True)
        process.wait()

    def restore_filestore(self, from_version, to_version):
        dump_file = os.path.join(self.path, 'filestore.tar')
        if os.path.isfile(dump_file):
            process = subprocess.Popen(
                ['mv %s %s/filestore.%s.tar' % (
                    dump_file, self.venv_path, from_version)], shell=True)
            process.wait()
        dump_file = os.path.join(
            self.venv_path, 'filestore.%s.tar' % from_version)
        filestore_path = '%s/openupgrade%s/data_dir/filestore' % (
            self.venv_path, to_version)
        if not os.path.isdir(filestore_path):
            process = subprocess.Popen([
                'mkdir -p %s' % filestore_path], shell=True)
            process.wait()
        process = subprocess.Popen([
            'tar -zxvf %s -C %s/openupgrade%s/data_dir/filestore/' % (
                dump_file, self.venv_path, to_version)], shell=True)
        process.wait()

    def dump_filestore(self, version):
        process = subprocess.Popen([
            'cd %s/openupgrade%s/data_dir/filestore && '
            'tar -zcvf %s/filestore.%s.tar %s' % (
                self.venv_path, version, self.venv_path, version, self.db)
        ], shell=True)
        process.wait()

    def restore_db(self, from_version):
        pg_bin_path = self.pg_bin_path
        process = subprocess.Popen(
            ['%sdropdb -p %s %s' % (pg_bin_path, self.db_port, self.db)],
            shell=True)
        process.wait()
        process = subprocess.Popen(
            ['%screatedb -p %s %s' % (
                pg_bin_path, self.db_port, self.db)], shell=True)
        process.wait()
        dump_file = os.path.join(self.path, 'database.gz')
        if os.path.isfile(dump_file):
            process = subprocess.Popen(
                ['mv %s %s/database.%s.gz' % (
                    dump_file, self.venv_path, from_version)], shell=True)
            process.wait()
        dump_file = os.path.join(
            self.venv_path, 'database.%s.gz' % from_version)

        process = subprocess.Popen(
            ['cat %s | gunzip | %spsql -U $USER -p %s -d %s ' % (
                dump_file, pg_bin_path, self.db_port, self.db)], shell=True)
        process.wait()

    # MASTER function #####
    def do_migration(self, from_version, to_version, restore_db_update=False,
                     restore_db_only=False, filestore=False, create_venv=True):
        to_branch = to_version if len(to_version) > 4 else False
        to_version = to_version[:4]
        if create_venv:
            self.create_venv_git_version(to_version, to_branch, openupgrade=True)
        # FIXME NB.: Per i test di migrazione alla 10.0 rimosso il compute da
        #  /tmp_venv/openupgrade10.0/odoo/addons/product/models$ cat product_template.py
        #  altrimenti ci mette ore
        # self.create_venv_git_version(from_version, openupgrade=True)
        if restore_db_update:
            # STEP1: create venv for current version to fix it
            self.create_venv_git_version(from_version, openupgrade=True)
            if filestore:
                self.restore_filestore(from_version, from_version)
            self.restore_db(from_version)
            self.disable_mail(disable=True)
            # n.b. when updating, at the end odoo service is stopped
            self.start_odoo(from_version, update=True)
        # restore db if not restored before, not needed if migration for more version
        elif restore_db_only:
            self.restore_db(from_version)
        if filestore:
            self.restore_filestore(from_version, to_version)
        self.disable_mail(disable=True)
        self.sql_fixes(self.receipts[from_version])
        # DO MIGRATION to next version ###
        self.auto_install_modules(from_version)
        self.uninstall_modules(from_version, before_migration=True)
        self.delete_old_modules(from_version)
        if to_version == '11.0':
            self.fix_taxes(from_version)
        if to_version == '12.0' and 'mac' in self.db:
            self.migrate_bank_riba_id_bank_ids(from_version)
            self.migrate_bank_riba_id_bank_ids_invoice(from_version)
        self.start_odoo(to_version, update=True)
        self.auto_install_modules(to_version)
        self.uninstall_modules(to_version, after_migration=True)
        self.sql_fixes(self.receipts[to_version])
        if to_version == '10.0':
            self.start_odoo(to_version)
            self.remove_modules('upgrade')
            self.remove_modules()
            self.install_uninstall_module('l10n_it_intrastat')
            self.stop_odoo()
        self.dump_database(to_version)
        if filestore:
            self.dump_filestore(to_version)
        if to_version in ['10.0', '11.0', '12.0']:
            requirements.create_pip_requirements(self, to_version)

    def fix_taxes(self, version):
        # correzione da fare sulle imposte prima della migrazione alla v.11.0 altrimenti
        # non può calcolare correttamente le ex-imposte parzialmente deducibili
        self.start_odoo(version)
        tax_obj = self.client.env['account.tax']
        for tax in tax_obj.search([
            ('children_tax_ids', '!=', False),
            ('amount_type', '=', 'group'),
        ]):
            first_child_amount = 0.0
            print('Fixed tax %s' % tax.name)
            for child_tax in tax.children_tax_ids:
                child_tax.amount_type = 'percent'
                if child_tax.amount == 0.0:
                    child_tax.amount = (tax.amount * 100) - first_child_amount
                else:
                    child_tax.amount = tax.amount * child_tax.amount
                first_child_amount = child_tax.amount
                print('Fixed child tax %s' % child_tax.name)
        self.stop_odoo()

    def migrate_bank_riba_id_bank_ids(self, version):
        self.start_odoo(version)
        partners = self.client.env['res.partner'].search([
            ('bank_riba_id', '!=', False)
        ])
        for partner in partners:
            bank_found = False
            if partner.bank_ids:
                for bank in partner.bank_ids:
                    bank.sequence = 10
                for bank in partner.bank_ids:
                    if bank.bank_abi == partner.bank_riba_id.abi and \
                            bank.bank_cab == partner.bank_riba_id.cab:
                        bank_found = True
                        bank.sequence = 0
                        print('La banca è corretta per il partner %s' % partner.name)
                        break
            if not bank_found:
                print('Creata banca mancante per il partner %s' % partner.name)
                partner.write({
                    'bank_ids': [(0, 0, {
                        'sequence': 0,
                        'acc_number': ''.join([str(partner.id),
                                               str(partner.bank_riba_id.abi),
                                               str(partner.bank_riba_id.cab),
                                               partner.bank_riba_id.name[:10]]),
                        'bank_id': partner.bank_riba_id.id,
                        'bank_abi': partner.bank_riba_id.abi,
                        'bank_cab': partner.bank_riba_id.cab,
                    })]
                })
        self.stop_odoo()

    def migrate_bank_riba_id_bank_ids_invoice(self, version):
        self.start_odoo(version)
        invoices = self.client.env['account.invoice'].search([
            ('bank_riba_id', '!=', False)
        ])
        for invoice in invoices:
            # trovo con abi e cab di bank_riba_id la res.partner.bank corretta
            partner_bank = self.client.env['res.partner.bank'].search([
                ('bank_abi', '=', invoice.bank_riba_id.abi),
                ('bank_cab', '=', invoice.bank_riba_id.cab),
                ('partner_id', '=', invoice.partner_id.id),
            ])
            if partner_bank:
                partner_bank = partner_bank[0]
                if invoice.partner_bank_id \
                        and invoice.partner_bank_id.bank_abi == partner_bank.bank_abi \
                        and invoice.partner_bank_id.bank_cab == partner_bank.bank_cab:
                    print('La banca è corretta per la fattura %s' % invoice.number)
                else:
                    print('Banca aggiornata in fattura %s da %s a %s' % (
                        invoice.number,
                        invoice.partner_bank_id and invoice.partner_bank_id.acc_number or '',
                        partner_bank.acc_number))
                    invoice.write({
                        'partner_bank_id': partner_bank.id,
                    })
            else:
                print('Banca non trovata per fattura %s' % invoice.number)
                new_partner_bank = self.client.env['res.partner.bank'].create({
                    'sequence': 0,
                    'partner_id': invoice.partner_id.id,
                    'acc_number': ''.join([str(invoice.partner_id.id),
                                           str(invoice.bank_riba_id.abi),
                                           str(invoice.bank_riba_id.cab),
                                           invoice.bank_riba_id.name[:10]]),
                    'bank_id': invoice.bank_riba_id.id,
                    'bank_abi': invoice.bank_riba_id.abi,
                    'bank_cab': invoice.bank_riba_id.cab,
                })
                invoice.write({
                    'partner_bank_id': new_partner_bank.id,
                })
        self.stop_odoo()

    def sql_fixes(self, receipt):
        for part in receipt:
            bash_commands = part.get('sql_commands', [])
            for bash_command in bash_commands:
                command = ["psql -p %s -d %s -c \'%s\'"
                           % (self.db_port, self.db, bash_command)]
                subprocess.Popen(command, shell=True).wait()
            bash_update_commands = part.get('sql_update_commands', [])
            if bash_update_commands:
                for bash_update_command in bash_update_commands:
                    upd_command = ['psql -p %s -d %s -c "%s"'
                                   % (self.db_port, self.db, bash_update_command)]
                    subprocess.Popen(upd_command, shell=True).wait()

    def post_migration(self, version):
        # re-enable mail servers and clean db
        self.disable_mail(disable=False)
        self.database_cleanup(version)

    def create_venv_git_version(self, version, branch=False, openupgrade=False):
        venv_path = '%s/%s%s' % (
            self.venv_path, 'openupgrade' if openupgrade else 'standard',
            version)
        py_version = '2.7' if version in ['7.0', '8.0', '9.0', '10.0'] \
            else '3.5' if version == '11.0' else '3.7'
        odoo_repo = 'https://github.com/OCA/OCB.git'
        if openupgrade:
            odoo_repo = 'https://github.com/sergiocorato/OpenUpgrade.git'
        if not os.path.isdir(venv_path):
            subprocess.Popen(['mkdir -p %s' % venv_path], shell=True).wait()
            # do not recreate virtualenv as it regenerate file with bug in split()
            # ../openupgrade10.0/lib/python2.7/site-packages/pip/_internal/vcs/git.py
            subprocess.Popen([
                'virtualenv -p /usr/bin/python%s %s' % (py_version, venv_path)],
                cwd=venv_path, shell=True).wait()
        if not os.path.isdir(os.path.join(venv_path, 'odoo')):
            subprocess.Popen([
                'cd %s && git clone --single-branch %s -b %s --depth 1 odoo' % (
                    venv_path, odoo_repo, branch or version)],
                cwd=venv_path, shell=True).wait()
        elif branch:
            subprocess.Popen(['cd %s/odoo && git reset --hard origin/%s && git pull '
                              'origin %s' % (
                                  venv_path, version, branch)],
                             cwd=venv_path, shell=True).wait()
        else:
            subprocess.Popen(['cd %s/odoo && git reset --hard origin/%s && git pull '
                              '&& git reset --hard origin/%s' % (
                              venv_path, version, version)],
                             cwd=venv_path, shell=True).wait()
        commands = [
            'bin/pip install "setuptools<58.0.0"',
            'bin/pip install -r odoo/requirements.txt',
            'cd odoo && ../bin/pip install -e . ' if version in [
                '8.0', '9.0', '10.0', '11.0', '12.0', '13.0'
            ] else 'cd repos/odoo && ../../bin/pip install -e . ',
        ]
        for command in commands:
            subprocess.Popen(command, cwd=venv_path, shell=True).wait()
        extra_paths = ['%s/addons-extra' % venv_path,
                       '%s/repos' % venv_path]
        for path in extra_paths:
            if not os.path.isdir(path):
                process = subprocess.Popen(
                    'mkdir %s' % path, cwd=venv_path, shell=True)
                process.wait()
        if os.path.isfile(os.path.join(venv_path, 'migration.log')):
            process = subprocess.Popen(
                'rm %s' % 'migration.log', cwd=venv_path, shell=True)
            process.wait()
        repos = config.load_config('openupgrade_repos.yml', version)
        for repo_name in repos:
            repo_text = repos.get(repo_name)
            repo = repo_text.split(' ')[0]
            repo_version = repo_text.split(' ')[1]
            if not os.path.isdir('%s/repos/%s' % (venv_path, repo_name)):
                process = subprocess.Popen([
                    'git clone %s --single-branch -b %s --depth 1 '
                    '%s/repos/%s'
                    % (repo, repo_version, venv_path, repo_name)
                ], cwd=venv_path, shell=True)
                process.wait()
            process = subprocess.Popen([
                'cd %s/repos/%s '
                '&& git remote set-branches --add origin %s '
                '&& git fetch '
                '&& git checkout origin/%s' % (
                    venv_path, repo_name,
                    repo_version,
                    repo_version)
            ], cwd=venv_path, shell=True)
            process.wait()
            # copy modules to create an unique addons path
            for root, dirs, files in os.walk(
                    '%s/repos/%s/' % (venv_path, repo_name)):
                for d in dirs:
                    if d not in ['.git', 'setup']:
                        process = subprocess.Popen([
                            "cp -rf %s/repos/%s/%s %s/addons-extra/" %(
                                venv_path, repo_name, d,
                                venv_path)
                        ], cwd=venv_path, shell=True)
                        process.wait()
                break

    def database_cleanup(self, to_version):
        self.start_odoo(to_version)
        self.remove_modules()
        self.remove_modules('upgrade')
        self.client.env.install('database_cleanup')
        for model in [
            'cleanup.purge.wizard.module',
            'cleanup.purge.wizard.model',
            'cleanup.purge.wizard.column',
            'cleanup.purge.wizard.data',
            'cleanup.purge.wizard.property'
        ]:
            try:
                self.database_cleanup_wizard(model)
            except Exception:
                pass
        module_id = self.client.env['ir.module.module'].search([
            ('name', '=', 'database_cleanup')])
        module_id.write({'state': 'to remove'})
        self.client.env.upgrade()
        self.stop_odoo()

    def database_cleanup_wizard(self, model):
        wizard = self.client.env[model]
        purge_obj = self.client.env['cleanup.purge.line.module']
        try:
            configuration = wizard.default_get(list(wizard.fields_get()))
        except Exception:
            return
        if not configuration:
            return
        try:
            wiz_id = wizard.create(configuration)
        except Exception:
            return
        if model == 'cleanup.purge.wizard.column':
            purge_line_ids = [x.id for x in wiz_id.purge_line_ids
                              if x.name not in ['openupgrade_legacy_9_0_help',
                                                'openupgrade_legacy_9_0_type',
                                                'openupgrade_legacy_11_0_usage']]
            if purge_line_ids:
                original_purge_line_ids = [x.id for x in wiz_id.purge_line_ids
                                           if id not in purge_line_ids]
                wiz_id.purge_line_ids = purge_obj.browse(purge_line_ids)
                res = wiz_id.purge_all()
                print(res)
                wiz_id.purge_line_ids = purge_obj.browse(
                    original_purge_line_ids)
        res1 = wiz_id.purge_all()
        print(res1)

    def auto_install_modules(self, version):
        self.start_odoo(version)
        module_obj = self.client.env['ir.module.module']
        if version == '12.0':
            self.remove_modules('upgrade')
        receipt = self.receipts[version]
        for modules in receipt:
            module_list = modules.get('auto_install', False)
            if module_list:
                for module_pair in module_list:
                    module_to_check = module_pair.split(' ')[0]
                    module_to_install = module_pair.split(' ')[1]
                    if module_obj.search([
                            ('name', '=', module_to_check),
                            ('state', '=', 'installed')]):
                        self.client.env.install(module_to_install)
        self.stop_odoo()

    def uninstall_modules(self, version, before_migration=False, after_migration=False):
        self.start_odoo(version)
        if version == '12.0':
            self.remove_modules('upgrade')
        receipt = self.receipts[version]
        for modules in receipt:
            if after_migration:
                modules_to_uninstall = modules.get('uninstall_after_migration', False)
                if modules_to_uninstall:
                    for module in modules_to_uninstall:
                        self.install_uninstall_module(module, install=False)
            if before_migration:
                modules_to_uninstall = modules.get('uninstall_before_migration', False)
                if modules_to_uninstall:
                    for module in modules_to_uninstall:
                        self.install_uninstall_module(module, install=False)
        self.stop_odoo()

    def delete_old_modules(self, version):
        receipt = self.receipts[version]
        if [modules.get('delete', False) for modules in receipt]:
            self.start_odoo(version)
            module_obj = self.client.env['ir.module.module']
            for modules in receipt:
                module_list = modules.get('delete', False)
                if module_list:
                    for module in module_list:
                        module = module_obj.search([
                            ('name', '=', module)])
                        if module:
                            module_obj.unlink(module.id)
            self.stop_odoo()

    def remove_modules(self, module_state=''):
        if module_state == 'upgrade':
            state = ['to upgrade', ]
        else:
            state = ['to remove', 'to install']
        module_obj = self.client.env['ir.module.module']
        modules = module_obj.search([('state', 'in', state)])
        msg_modules = ''
        msg_modules_after = ''
        if modules:
            msg_modules = str([x.name for x in modules])
        for module in modules:
            module.button_uninstall_cancel()
        modules_after = module_obj.search(
            [('state', '=', 'to upgrade')])
        if modules_after:
            msg_modules_after = str([x.name for x in modules_after])
        print('Modules: %s' % msg_modules)
        print('Modules after: %s' % msg_modules_after)

    def install_uninstall_module(self, module, install=True):
        module_obj = self.client.env['ir.module.module']
        to_remove_modules = module_obj.search(
            [('state', '=', 'to remove')])
        for module_to_remove in to_remove_modules:
            module_to_remove.button_uninstall_cancel()
        state = self.client.env.modules(module)
        if state:
            if install:
                self.client.env.install(module)
            elif state.get('installed', False) or state.get('to upgrade', False)\
                    or state.get('uninstallable'):
                module_id = module_obj.search([('name', '=', module)])
                if module_id:
                    try:
                        module_id.button_immediate_uninstall()
                        print('Module %s uninstalled' % module)
                        module_id.unlink()
                    except Exception as e:
                        print('Module %s not uninstalled for %s' % (module, e))
                        pass
                else:
                    print('Module %s not found' % module)