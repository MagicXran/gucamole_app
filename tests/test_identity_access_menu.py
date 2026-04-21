from backend.identity_access import ADMIN_MENU_ITEMS, _build_menu_tree


def test_admin_menu_restores_all_admin_pages():
    paths = [item["path"] for item in ADMIN_MENU_ITEMS]

    assert "/admin/pools" in paths
    assert "/admin/apps" in paths
    assert "/admin/users" in paths
    assert "/admin/acl" in paths
    assert "/admin/queues" in paths
    assert "/admin/monitor" in paths
    assert "/admin/workers" in paths
    assert "/admin/analytics" in paths
    assert "/admin/audit" in paths

    admin_group = next(group for group in _build_menu_tree(True) if group["key"] == "admin")
    admin_paths = [item["path"] for item in admin_group["children"]]

    assert admin_paths == paths
