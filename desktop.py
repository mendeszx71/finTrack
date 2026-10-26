"""FinTrack desktop entrypoint for Windows (pywebview)."""
import threading
from http.server import ThreadingHTTPServer
from server import Handler, init
import webview

class LocalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

def main():
    init()
    server = LocalServer(('127.0.0.1', 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        webview.create_window('FinTrack Advanced', f'http://127.0.0.1:{port}', width=1280, height=820, min_size=(900, 620))
        webview.start(gui='edgechromium')
    finally:
        server.shutdown()
        server.server_close()

if __name__ == '__main__':
    main()
