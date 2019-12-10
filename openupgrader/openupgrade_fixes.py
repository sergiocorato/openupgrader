# -*- coding: utf-8 -*-
# Copyright 2019 Sergio Corato <https://github.com/sergiocorato>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

import subprocess


class Fixes:
    def __init__(self, db, user, password, db_port):
        self.db = db
        self.user = user
        self.password = password
        self.db_port = db_port

    # in migration to 10.0, some account.move.line created from account.invoice
    # missed tax_line_id
    # elect name,date from account_move_line where tax_line_id is null and account_id
    # = (id del conto iva a debito);
    # ma probabilmente era un errore della 8.0
    # fixme nella migrazione dalla 8.0 alla 10.0 non tutte le imposte acquisto vengono
    #  impostate con il campo conto liquidazione IVA! e l'iva indetraibile non viene
    #  ovviamente corretta con la nuova configurazione (padre-figlie)
    # todo fix ir.config_parameter sempre a 'http://127.0.0.1:8069'

    def remove_views(self):
        bash_commands = [
            'delete from ir_ui_view where inherit_id is not null;',
            'delete from ir_ui_view where inherit_id is not null;',
            'delete from ir_ui_view where inherit_id is not null;',
            'delete from ir_ui_view where inherit_id is not null;',
            'delete from ir_ui_view where inherit_id is not null;',
            'delete from ir_ui_view where name = \'stock.journal.form\';',
            'delete from ir_ui_view where id in ('
                'select ir_model_data.res_id from ir_model_data join '
                'ir_module_module on ir_module_module.name = '
                'ir_model_data.module where model=\'ir.ui.view\' '
                'and state=\'uninstalled\');',
            'delete from ir_ui_menu where id in ('
                'select ir_model_data.res_id from ir_model_data join '
                'ir_module_module on ir_module_module.name = '
                'ir_model_data.module where model=\'ir.ui.menu\' '
                'and state=\'uninstalled\');',
            'delete from ir_ui_view where id in (475, 472, 735);',
            'delete from ir_ui_view where id in (736, 476, 536, 963, 156);',
            'delete from ir_ui_view where id in (1577, 1578, 1918, 2011);',
            'delete from ir_ui_view where model = \'account.invoice\' '
                'and name ilike \'%pro%\';',
            # try to fix account_vat_period_end_statement upgrade, if don't
            # work, remove and reinstall
            'delete from ir_ui_view where model = \'res.company\' '
                'and name ilike \'%view_company_form_rea%\';',
            'delete from ir_ui_view where model = \'res.partner\' '
                'and name ilike \'%view_rea_partner_form%\';',
            'delete from ir_ui_view where model = \'res.company\' '
                'and name ilike \'%view_vat_period_end_statement_company%\';',
            'delete from decimal_precision where name = \'Stock Volume\';',
            'update ir_rule set active = true where active = false and name !='
                ' \'Project: project manager: does not see all (modified)\';',
            'DROP VIEW IF EXISTS report_analytic_account_close;',
            'DROP VIEW IF EXISTS hr_expense_report;',
            'DROP VIEW IF EXISTS report_timesheet_line;',
            'DROP VIEW IF EXISTS hr_timesheet_report;',
            'DROP VIEW IF EXISTS report_account_receivable;',
            'delete from hr_applicant_category;',
            'delete from ir_ui_view where model = \'account.payment.mode\';',
        ]
        for bash_command in bash_commands:
            command = ['psql -U sergio -p %s -d %s -c "%s"'
                       % (self.db_port, self.db, bash_command)]
            process = subprocess.Popen(command, shell=True)
            process.wait()

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

    def fix_uom_invoiced_from_sale(self):
        self.start_odoo('8.0')
        import logging
        logging.basicConfig(filename='check_uom.log',
                            level=logging.DEBUG)
        sale_order_line_model = self.client.env['sale.order.line']
        sale_lines = sale_order_line_model.search([
            ('invoice_lines', '!=', False)])
        i = 0
        logging.info('sale_lines len = %d' % len(sale_lines))
        for sale_line in sale_lines:
            # 1. update product_uom in sale_order_line with product_id.uom_id
            # 2. update uos_id in sale_order_line.invoice_lines (uom_id after migration
            # 3. update uos_id in account_invoice_line with product_id.uom_id
            # 4. update product_uom in purchase_order_line with product_id.uom_id
            # fix uom in sale order lines
            # if sale_line.product_id and sale_line.product_id.uom_id.category_id.id != \
            #         sale_line.product_uom.category_id.id:
            #     logging.info('syncronize sale line uom to sale line')
            #     sale_line.product_uom = sale_line.product_id.uom_id
            # fix uom in invoice lines
            # logging.info('sale_line id %s with invoice_lines %s' % (
            #     sale_line.id, sale_line.invoice_lines
            # ))
            # if len(set([x.uos_id.id for x in sale_line.invoice_lines])) > 1:
            #     logging.info('Found more uos_id in invoice_lines for the '
            #                  'same sale order line, in invoice %s'
            #                  % [x.invoice_id.name for x in
            #                     sale_line.invoice_lines])
            for inv_line in sale_line.invoice_lines:
                if not inv_line.uos_id:
                    inv_line.uos_id = sale_line.product_uom
                    logging.info('invoice_line %s do not have uom, set equal'
                                 'to sale line uom %s' % (inv_line.id,
                                                          sale_line.product_uom))
                if inv_line.uos_id.category_id.id != \
                        sale_line.product_uom.category_id.id:
                    # invoice uom ctg differ from sale uom
                    logging.info('invoice line %s differ uom %s from sale'
                                 'line uom %s' % (inv_line.id, inv_line.uos_id,
                                                  sale_line.product_uom))
                    if inv_line.product_id:
                        if sale_line.product_id:
                            # either have product_id but with different uom ctg
                            if inv_line.product_id.uom_id.category_id.id != \
                                    sale_line.product_uom.category_id.id:
                                # fix product_id uom in invoice
                                inv_line.product_id.uom_id = sale_line. \
                                    product_id.uom_id
                                # fix uos_id in invoice line
                                logging.info(
                                    '#1 sale_line %s updated uom_id %s to %s'
                                    % (
                                       sale_line.id, sale_line.product_uom,
                                       inv_line.uos_id))
                        else:
                            # invoice has a product_id while sale don't, so
                            # update sale with uom of invoice
                            logging.info(
                                '#2 sale_line %s updated uom_id %s to %s' % (
                                    sale_line.id, sale_line.product_uom,
                                    inv_line.uos_id))
                    else:
                        logging.info(
                            '#3 sale_line %s updated uom_id %s to %s' % (
                                sale_line.id, sale_line.product_uom,
                                inv_line.uos_id))
                    sale_line.product_uom = inv_line.uos_id
        self.stop_odoo()

    def fix_uom_invoiced_from_purchase(self):
        self.start_odoo('8.0')
        import logging
        logging.basicConfig(filename='check_uom_purchase.log',
                            level=logging.DEBUG)
        purchase_order_line_model = self.client.env['purchase.order.line']
        purchase_lines = purchase_order_line_model.search([
            ('invoice_lines', '!=', False)])
        i = 0
        logging.info('purchase_lines len = %d' % len(purchase_lines))
        for purchase_line in purchase_lines:
            # 1. update product_uom in sale_order_line with product_id.uom_id
            # 2. update uos_id in sale_order_line.invoice_lines (uom_id after migration
            # 3. update uos_id in account_invoice_line with product_id.uom_id
            # 4. update product_uom in purchase_order_line with product_id.uom_id
            # fix uom in sale order lines
            # if purchase_line.product_id and purchase_line.product_id.uom_id.\
            #         category_id.id != \
            #         purchase_line.product_uom.category_id.id:
            #     purchase_line.product_uom = purchase_line.product_id.uom_id
            # fix uom in invoice lines
            logging.info('purchase_line id %s with invoice_lines %s' % (
                purchase_line.id, purchase_line.invoice_lines
            ))
            for inv_line in purchase_line.invoice_lines:
                if not inv_line.uos_id:
                    inv_line.uos_id = purchase_line.product_uom
                if inv_line.uos_id.category_id.id != \
                        purchase_line.product_uom.category_id.id:
                    # invoice uom ctg differ from sale uom
                    if inv_line.product_id:
                        if purchase_line.product_id:
                            # either have product_id but with different uom ctg
                            if inv_line.product_id.uom_id.category_id.id != \
                                    purchase_line.product_uom.category_id.id:
                                # fix product_id uom in invoice
                                # inv_line.product_id.uom_id = sale_line. \
                                #     product_id.uom_id
                                # fix uos_id in invoice line
                                logging.info(
                                    '#1 purchase_line %s updated uom_id %s to %s'
                                    % (
                                        purchase_line.id,
                                        purchase_line.product_uom,
                                        inv_line.uos_id))
                        else:
                            # invoice has a product_id while sale don't, so
                            # update sale with uom of invoice
                            logging.info(
                                '#2 purchase_line %s updated uom_id %s to %s' % (
                                    purchase_line.id, purchase_line.product_uom,
                                    inv_line.uos_id))
                    else:
                        logging.info(
                            '#3 purchase_line %s updated uom_id %s to %s' % (
                                purchase_line.id, purchase_line.product_uom,
                                inv_line.uos_id))
                    # write all invoice lines, then break
                    for line in purchase_line.invoice_lines:
                        logging.info(
                            '#4 inv line %s updated uom_id %s to %s'
                            % (
                                line.id,
                                line.uos_id,
                                purchase_line.product_uom))
                        line.uos_id = purchase_line.product_uom
                    break
        purchase_lines = purchase_order_line_model.search([
            ('partner_id', '=', 378)])
        for purchase_line in purchase_lines:
            purchase_line.product_uom = 1
        invoice_lines = self.client.env['account.invoice.line'].search([
            ('partner_id', '=', 378)])
        for invoice_line in invoice_lines:
            invoice_line.uos_id = 1
        self.stop_odoo()


    def remove_aeroo_reports(self):
        model_obj = self.client.env['ir.model.data']
        reports = model_obj.search([
            ('model', '=', 'ir.actions.report.xml')
        ])
        #todo get reports by report_type = 'aeroo'

    # todo dopo il ripristino del db e del filestore:
    #  ripristinare filtri disabilitati perche invalidi

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
