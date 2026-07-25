# Current-state audit

## Repository evidence

- `backend/router.py:81-114`: global drive config and per-user `/drive/portal_u{user_id}` mapping.
- `backend/guacamole_crypto.py:176-181,193-225`: RemoteApp is optional; clipboard and drive/file-transfer parameters are emitted conditionally.
- `backend/file_router.py:110-121`: Portal API path containment with `resolve()` + prefix check.
- `config/config.json:23-31`: GuacDrive enabled; browser transfer disabled globally.
- `deploy/docker-compose.yml:11-19,69-86,103-114`: guacd/backend/nginx share `/drive`; only Nginx is published.
- `deploy/nginx/conf.d/portal.conf:36-43`: `/internal-drive/` is Nginx internal alias.
- `docker-compose.yml:21-27`: old stack publishes Guacamole 8080 directly.
- `frontend/js/portal-launch.js:72-80`: Guacamole iframe grants browser clipboard capabilities.
- `docs/personal-space-design.md:423-491`: RemoteApp directly modifies GuacDrive outside Portal API; API isolation is per user.

## Local runtime snapshot, 2026-07-25

Read-only query against the running `nercar-portal` backend/database:

- 5 active applications.
- 1 RDP host.
- 1 distinct RDP account.
- Each active application is assigned to 2 portal users.
- 2 active connections have empty `remote_app` and are full-desktop candidates.
- VSCode is published as a RemoteApp.
- Only Notepad has both clipboard directions disabled; the other four active applications have copy/paste open.
- Global Guacamole browser upload/download remains disabled through config inheritance.

No credential values were read or recorded.

## Windows policy evidence

- `C:\Windows\PolicyDefinitions\zh-CN\WindowsExplorer.adml:134-143` states that hiding drives removes icons but users and programs can still access them by other methods.
- `C:\Windows\PolicyDefinitions\zh-CN\WindowsExplorer.adml:258-267` states that “prevent access from My Computer” does not prevent programs from accessing local or network drives.

## Official sources

- Apache Guacamole RDP configuration: https://guacamole.apache.org/doc/gug/configuring-guacamole.html
  - `enable-drive` exposes a virtual drive persisted under `drive-path`.
  - `disable-download` and `disable-upload` govern browser-side transfer, not Windows local-disk access.
  - `disable-copy` and `disable-paste` govern browser/remote clipboard directions.
- Microsoft AppLocker overview: https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/applocker/applocker-overview
  - AppLocker controls which executables, scripts, installers, DLLs, packaged apps and installers users can run.
  - Microsoft describes AppLocker as defense-in-depth and recommends App Control for Business for robust protection.
- Microsoft Application Control for Windows: https://learn.microsoft.com/en-us/windows/security/application-security/application-control/app-control-for-business/appcontrol

## Conclusion

The current per-user GuacDrive mapping is a valid component and should remain. The missing boundary is Windows-side identity and policy enforcement. Hiding drives alone cannot satisfy the requested security property.
