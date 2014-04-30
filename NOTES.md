docker build -t cameronmaske/node-server test
docker tag f2f8016587f2 cameronmaske/node-server:v1

change to v2

docker build -t cameronmaske/node-server test

docker images
REPOSITORY                 TAG                 IMAGE ID            CREATED             VIRTUAL SIZE
cameronmaske/node-server   latest              6dd1178fe740        7 seconds ago       398.5 MB
cameronmaske/node-server   v1                  f2f8016587f2        2 minutes ago       398.5 MB

docker tag 6dd1178fe740 cameronmaske/node-server:v2
docker push cameronmaske/node-server


Nginx as a load balancer.
All nginx configuration files are located in the /etc/nginx/ directory. The primary configuration file is /etc/nginx/nginx.conf.

apt-get install -y nginx

http {
    upstream containers {
        # Containers forwarding.
        server 10.0.0.1:80;
        server 10.0.0.2:80;
        server 10.0.0.3:80;
    }

    server {
        listen 80;
        location / {
            proxy_pass http://containers;
        }
    }
}


user www-data;
worker_processes 4;
pid /var/run/nginx.pid;

events {
        worker_connections 768;
        # multi_accept on;
}

http {
    upstream containers {
        # Containers forwarding.
        server 10.0.0.1:80;
        server 10.0.0.2:80;
        server 10.0.0.3:80;
    }

    server {
        listen 80;
        location / {
            proxy_pass http://containers;
        }
    }
}

sudo service nginx start

/etc/init.d/nginx configtest && sudo /etc/init.d/nginx reload
