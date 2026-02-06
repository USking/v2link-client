# v2link-client

Linux desktop client for V2Ray-style links built with Python 3.11+ and PyQt6 (currently supports `vless://`).

## Runtime requirements

- Python 3.11+
- Xray-core in your `PATH` (`xray version` should work)

## Development

- Create a virtual environment and install dependencies:
  - `pip install -r requirements.txt`
- Run:
  - `./scripts/dev_run.sh`

## Notes

- Current UI flow:
  - Paste a `vless://` link
  - Click `Validate & Save`
  - Click `Start` (defaults to SOCKS5 `127.0.0.1:1080`, HTTP `127.0.0.1:8080`, but will pick free ports if busy)
