# Guacamole 1.6.0 with the narrowly scoped RDPDR UTF-8 byte-length fix.
FROM guacamole/guacd:1.6.0 AS guacd-source

FROM python:3.12-slim-bookworm AS patcher
ARG GUACD_RDP_LIBRARY_SHA256=00e12f90104aaa8cffc0b0b8ab461ff1f774e7b2c45c47b978e3b7e2d088e729
COPY --from=guacd-source /opt/guacamole/lib/libguac-client-rdp.so.0.0.0 /tmp/libguac-client-rdp.so.0.0.0
COPY scripts/patch-guacd-rdpdr-drive-name.py /tmp/patch-guacd-rdpdr-drive-name.py
RUN python /tmp/patch-guacd-rdpdr-drive-name.py \
    --input /tmp/libguac-client-rdp.so.0.0.0 \
    --output /tmp/libguac-client-rdp.so.0.0.0.patched \
    --expected-sha256 ${GUACD_RDP_LIBRARY_SHA256}

FROM guacamole/guacd:1.6.0
COPY --from=patcher /tmp/libguac-client-rdp.so.0.0.0.patched /opt/guacamole/lib/libguac-client-rdp.so.0.0.0
