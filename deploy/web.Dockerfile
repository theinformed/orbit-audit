FROM nginx:1.30-alpine

COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
# Includes the optional static study document and deferred app shell when the
# constrained-delivery build flag is enabled; default builds contain index only.
COPY dist/*.html* /usr/share/nginx/html/
COPY dist/assets /usr/share/nginx/html/assets
# Named explicitly rather than swept up by a `COPY dist/`, because `dist/data`
# is a mount point for the artifact volume and copying it into the image would
# bake a stale snapshot underneath the mount. That is also why the favicon went
# missing: it was built, rsynced to the VPS and then never entered the image,
# so nginx answered /space/favicon.svg with the SPA fallback -- HTTP 200, with
# Content-Type text/html. A 200 is not proof that the right thing was served.
COPY dist/favicon.svg /usr/share/nginx/html/favicon.svg
COPY dist/apple-touch-icon.png /usr/share/nginx/html/apple-touch-icon.png
COPY dist/icon-512.png /usr/share/nginx/html/icon-512.png
COPY dist/social-card.png /usr/share/nginx/html/social-card.png
# The reader-feedback widget. Named here for the same reason as the icons: the
# verify build config sets publicDir:false (it would otherwise copy the ~44 GB
# public/data tree), so nothing under public/ reaches dist on its own. Baked in
# rather than linked from the shared host, so the box still opens and says the
# submission failed honestly when the feedback service is down.
COPY dist/feedback-widget.js /usr/share/nginx/html/feedback-widget.js

# Operator methods pages. Static, auth-gated at the Caddy layer
# (/space/ops/* -> forward_auth -> rewrite /ops/*), served by nginx's ordinary
# try_files. Staged into dist/ops by deploy/build-and-stage.sh on the VPS,
# because the verify build sets publicDir:false and ships nothing from public/
# on its own -- the exact trap documented at the top of that script.
COPY dist/ops /usr/share/nginx/html/ops

EXPOSE 8080
