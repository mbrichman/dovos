#!/bin/bash
source venv/bin/activate
python -m db.workers.embedding_worker
