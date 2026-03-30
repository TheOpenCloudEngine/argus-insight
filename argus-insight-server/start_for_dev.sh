#!/bin/sh

uvicorn app.main:app --host 0.0.0.0 --port 4500 --reload --reload-dir app
