"""Static server for dist/ only, bound to 127.0.0.1 (exposed publicly only via cloudflared)."""
import http.server, functools, mimetypes, sys, os
mimetypes.add_type("model/gltf-binary", ".glb")
mimetypes.add_type("text/javascript", ".js")
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist")
class H(http.server.SimpleHTTPRequestHandler):
    extensions_map = {**http.server.SimpleHTTPRequestHandler.extensions_map,
                      ".glb": "model/gltf-binary", ".js": "text/javascript"}
    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        super().end_headers()
handler = functools.partial(H, directory=ROOT)
http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler).serve_forever()
