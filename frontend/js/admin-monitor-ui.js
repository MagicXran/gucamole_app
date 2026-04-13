(function(global) {
    'use strict';

    function renderMonitorCards(data) {
        var container = document.getElementById('monitor-cards');
        container.innerHTML = '';

        var summary = document.getElementById('monitor-summary');
        if (summary) {
            summary.textContent = '在线 ' + data.total_online + ' 人 / ' + data.total_sessions + ' 个会话';
        }

        (data.apps || []).forEach(function(app) {
            var card = document.createElement('div');
            card.className = 'monitor-card';

            var iconEl = document.createElement('span');
            iconEl.className = 'monitor-card__icon';
            iconEl.textContent = ICON_MAP[app.icon] || ICON_MAP.desktop;

            var info = document.createElement('div');
            info.className = 'monitor-card__info';

            var nameEl = document.createElement('div');
            nameEl.className = 'monitor-card__name';
            nameEl.textContent = app.app_name;

            var countEl = document.createElement('div');
            countEl.className = 'monitor-card__count' + (app.active_count > 0 ? ' monitor-card__count--active' : '');
            countEl.textContent = app.active_count + ' ';

            var dot = document.createElement('span');
            dot.className = 'monitor-card__dot ' + (app.active_count > 0 ? 'monitor-card__dot--green' : 'monitor-card__dot--gray');
            countEl.appendChild(dot);

            info.appendChild(nameEl);
            info.appendChild(countEl);
            card.appendChild(iconEl);
            card.appendChild(info);
            container.appendChild(card);
        });
    }

    global.AdminMonitorUi = {
        renderMonitorCards: renderMonitorCards,
    };
})(window);
