/**
 * 登录页面逻辑
 */
(function () {
    // 已有 token → 跳转主页
    if (localStorage.getItem('portal_token')) {
        window.location.href = '/';
        return;
    }

    document.getElementById('login-form').addEventListener('submit', async function (e) {
        e.preventDefault();
        var errorEl = document.getElementById('login-error');
        errorEl.style.display = 'none';

        var username = document.getElementById('username').value.trim();
        var password = document.getElementById('password').value;

        if (!username || !password) {
            errorEl.textContent = '请输入用户名和密码';
            errorEl.style.display = 'block';
            return;
        }

        var btn = this.querySelector('button[type="submit"]');
        btn.disabled = true;
        btn.textContent = '登录中...';

        try {
            var resp = await fetch('/api/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: username, password: password }),
            });

            if (!resp.ok) {
                var err = await resp.json().catch(function () { return {}; });
                throw new Error(err.detail || '登录失败');
            }

            var data = await resp.json();
            localStorage.setItem('portal_token', data.token);
            localStorage.setItem('portal_user', JSON.stringify({
                user_id: data.user_id,
                username: data.username,
                display_name: data.display_name,
                is_admin: data.is_admin || false,
            }));
            window.location.href = '/';
        } catch (err) {
            errorEl.textContent = err.message;
            errorEl.style.display = 'block';
        } finally {
            btn.disabled = false;
            btn.textContent = '登录';
        }
    });
})();
