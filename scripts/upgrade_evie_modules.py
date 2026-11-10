"""Install and upgrade every available Evie module in the current database.

Run through Odoo's shell so that ``env`` is provided automatically::

    odoo-bin shell -d "$PGDATABASE" < "$HOME/src/user/eveai/scripts/upgrade_evie_modules.py"

Substitute ``eveai`` with the actual submodule path when necessary.
"""

Module = env['ir.module.module']  # noqa: F821

print(f'[evie-upgrade] Database: {env.cr.dbname}')  # noqa: F821
print('[evie-upgrade] Refreshing the apps list...')
Module.update_list()

modules = Module.search([('name', 'like', 'evie_%')], order='name')
to_install = modules.filtered(lambda module: module.state == 'uninstalled')
to_upgrade = modules.filtered(lambda module: module.state == 'installed')

install_names = ', '.join(to_install.mapped('name')) or 'none'
upgrade_names = ', '.join(to_upgrade.mapped('name')) or 'none'
print(f'[evie-upgrade] Installing: {install_names}')
print(f'[evie-upgrade] Upgrading: {upgrade_names}')

to_install.button_immediate_install()
to_upgrade.button_immediate_upgrade()
env.cr.commit()  # noqa: F821

print('[evie-upgrade] Completed. Final module report:')
final_modules = Module.search([('name', 'like', 'evie_%')], order='name')
for module in final_modules:
    print(
        f'[evie-upgrade]   {module.name}: state={module.state}, '
        f'installed={module.installed_version or "-"}, '
        f'latest={module.latest_version or "-"}'
    )
