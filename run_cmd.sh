#!/bin/bash

exec gunicorn tastemakerbot.wsgi:application --workers 4 --name tastemakerbot --bind 0.0.0.0:8011 --timeout 200 &