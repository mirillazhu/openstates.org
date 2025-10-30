#!/bin/sh

# set DATABASE_URL for local development
export DATABASE_URL="postgis://openstates:openstates@localhost:5405/openstatesorg"

poetry run pytest -W always --ds web.test_settings --reuse-db --strict "$@"
