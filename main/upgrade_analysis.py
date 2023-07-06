import openupgrader


class UpgradeAnalysis:
    """
    This function create an instance of odoo these modules in path:
        openupgrade_scripts
        openupgrade_records

    It creates a database without demo data and install the upgrade_analysis module and
    the module passed in __init__ function.

    Then follow these instructions to do manually:

    On both instances: from the analysis menu, start the Generate Records Wizard.
    On the target instance (this is the more recent version): from the analysis menu,
    select the Comparison Configuration option and create a new config to connect to
    the other instance. In the form view of this configuration record ,
    start a New Analysis.

    The analysis files for each of the modules will be placed in the following location:
     1. In the case of Odoo modules: in the path that is indicated by the –upgrade-path
      parameter of the Odoo server, or in the scripts folder of the openupgrade_scripts
      module directory if it is available in your addons path
     2. In the case of OCA or custom modules: in the migrations/<version> directory in
      the module directory itself.

    Example call:
     u = upgrade_analysis.UpgradeAnalysis('14.0', 'account_invoice_dueamount')
     u.init_odoo_istance()
     u.start_odoo()
    """
    def __init__(self, version, module):
        self.db = 'upgrade'
        self.version = version
        self.module = module
        self.upgrade_module = 'upgrade_analysis'
        # < 13.0 are not supported
        # if version == '12.0':
        #     self.upgrade_module = 'openupgrade_records'
        db_port = '5440'
        if version == '14.0':
            db_port = '5441'
        if version == '16.0':
            db_port = '5442'
        self.connection = openupgrader.Connection(
            db=self.db,
            user='demo',
            password='admin',
            db_port=db_port,
        )

    def init_odoo_istance(self):
        self.connection.create_venv_git_version(
            self.version, openupgrade=False)

    def start_odoo(self):
        self.connection.start_odoo(
            version=self.version,
            openupgrade_folder=False,
            extra_command=f'-d {self.db} -i base,{self.upgrade_module},{self.module} '
                          f'--without-demo=ALL'
        )
