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
