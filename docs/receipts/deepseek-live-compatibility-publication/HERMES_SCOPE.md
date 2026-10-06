# User-selected Hermes credential for key check

Anthony's follow-up “check hermes .env” selects `/Users/vaquez/.hermes/.env` for the
previously requested one-call API-key test. File metadata confirms a regular, user-owned,
non-symlink, 0600 file within the read bound. Its contents have not been read at this commit.
The revised plan SHA-256 is `5d961e8dbb99b9d2e37117972928ae9c8246f1f1d3c97b65dc7865221c771aa1`.

Exactly one literal `DEEPSEEK_API_KEY` is parsed in memory from that explicitly named file.
No other key is loaded or printed, no shell is sourced, no environment is changed, and no
credential is copied to another file. The Hermes file is not edited. Missing, duplicate,
expanded or malformed target assignments refuse the request. Seven newly generated dummy
parser checks pass with network denied. The raw API response is never logged.

This changes only the credential selection for the separate single GET /models check.
One authenticated metadata request maximum, zero inference, 30 seconds, no retries; the
original preregistered compatibility plan and its unfilled authorization remain unchanged.
The old missing-file preflight is retained; it consumed zero request allowance. The metadata
probe result stays local at `/Users/vaquez/.local/state/humanity-succeed/deepseek-key-check-hermes-001/result.json`.
