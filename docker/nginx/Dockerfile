FROM nginx:latest

COPY robots.txt /etc/nginx/robots.txt
COPY favicon.ico /etc/nginx/favicon.ico

COPY nginx.common.conf /etc/nginx/nginx.common.conf
COPY nginx.dev.conf /etc/nginx/nginx.dev.conf
COPY nginx.prod.conf /etc/nginx/nginx.prod.conf

ARG NGINX_CONF=nginx.dev.conf
COPY ${NGINX_CONF} /etc/nginx/nginx.conf