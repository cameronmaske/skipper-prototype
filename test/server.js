var host = "0.0.0.0";
var port = 1337;
var express = require("express");

var app = express();

app.get("/", function(request, response){
    response.send("v2");
});

app.listen(port, host);