FROM dockerfile/nodejs

WORKDIR /code/
RUN npm install express

ADD server.js /code/server.js

EXPOSE 1337

CMD node server.js