/**
 * Portal Branding — 禁用 Guacamole 菜单快捷键
 *
 * CSS 隐藏了菜单的 DOM，但 Angular 控制器仍会将 menu.shown 设为 true。
 * 当 menu.shown = true 时，键盘输入被菜单截获不会发送到 RDP 会话。
 * 此脚本定期检测并重置状态，确保键盘输入始终流向远程桌面。
 */
(function () {
    'use strict';

    setInterval(function () {
        try {
            var el = document.getElementById('guac-menu');
            if (el && window.angular) {
                var s = angular.element(el).scope();
                if (s && s.menu && s.menu.shown) {
                    s.menu.shown = false;
                    s.$apply();
                }
            }
        } catch (e) {
            /* 忽略: Angular 尚未就绪或 scope 不可用 */
        }
    }, 150);
})();
