# -*- coding: utf-8 -*-
# Copyright 2019 Sergio Corato <https://github.com/sergiocorato>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import subprocess


class Fixes:
    # in migration to 10.0, some account.move.line created from account.invoice
    # missed tax_line_id
    # select name,date from account_move_line where tax_line_id is null and account_id
    # = (id del conto iva a debito);
    # ma probabilmente era un errore della 8.0
    # fixme nella migrazione dalla 8.0 alla 10.0 non tutte le imposte acquisto vengono
    #  impostate con il campo conto liquidazione IVA! e l'iva indetraibile non viene
    #  ovviamente corretta con la nuova configurazione (padre-figlie)
    # todo dopo il ripristino del db e del filestore:
    #  ripristinare filtri disabilitati perche invalidi

    def set_product_with_wrong_uom_not_saleable(self):
        # giorni: 29 e 26 > not saleable
        # ore: 27 e 20 > 5 not saleable
        # type = 'service' > 6 not saleable
        bash_commands = [
            'update product_template set sale_ok = false where '
            'uom_id in (29,26);',
            'update product_template set sale_ok = false where '
            'uom_id in (20,27);',
            'update product_template set sale_ok = false where '
            'uom_id = 1 and type = \'service\';',
        ]
        for bash_command in bash_commands:
            command = ['psql -U sergio -p %s -d %s -c "%s"'
                       % (self.db_port, self.db, bash_command)]
            process = subprocess.Popen(command, shell=True)
            process.wait()

    def update_product_track_service(self):
        bash_commands = [
            'update product_template set track_service = \'task\' where '
            'type '
            ' = \'service\' and uom_id in (select id from product_uom where '
            'category_id in (select id from product_uom_categ where name ilike'
            ' \'%Working%\'));',
        ]
        for bash_command in bash_commands:
            command = ['psql -U sergio -p %s -d %s -c "%s"'
                       % (self.db_port, self.db, bash_command)]
            process = subprocess.Popen(command, shell=True)
            process.wait()

    # def update_auto_create_task(self):
    #     # todo if want to use this, would have to map the task related and
    #     # write them inside sale order line to work correctly
    #     bash_commands = [
    #         'update product_template set auto_create_task = true where type '
    #         ' = \'service\' and uom_id in (select id from product_uom where '
    #         'category_id in (select id from product_uom_categ where name ilike'
    #         ' \'%Working%\'));',
    #     ]
    #     for bash_command in bash_commands:
    #         command = ['psql -U sergio -p %s -d %s -c "%s"'
    #                    % (self.db_port, self.db, bash_command)]
    #         process = subprocess.Popen(command, shell=True)
    #         process.wait()

    def update_analitic_sal(self):
        bash_commands = [
            'update account_analytic_account set use_sal = true where id'
            ' in (select account_analytic_id from account_analytic_sal);',
        ]
        for bash_command in bash_commands:
            command = ['psql -U sergio -p %s -d %s -c "%s"'
                       % (self.db_port, self.db, bash_command)]
            process = subprocess.Popen(command, shell=True)
            process.wait()

    def fix_delivered_hours_sale(self):
        self.start_odoo('10.0', venv=True)
        import logging
        logging.basicConfig(filename='fix_delivered_hours_sale.log',
                            level=logging.DEBUG)
        contract_obj = self.client.env['account.analytic.account']
        sale_obj = self.client.env['sale.order']
        for contract in contract_obj.search([]):
            if not contract.project_ids:
                continue
            if not contract.project_ids[0].line_ids:
                continue
            done_sale_orders = sale_obj.search([
                ('name', 'ilike', contract.name),
                ('state', '=', 'done')
            ])
            if done_sale_orders:
                for sale_order in done_sale_orders:
                    sale_order.state = 'sale'
            contract.project_ids[0].line_ids.write({'lead_id': False})
            if done_sale_orders:
                for sale_order in done_sale_orders:
                    sale_order.state = 'done'
            logging.info('Fixed hours delivered for sale orders of project %s!'
                         % contract.name)
        self.stop_odoo()

    def fix_taxes(self):
        # correzione da fare sulle imposte dopo la migrazione
        # la correzione durante la migrazione pare complicata
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
