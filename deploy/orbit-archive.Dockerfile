# The bigmem-side orbit-history archive server.
#
# Nothing is COPIED into this image except the server config: the shards are a
# read-only bind mount, because they are 4.1 GB rewritten hourly and baking a
# generation of them into a layer would be both enormous and instantly stale.
FROM nginx:1.30-alpine

COPY deploy/orbit-archive.nginx.conf /etc/nginx/conf.d/default.conf

# Estate rule: every new container ships with a HEALTHCHECK or a written
# exemption. `grep -qx ok` rather than a bare wget, because an nginx that has
# lost its config still answers 200 with something -- exit 0 on a 200 would be
# the green-is-not-healthy defect this estate has already paid for once.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz | grep -qx ok

EXPOSE 8080
