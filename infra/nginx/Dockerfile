FROM nginx:1.27-alpine
RUN apk add --no-cache openssl \
    && mkdir -p /etc/nginx/certs \
    && openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
       -keyout /etc/nginx/certs/dev.key -out /etc/nginx/certs/dev.crt \
       -subj "/CN=localhost" \
    && apk del openssl
COPY nginx.conf /etc/nginx/conf.d/default.conf
