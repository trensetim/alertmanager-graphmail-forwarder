#!/bin/sh

gunicorn -k gthread -b 0.0.0.0:8000 main:flask
