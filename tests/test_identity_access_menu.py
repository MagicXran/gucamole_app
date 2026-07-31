from backend.identity_access import ADMIN_MENU_ITEMS, _build_menu_tree


def test_workspace_menu_uses_user_space_label():
    my_group = next(group for group in _build_menu_tree(False) if group["key"] == "my")
    workspace = next(item for item in my_group["children"] if item["key"] == "my-workspace")

    assert workspace["title"] == "用户空间"


def test_admin_menu_restores_all_admin_pages():
    paths = [item["path"] for item in ADMIN_MENU_ITEMS]

    assert "/admin/pools" in paths
    assert "/admin/apps" in paths
    assert "/admin/vscode-policies" in paths
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
