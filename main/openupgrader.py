#!/usr/bin/env python3
# Copyright 2019 Sergio Corato <https://github.com/sergiocorato>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import odooly
import shutil
import subprocess
import time
import os
import signal
from main import config
from main import openupgrade_fixes

versions = {
    '7.0': '8.0',
    '8.0': '9.0',
    '9.0': '10.0',
    '10.0': '11.0',
    '11.0': '12.0',
    '12.0': '13.0',
    '13.0': '14.0',
    '14.0': '15.0',
    '15.0': '16.0',
}


class Connection:
    def __init__(self, db, user, password, db_port='5432'):
        """
        PROCEDURA:
        copiare nella cartella ~ i file:
        database.gz [file creato con pg_dump [database] | gzip > database.gz
        e filestore.tar [file creato con tar -cvzf filestore.tar ./filestore
        oppure
        database.sql e cartella del filestore [estratti da auto_backup]
        e lanciare con
        import openupgrader
        mig = openupgrader.Connection('db', 'amministratore_db', 'pw_db', '5435')
        mig.init_migration(from_version=8.0, to_version=9.0, restore_db_update=True,
         filestore=True)
        in seguito lanciare i comandi seguenti ripetutamente per ogni versione
        mig.prepare_migration()
        mig.do_migration()
        oppure
        mig.prepare_do_migration()
        n.b.: per il momento è supportata solo la migrazione di 1 versione per volta
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
        self.fixes = openupgrade_fixes.Fixes()
        self.from_version = False
        self.to_version = False
        self.restore_db_update = False
        self.restore_db_only = False
        self.create_venv = False
        self.filestore = False
        self.fix_banks = False
        self.migrate_ddt = False
        self.repos = False
        self.client = False

    def odoo_connect(self):
        self.client = odooly.Client(
            server='http://localhost:%s' % self.xmlrpc_port,
            db=self.db,
            user=self.user,
            password=self.password,
        )
        time.sleep(5)

    def start_odoo(self, version, update=False, openupgrade_folder=True,
                   extra_command='', save=False):
        """
        :param version: odoo version to start (8.0, 9.0, 10.0, ...)
        :param update: if True odoo will be updated with -u all and stopped
        :param openupgrade_folder: if True create odoo in a folder openupgrade, else
         standard
        :param extra_command: command that will be passed after executable
        :param save: if True save .odoorc and stop Odoo
        :return: Odoo instance in "self.client" if not updated, else nothing
        """
        venv_path = '%s/%s%s' % (
            self.venv_path, 'openupgrade' if openupgrade_folder else 'standard',
            version)
        load = 'web'
        if version == '10.0':
            load = 'web,web_kanban'
        if version not in ['7.0', '8.0', '9.0', '10.0', '11.0']:
            load = 'base,web'
        if version not in [
            '7.0', '8.0', '9.0', '10.0', '11.0', '12.0', '13.0'
        ]:
            load += ',openupgrade_framework,module_change_auto_install'
        executable = 'openerp-server' if version in ['7.0', '8.0', '9.0']\
            else 'odoo'
        odoorc_exist = bool(
            os.path.isfile(
                os.path.join(venv_path, '.odoorc')
            )
            and not self.migrate_ddt
        )
        addons_path = f'{venv_path}/repos/odoo/addons,'
        if version in ['8.0', '9.0', '10.0', '11.0', '12.0', '13.0']:
            addons_path = f"{venv_path}/odoo/addons,"
        extra_addons_path = \
            f',{venv_path}/repos/odoo/odoo/addons,{venv_path}/odoo'
        if version in ['10.0', '11.0', '12.0', '13.0']:
            extra_addons_path = f',{venv_path}/odoo/odoo/addons'
        bash_command = \
            f"bin/{executable} " \
            f"{'-c .odoorc' if odoorc_exist else ''} " \
            f"{not odoorc_exist and f'--addons-path={addons_path}' or ''}" \
            f"{not odoorc_exist and f'{venv_path}/addons-extra' or ''}" \
            f"{not odoorc_exist and extra_addons_path or ''} " \
            f"{extra_command} " \
            f"--db_port={self.db_port} --xmlrpc-port={self.xmlrpc_port} " \
            f"--logfile={venv_path}/migration.log " \
            f"{not odoorc_exist and '--limit-time-cpu=1600' or ''} " \
            f"{not odoorc_exist and '--limit-time-real=3200' or ''} " \
            f"{not odoorc_exist and '--limit-memory-soft=4147483648' or ''} " \
            f"{not odoorc_exist and '--limit-memory-hard=4679107584' or ''} " \
            f"--load={load} "
        cwd_path = '%s/' % venv_path
        if version != '7.0':
            bash_command += "--data-dir=%s/data_dir " % venv_path
        if update:
            bash_command += " -u all -d %s --stop" % self.db
        if save:
            bash_command += " -s --stop"
        process = subprocess.Popen(
            bash_command.split(), stdout=subprocess.PIPE, cwd=cwd_path)
        self.pid = process.pid
        if update or extra_command:
            process.wait()
        else:
            time.sleep(15)
            if not save:
                self.odoo_connect()
            else:
                not_auto_install_list = [
                    "partner_autocomplete", "iap", "mail_bot", "account_edi",
                    "account_edi_facturx", "account_edi_ubl", "l10n_it_stock_ddt"
                ]
                mod_not_install = \
                    f"modules_auto_install_disabled = {','.join(not_auto_install_list)}"
                subprocess.Popen(
                    ['mv ~/.odoorc ./'], shell=True, cwd=cwd_path
                ).wait()
                subprocess.Popen(
                    [f'sed -i "s/^osv_memory_age_limit.*/{mod_not_install}/g" .odoorc'],
                    shell=True, cwd=cwd_path
                ).wait()
        time.sleep(5)

    def stop_odoo(self):
        if self.pid:
            os.kill(self.pid, signal.SIGTERM)
            time.sleep(10)
            os.kill(self.pid, signal.SIGTERM)

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
        filestore_path = os.path.join(
            self.venv_path, f'openupgrade{to_version}', 'data_dir', 'filestore'
        )
        if not os.path.isdir(filestore_path):
            os.makedirs(filestore_path, exist_ok=True)
        dump_folder = os.path.join(self.path, 'filestore')
        dump_file = os.path.join(self.path, 'filestore.tar')
        if os.path.isdir(dump_folder):
            process = subprocess.Popen([
                f'tar -zcvf {self.venv_path}/filestore.{from_version}.tar filestore'
            ], shell=True, cwd=self.path)
            process.wait()
            shutil.rmtree(dump_folder)
        elif os.path.isfile(dump_file):
            os.rename(dump_file, f'{self.venv_path}/filestore.{from_version}.tar')
        dump_file = os.path.join(
            self.venv_path, f'filestore.{from_version}.tar')
        filestore_db_path = os.path.join(
            filestore_path, self.db
        )
        if not os.path.isdir(filestore_db_path):
            os.mkdir(filestore_db_path)
        process = subprocess.Popen([
            f'tar -zxvf {dump_file} --strip-components=1 -C {filestore_db_path}/'
        ], shell=True)
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
        if not os.path.isfile(dump_file):
            dump_file_sql = os.path.join(self.path, 'database.sql')
            if os.path.isfile(dump_file_sql):
                subprocess.Popen([
                    'gzip -c %s > %s' % (
                        dump_file_sql, dump_file)
                ], shell=True).wait()
                os.unlink(dump_file_sql)
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
    def init_migration(self, from_version, to_version, restore_db_update=False,
                       restore_db_only=False, filestore=False, create_venv=True,
                       fix_banks=False, migrate_ddt=False):
        self.from_version = from_version
        self.to_version = to_version[:4]
        self.restore_db_update = restore_db_update
        self.restore_db_only = restore_db_only
        self.create_venv = create_venv
        self.filestore = filestore
        self.fix_banks = fix_banks
        self.migrate_ddt = migrate_ddt

    def prepare_do_migration(self):
        self.prepare_migration()
        self.do_migration()

    def prepare_migration(self):
        to_version = self.to_version
        from_version = self.from_version
        if self.create_venv:
            self.create_venv_git_version(to_version)
            self.create_venv_git_version(from_version)
        # FIXME NB.: Per i test di migrazione alla 10.0 rimosso il compute da
        #  /tmp_venv/openupgrade10.0/odoo/addons/product/models$ cat product_template.py
        #  altrimenti ci mette ore
        if self.restore_db_update:
            if self.filestore:
                self.restore_filestore(from_version, from_version)
            self.restore_db(from_version)
            self.disable_mail(disable=True)
            # n.b. when updating, at the end odoo service is stopped
            self.start_odoo(from_version, update=True)
            self.restore_db_update = False
        # restore db if not restored before, not needed if migration for more version
        elif self.restore_db_only:
            self.restore_db(from_version)
            self.restore_db_only = False
        if self.filestore:
            self.restore_filestore(from_version, to_version)
        self.disable_mail(disable=True)
        self.sql_fixes(self.receipts[from_version])
        self.uninstall_modules(from_version, before_migration=True)
        self.delete_old_modules(from_version)

    def disable_cron(self, disable=True):
        # add a big number to priority to identify them later
        value = 55000
        sign = '+' if disable else '-'
        sql = f"UPDATE ir_cron SET priority = priority {sign} {value}, " + \
              f"active = false WHERE active IS true;"
        if not disable:
            sql = f"UPDATE ir_cron SET active = true, priority = priority {sign} " + \
                  f"{value} WHERE priority > {value};"
        subprocess.Popen(
            [f'psql -p {self.db_port} -d {self.db} -c "{sql}"'],
            shell=True, cwd=self.path
        )

    def do_migration(self):
        self.disable_cron()
        to_version = self.to_version
        from_version = self.from_version
        if to_version == '11.0':
            self.fix_taxes(from_version)
        if to_version == '12.0' and self.fix_banks:
            self.fixes.migrate_bank_riba_id_bank_ids(from_version)
            self.fixes.migrate_bank_riba_id_bank_ids_invoice(from_version)
        if from_version == '12.0' and self.migrate_ddt:
            self.migrate_l10n_it_ddt_to_l10n_it_delivery_note(from_version)
        self.start_odoo(to_version, update=True)
        self.uninstall_modules(to_version, after_migration=True)
        self.auto_install_modules(to_version)
        self.sql_fixes(self.receipts[to_version])
        if to_version == '10.0':
            self.start_odoo(to_version)
            self.remove_modules('upgrade')
            self.remove_modules()
            self.install_uninstall_module('l10n_it_intrastat')
            self.stop_odoo()
        self.dump_database(to_version)
        if self.filestore:
            self.dump_filestore(to_version)
        print(f"Migration done from version {from_version} to version {to_version}")
        self.disable_cron(False)
        if self.from_version in versions:
            self.from_version = self.to_version
            self.to_version = versions[self.from_version]
            print(f"Set next version to {self.to_version}")

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

    def migrate_l10n_it_ddt_to_l10n_it_delivery_note(self, version):
        self.start_odoo(version)
        if self.client.env['ir.module.module'].search([
            ('name', '=', 'l10n_it_ddt'),
            ('state', '=', 'installed'),
        ]):
            self.install_uninstall_module(
                'l10n_it_delivery_note', install=True
            )
            self.stop_odoo()
            self.start_odoo(version=version,
                            extra_command=f'migrate_l10n_it_ddt -d {self.db}')

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

    def create_venv_git_version(self, version, openupgrade=True):
        self.repos = config.load_config('openupgrade_repos.yml', version)
        odoo_path = '%s/%s%s' % (
            self.venv_path, 'openupgrade' if openupgrade else 'standard',
            version)
        py_version = '2.7' if version in ['7.0', '8.0', '9.0', '10.0'] \
            else '3.5' if version == '11.0' else '3.7'
        odoo_repo = 'https://github.com/sergiocorato/OpenUpgrade.git'
        if not os.path.isdir(odoo_path):
            subprocess.Popen(['mkdir -p %s' % odoo_path], shell=True).wait()
            # do not recreate virtualenv as it regenerate file with bug in split()
            # ../openupgrade10.0/lib/python2.7/site-packages/pip/_internal/vcs/git.py
            subprocess.Popen([
                'virtualenv -p /usr/bin/python%s %s' % (py_version, odoo_path)],
                cwd=odoo_path, shell=True).wait()
        # install odoo repo, from v. 14.0 it contains only migration script
        if not os.path.isdir(os.path.join(odoo_path, 'odoo')):
            subprocess.Popen([
                'cd %s && git clone --single-branch %s -b %s --depth 1 odoo' % (
                    odoo_path, odoo_repo, version)],
                cwd=odoo_path, shell=True).wait()
        else:
            subprocess.Popen(['cd %s/odoo && git reset --hard origin/%s && git pull '
                              '&& git reset --hard origin/%s' % (
                                  odoo_path, version, version
                              )], cwd=odoo_path, shell=True).wait()
        if version not in [
            '7.0', '8.0', '9.0', '10.0', '11.0', '12.0', '13.0'
        ]:
            # install odoo repo
            self.install_repo('odoo', odoo_path)
        commands = [
            'bin/pip install "setuptools<58.0.0"',
            'bin/pip install -r odoo/requirements.txt',
            'bin/pip install -r repos/odoo/requirements.txt' if version not in [
                '8.0', '9.0', '10.0', '11.0', '12.0', '13.0'] else '',
            'cd odoo && ../bin/pip install -e . ' if version in [
                '8.0', '9.0', '10.0', '11.0', '12.0', '13.0'
            ] else 'cd repos/odoo && ../../bin/pip install -e . ',
        ]
        for command in commands:
            subprocess.Popen(command, cwd=odoo_path, shell=True).wait()
        extra_paths = ['%s/addons-extra' % odoo_path,
                       '%s/repos' % odoo_path]
        for path in extra_paths:
            if not os.path.isdir(path):
                process = subprocess.Popen(
                    'mkdir %s' % path, cwd=odoo_path, shell=True)
                process.wait()
        if os.path.isfile(os.path.join(odoo_path, 'migration.log')):
            process = subprocess.Popen(
                'rm %s' % 'migration.log', cwd=odoo_path, shell=True)
            process.wait()

        for repo_name in self.repos:
            self.install_repo(repo_name, odoo_path)

    def install_repo(self, repo_name, odoo_path):
        repo_text = self.repos.get(repo_name)
        repo = repo_text.split(' ')[0]
        repo_version = repo_text.split(' ')[1]
        repo_path = os.path.join(odoo_path, 'repos', repo_name)
        if not os.path.isdir(repo_path):
            process = subprocess.Popen([
                f'git clone --single-branch -b {repo_version} {repo} --depth 1 '
                f'{repo_path}'
            ], cwd=odoo_path, shell=True)
            process.wait()
        process = subprocess.Popen([
            f'git fetch --all && git reset --hard origin/{repo_version}'
        ], cwd=f"{repo_path}", shell=True)
        process.wait()
        # copy modules to create a unique addons path
        for root, dirs, files in os.walk(repo_path):
            for d in dirs:
                if d not in ['.git', 'setup']:
                    process = subprocess.Popen([
                        f"cp -rf {repo_path}/{d} {odoo_path}/addons-extra/"
                    ], cwd=odoo_path, shell=True)
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

    @staticmethod
    def uninst(module_to_uninstall, module_to_unistall_id, success):
        try:
            module_to_unistall_id.button_immediate_uninstall()
            module_to_unistall_id.unlink()
            print('Module %s uninstalled' % module_to_uninstall)
            success = 5
        except Exception as e:
            print(
                'Module %s not uninstalled for %s, trying %s/%s times.' % (
                    module_to_uninstall, str(e).replace('\n', ''), success + 1, 5)
            )
            time.sleep(10)
            success += 1
        return success

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
                    res = 0
                    while res < 5:
                        res = self.uninst(module, module_id, res)
                else:
                    print('Module %s not found' % module)
