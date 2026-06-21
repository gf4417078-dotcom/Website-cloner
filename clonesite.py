#!/usr/bin/env python3
import sys, os, re, base64, hashlib, json, socket, ssl, time, random
import urllib.request, urllib.parse, urllib.error, http.cookiejar
from html.parser import HTMLParser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urljoin, urlparse, quote

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
]
HEADERS_BASE = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "identity",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive",
    "DNT": "1",
}
MIN_DELAY, MAX_DELAY = 0.5, 1.5
TOR_MIN_DELAY, TOR_MAX_DELAY = 1.0, 3.0
MAX_RETRIES = 3
TIMEOUT, TOR_TIMEOUT = 20, 40
COMMON_DIRS = [
    "api", "api/v1", "api/v2", "admin", "backup", "data", "json", "rest",
    "graphql", "upload", "uploads", "assets", "static", "media", "files",
    "content", "config", "users", "login", "dashboard",
    "wp-json", "wp-content", "wp-admin", "xmlrpc.php",
    "sitemap.xml", "robots.txt", "feed", "rss", "atom"
]

cookie_jar = http.cookiejar.CookieJar()
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE
PROXY_URL, TOR_MODE = None, False
FAILED_RESOURCES, DOWNLOADED = 0, 0
INLINE_CACHE = {}
SINGLE_FILE_MODE = False

def setup_proxy(proxy_str):
    global PROXY_URL, TOR_MODE
    PROXY_URL = proxy_str
    if proxy_str is None:
        TOR_MODE = False
        if hasattr(socket, '_original_socket'):
            socket.socket = socket._original_socket
        return
    if not hasattr(socket, '_original_socket'):
        socket._original_socket = socket.socket
    if proxy_str == 'tor':
        for port in (9050, 9150):
            try:
                import socks
                socks.set_default_proxy(socks.SOCKS5, '127.0.0.1', port, True)
                socket.socket = socks.socksocket
                socket.getaddrinfo = lambda hostname, port, family=0, type=0, proto=0, flags=0: \
                    [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (hostname, port))]
                TOR_MODE = True
                PROXY_URL = f'socks5://127.0.0.1:{port}'
                print(f"ðŸ§… Conectado via Tor/Orbot na porta {port}")
                return
            except ImportError:
                socket.socket = socket._original_socket
                sys.exit("Erro: Para usar Tor/Orbot, instale 'PySocks': pip install PySocks")
            except Exception:
                socket.socket = socket._original_socket
                continue
        socket.socket = socket._original_socket
        sys.exit("Erro: Nenhum proxy Tor/Orbot encontrado nas portas 9050 ou 9150.\n"
                 "  Ligue o Orbot e tente novamente, ou use --proxy socks5://127.0.0.1:9150")
    elif proxy_str.startswith('socks'):
        try:
            import socks
        except ImportError:
            sys.exit("Erro: Para usar proxy SOCKS, instale 'PySocks': pip install PySocks")
        m = re.match(r'socks([45])://([^:]+):(\d+)', proxy_str)
        if not m:
            sys.exit("Formato: socks5://host:port")
        ver, host, port = m.groups()
        socks.set_default_proxy(
            socks.SOCKS5 if int(ver) == 5 else socks.SOCKS4,
            host, int(port), True
        )
        socket.socket = socks.socksocket
        socket.getaddrinfo = lambda hostname, port, family=0, type=0, proto=0, flags=0: \
            [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (hostname, port))]
        TOR_MODE = True
    elif not proxy_str.startswith('http'):
        sys.exit("Proxy invÃ¡lido. Use socks5:// ou http://")

def create_opener():
    handlers = [
        urllib.request.HTTPSHandler(context=ssl_context),
        urllib.request.HTTPCookieProcessor(cookie_jar)
    ]
    if PROXY_URL and PROXY_URL.startswith('http'):
        handlers.insert(0, urllib.request.ProxyHandler({'http': PROXY_URL, 'https': PROXY_URL}))
    return urllib.request.build_opener(*handlers)

def build_request(url, referer=None):
    headers = HEADERS_BASE.copy()
    headers["User-Agent"] = random.choice(USER_AGENTS)
    if referer:
        headers["Referer"] = referer
    return urllib.request.Request(url, headers=headers)

def fetch(url, referer=None, expect_json=False, is_image=False):
    safe_url = quote(url, safe=':/?&=#%')
    opener = create_opener()
    timeout = TOR_TIMEOUT if TOR_MODE else TIMEOUT
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            req = build_request(safe_url, referer)
            if expect_json:
                req.add_header("Accept", "application/json, text/javascript, */*; q=0.01")
            if is_image:
                req.add_header("Accept", "image/webp,image/apng,image/*,*/*;q=0.8")
                req.add_header("Sec-Fetch-Dest", "image")
                req.add_header("Sec-Fetch-Mode", "no-cors")
            with opener.open(req, timeout=timeout) as resp:
                return resp.read(), resp.getheader('Content-Type', '')
        except urllib.error.HTTPError as e:
            if e.code == 403 and referer and attempt == 0:
                referer = None
                continue
            if e.code == 404:
                return None, None
            last_error = e
        except Exception as e:
            last_error = e
        if attempt < MAX_RETRIES - 1:
            time.sleep((2 ** attempt) + random.uniform(0, 1))
    if last_error:
        print(f"Falha permanente em {url}: {last_error}")
    return None, None

def unique_backup(path):
    base = path + '.bak'
    if not os.path.exists(base):
        return base
    counter = 1
    while os.path.exists(f"{base}.{counter}"):
        counter += 1
    return f"{base}.{counter}"

def safe_makedirs(path):
    if os.path.isdir(path): return
    parts = path.split(os.sep)
    current = ''
    for part in parts:
        if not part: continue
        current = os.path.join(current, part) if current else part
        if len(part) > 200:
            name, ext = os.path.splitext(part)
            short = hashlib.md5(part.encode()).hexdigest()[:12] + ext
            current = os.path.join(os.path.dirname(current), short) if os.path.dirname(current) else short
            part = short
        if os.path.isfile(current):
            backup = unique_backup(current)
            print(f"Renomeando arquivo '{current}' para '{backup}' para criar diretÃ³rio.")
            os.rename(current, backup)
            os.makedirs(current, exist_ok=True)
        elif not os.path.exists(current):
            os.makedirs(current, exist_ok=True)

def baixar_arquivo(url, caminho_local, referer=None, expect_json=False, force=False, is_image=False):
    global FAILED_RESOURCES, DOWNLOADED, INLINE_CACHE, SINGLE_FILE_MODE
    if SINGLE_FILE_MODE:
        nome = os.path.basename(caminho_local)
        if re.search(r'%24%7B|%3E%3C|\$\{|\}|\"|\'|<|>|&quot', nome):
            return False, None, 0
        min_d, max_d = (TOR_MIN_DELAY, TOR_MAX_DELAY) if TOR_MODE else (MIN_DELAY, MAX_DELAY)
        time.sleep(random.uniform(min_d, max_d))
        content, ct = fetch(url, referer, expect_json, is_image)
        if content:
            DOWNLOADED += 1
            print(f"âœ” {DOWNLOADED}: {url}")
            INLINE_CACHE[caminho_local] = content
            return True, ct
        else:
            FAILED_RESOURCES += 1
        return False, None, 0
    if os.path.isdir(caminho_local):
        backup = unique_backup(caminho_local)
        print(f"DiretÃ³rio '{caminho_local}' renomeado para '{backup}' para salvar arquivo.")
        if os.path.isdir(caminho_local):
            return False, None
        os.rename(caminho_local, backup)
    if not force and os.path.isfile(caminho_local) and os.path.getsize(caminho_local) > 0:
        return True, None
    safe_makedirs(os.path.dirname(caminho_local) or '.')
    dir_part = os.path.dirname(caminho_local)
    nome = os.path.basename(caminho_local)
    if len(nome) > 200:
        name, ext = os.path.splitext(nome)
        nome = hashlib.md5(nome.encode()).hexdigest()[:12] + ext
        caminho_local = os.path.join(dir_part, nome)
    min_d, max_d = (TOR_MIN_DELAY, TOR_MAX_DELAY) if TOR_MODE else (MIN_DELAY, MAX_DELAY)
    time.sleep(random.uniform(min_d, max_d))
    content, ct = fetch(url, referer, expect_json, is_image)
    if content:
        try:
            with open(caminho_local, 'wb') as f:
                f.write(content)
            DOWNLOADED += 1
            print(f"âœ” {DOWNLOADED}: {url}")
            return True, ct
        except Exception as e:
            print(f"Erro ao salvar {url}: {e}")
    else:
        FAILED_RESOURCES += 1
    return False, None

class MegaExtractor(HTMLParser):
    def __init__(self, base_url, dominio, include_external=False):
        super().__init__()
        self.base_url, self.dominio = base_url, dominio
        self.include_external = include_external
        self.links, self.assets = set(), set()

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        tag = tag.lower()
        if tag == 'a' and 'href' in attr:
            url = urljoin(self.base_url, attr['href'])
            if self._interno(url): self.links.add(url)
        for a in ('src','data-src','data-lazy-src','data-original','poster',
                  'data-poster','data','value','background','data-bg',
                  'data-image','data-thumb','data-url','content'):
            if a in attr and attr[a] and not attr[a].startswith('data:'):
                self._add_asset(attr[a])
        for srcset_attr in ('srcset','data-srcset','imagesrcset'):
            if srcset_attr in attr:
                self._parse_srcset(attr[srcset_attr])
        if tag == 'script' and 'src' in attr:
            self._add_asset(attr['src'])
        if tag == 'link':
            rel = attr.get('rel','').lower()
            if any(r in rel for r in ('stylesheet','icon','manifest','preload','prefetch','modulepreload','font')):
                self._add_asset(attr.get('href',''))
            elif 'href' in attr:
                url = urljoin(self.base_url, attr['href'])
                if self._valido_asset(url): self.assets.add(url)
        for style_attr in ('style','data-style'):
            if style_attr in attr:
                for m in re.finditer(r'url\(["\']?(.*?)["\']?\)', attr[style_attr], re.I):
                    self._add_asset(m.group(1))

    def _add_asset(self, url_str):
        if not url_str or url_str.startswith(('data:','javascript:','#','mailto:','tel:')):
            return
        url = urljoin(self.base_url, quote(url_str, safe=':/?&=#%@'))
        if self._valido_asset(url):
            self.assets.add(url)

    def _parse_srcset(self, srcset):
        for part in srcset.split(','):
            cand = part.strip().split()[0] if part.strip() else ''
            if cand:
                url = urljoin(self.base_url, quote(cand, safe=':/?&=#%@'))
                if self._valido_asset(url):
                    self.assets.add(url)

    def _valido_asset(self, url):
        if not url or not url.startswith(('http:','https:')):
            return False
        if re.search(r'\$\{|\}|%24%7B|%3E%3C|&quot', url, re.I):
            return False
        parsed = urlparse(url)
        return self.include_external or parsed.netloc == self.dominio

    def _interno(self, url):
        parsed = urlparse(url)
        return parsed.scheme in ('http','https') and parsed.netloc == self.dominio

def reescrever_html(html_bytes, base_url, dominio):
    texto = html_bytes.decode('utf-8', errors='ignore')
    texto = re.sub(re.escape(f"{urlparse(base_url).scheme}://{dominio}"), '', texto)
    texto = re.sub(re.escape(f"//{dominio}"), '', texto)
    return texto.encode('utf-8')

def reescrever_css(css_bytes, base_url, dominio):
    texto = css_bytes.decode('utf-8', errors='ignore')
    texto = re.sub(re.escape(f"{urlparse(base_url).scheme}://{dominio}"), '', texto)
    texto = re.sub(re.escape(f"//{dominio}"), '', texto)
    return texto.encode('utf-8')

TEXT_EXTS = {'.html','.htm','.css','.js','.json','.xml','.txt','.php','.asp','.aspx','.svg','.ts'}
def is_text_file(fname): return os.path.splitext(fname)[1].lower() in TEXT_EXTS

def encontrar_apis(conteudo_bytes, base_url, dominio):
    texto = conteudo_bytes.decode('utf-8', errors='ignore')
    endpoints = set()
    patterns = [
        r"""["'`](/[a-zA-Z0-9_\-./?=&%]+)["'`]""",
        rf"https?://{re.escape(dominio)}/([a-zA-Z0-9_\-./?=&%]+)",
        rf"//{re.escape(dominio)}/([a-zA-Z0-9_\-./?=&%]+)",
        r"""fetch\(["'`]([^"'\`]+)["'`]\)""",
        r"""axios\.(?:get|post|put|delete)\(["'`]([^"'\`]+)["'`]\)""",
        r"""\.get\(["'`]([^"'\`]+)["'`]\)""",
        r"""\.post\(["'`]([^"'\`]+)["'`]\)""",
    ]
    for p in patterns:
        for m in re.finditer(p, texto):
            path = m.group(1).split('?')[0]
            if path and not path.endswith(('.js','.css','.png','.jpg','.gif','.svg','.woff','.ttf','.html','.htm')):
                full = urljoin(base_url, path)
                parsed = urlparse(full)
                if parsed.netloc == dominio and parsed.scheme in ('http','https'):
                    endpoints.add(full)
    return endpoints

def bypass_mirror_verification(html_bytes, base_url):
    texto = html_bytes.decode('utf-8', errors='ignore')
    mirrors_match = re.search(r'MIRRORS\s*=\s*\[(.*?)\];', texto, re.DOTALL)
    if not mirrors_match:
        return None
    mirrors = []
    for m in re.finditer(r"\{\s*id:\s*(\d+)\s*,\s*url:\s*'([^']+)'\s*,\s*name:\s*'([^']+)'\s*\}", mirrors_match.group(1)):
        mirrors.append({'id': int(m.group(1)), 'url': m.group(2), 'name': m.group(3)})
    if not mirrors:
        return None
    test_file = '/static/speedtest.bin'
    test_match = re.search(r"TEST_FILE\s*=\s*'([^']+)'", texto)
    if test_match:
        test_file = test_match.group(1)
    ping_file = '/static/images/favicon-32x32.png'
    ping_match = re.search(r"PING_FILE\s*=\s*'([^']+)'", texto)
    if ping_match:
        ping_file = ping_match.group(1)
    print(f"ðŸ” Sistema de mirror detection encontrado ({len(mirrors)} mirrors). Executando bypass...")
    best_mirror = None
    best_speed = -1
    for mirror in mirrors:
        ping_url = mirror['url'].rstrip('/') + ping_file
        content, ct = fetch(ping_url, is_image=True)
        if content and len(content) > 100:
            test_url = mirror['url'].rstrip('/') + test_file
            start_test = time.time()
            test_content, _ = fetch(test_url)
            if test_content and len(test_content) > 100:
                speed = len(test_content) / (time.time() - start_test + 0.01)
                print(f"  Mirror {mirror['name']}: {speed/1024:.0f} KB/s")
                if speed > best_speed:
                    best_speed = speed
                    best_mirror = mirror
    if best_mirror:
        print(f"âœ… Mirror vencedor: {best_mirror['name']} â€” URL: {best_mirror['url']}")
        return best_mirror['url']
    if mirrors:
        return mirrors[0]['url']
    return None

def clonar_site(url_alvo, baixar_apis=True, deep_scan=False, force=False):
    global FAILED_RESOURCES, DOWNLOADED, INLINE_CACHE, SINGLE_FILE_MODE
    dominio = urlparse(url_alvo).netloc
    pasta = dominio.replace(':', '_')
    if not SINGLE_FILE_MODE:
        os.makedirs(pasta, exist_ok=True)
        print(f"ðŸ“ Pasta: {os.path.abspath(pasta)}")
    else:
        print(f"ðŸ“„ Gerando UnicoHtml.html diretamente (sem pastas)...")
    content, ct = fetch(url_alvo)
    if not content:
        print("âŒ NÃ£o foi possÃ­vel acessar a pÃ¡gina inicial.")
        return pasta
    new_url = bypass_mirror_verification(content, url_alvo)
    if new_url:
        url_alvo = new_url
        print(f"ðŸ”„ Iniciando clone a partir de: {url_alvo}")
        content, ct = fetch(url_alvo)
        if not content:
            print("âŒ Falha ao acessar a pÃ¡gina de destino.")
            return pasta
    content = re.sub(rb'<script>[\s\S]*?MIRRORS[\s\S]*?</script>', b'', content)
    parsed = urlparse(url_alvo)
    path = parsed.path
    if path.endswith('/') or not path:
        nome_arquivo = 'index.html'
    else:
        nome_arquivo = path.split('/')[-1]
        if '.' not in nome_arquivo: nome_arquivo += '.html'
        path = os.path.dirname(path) + '/'
    index_path = os.path.join(pasta, path.lstrip('/'), nome_arquivo)
    if SINGLE_FILE_MODE:
        INLINE_CACHE[index_path] = content
        html_bytes = content
        DOWNLOADED += 1
        print(f"âœ” {DOWNLOADED}: {url_alvo}")
    else:
        safe_makedirs(os.path.dirname(index_path) or '.')
        with open(index_path, 'wb') as f:
            f.write(content)
        html_bytes = content
        DOWNLOADED += 1
        print(f"âœ” {DOWNLOADED}: {url_alvo}")
    visitar = {url_alvo}
    visitados = set()
    recursos_ok = set()
    apis_pendentes = set()
    apis_baixadas = set()
    while visitar:
        url_atual = visitar.pop()
        if url_atual in visitados: continue
        visitados.add(url_atual)
        parsed = urlparse(url_atual)
        path = parsed.path
        if path.endswith('/') or not path:
            nome_arquivo = 'index.html'
        else:
            nome_arquivo = path.split('/')[-1]
            if '.' not in nome_arquivo: nome_arquivo += '.html'
            path = os.path.dirname(path) + '/'
        caminho_html = os.path.join(pasta, path.lstrip('/'), nome_arquivo)
        if url_atual == url_alvo:
            html_bytes = INLINE_CACHE.get(index_path, content) if SINGLE_FILE_MODE else open(index_path, 'rb').read()
        else:
            if SINGLE_FILE_MODE:
                ok, ct, _ = baixar_arquivo(url_atual, caminho_html, force=force)
                if not ok: continue
                html_bytes = INLINE_CACHE.get(caminho_html, b'')
            else:
                if not baixar_arquivo(url_atual, caminho_html, force=force)[0]: continue
                with open(caminho_html, 'rb') as f:
                    html_bytes = f.read()
        html_bytes = re.sub(rb'<script>[\s\S]*?MIRRORS[\s\S]*?</script>', b'', html_bytes)
        extrator = MegaExtractor(url_atual, dominio)
        extrator.feed(html_bytes.decode('utf-8', errors='ignore'))
        # Fallback para SvelteKit /_app/immutable/
        fallback_assets = set(re.findall(rb'(?:"|\')?(/_app/[\w\-./@]+)(?:"|\')?', html_bytes))
        for raw in fallback_assets:
            asset_url = urljoin(url_atual, raw.decode('utf-8', errors='ignore'))
            if asset_url not in recursos_ok and asset_url.startswith('http'):
                extrator.assets.add(asset_url)
        print(f"[{url_atual}] {len(extrator.links)} pÃ¡ginas, {len(extrator.assets)} recursos")
        for link in extrator.links:
            if link not in visitados: visitar.add(link)
        html_local = reescrever_html(html_bytes, url_atual, dominio)
        if SINGLE_FILE_MODE:
            INLINE_CACHE[caminho_html] = html_local
        else:
            safe_makedirs(os.path.dirname(caminho_html) or '.')
            with open(caminho_html, 'wb') as f:
                f.write(html_local)
        for asset_url in extrator.assets:
            if asset_url in recursos_ok: continue
            recursos_ok.add(asset_url)
            parsed_a = urlparse(asset_url)
            asset_path = parsed_a.path
            if asset_path.endswith('/'): continue
            nome = asset_path.split('/')[-1]
            asset_dir = os.path.dirname(asset_path).lstrip('/')
            is_media = nome.lower().endswith(('.png','.jpg','.jpeg','.gif','.webp','.svg','.mp4','.webm','.mp3','.ogg','.wav'))
            caminho_asset = os.path.join(pasta, asset_dir, nome)
            ok, ct = baixar_arquivo(asset_url, caminho_asset, referer=url_atual, force=force, is_image=is_media)
            if ok:
                if is_text_file(nome) and baixar_apis:
                    raw = INLINE_CACHE.get(caminho_asset) if SINGLE_FILE_MODE else open(caminho_asset, 'rb').read()
                    if not SINGLE_FILE_MODE:
                        with open(caminho_asset, 'rb') as f:
                            raw = f.read()
                    for ep in encontrar_apis(raw, asset_url, dominio):
                        if ep not in apis_baixadas: apis_pendentes.add(ep)
                if nome.endswith('.css'):
                    raw = INLINE_CACHE.get(caminho_asset) if SINGLE_FILE_MODE else open(caminho_asset, 'rb').read()
                    if not SINGLE_FILE_MODE:
                        with open(caminho_asset, 'rb') as f:
                            raw = f.read()
                    for css_url in re.findall(r'url\(["\']?(.*?)["\']?\)', raw.decode('utf-8', errors='ignore')):
                        abs_css = urljoin(asset_url, css_url)
                        if not abs_css.startswith('data:') and urlparse(abs_css).netloc == dominio:
                            if abs_css not in recursos_ok:
                                recursos_ok.add(abs_css)
                                parsed_c = urlparse(abs_css)
                                css_path = parsed_c.path
                                if not css_path.endswith('/'):
                                    nome_c = css_path.split('/')[-1]
                                    css_dir = os.path.dirname(css_path).lstrip('/')
                                    baixar_arquivo(abs_css, os.path.join(pasta, css_dir, nome_c), referer=asset_url, force=force)
                    css_local = reescrever_css(raw, asset_url, dominio)
                    if SINGLE_FILE_MODE:
                        INLINE_CACHE[caminho_asset] = css_local
                    else:
                        with open(caminho_asset, 'wb') as f:
                            f.write(css_local)
    if deep_scan and not SINGLE_FILE_MODE:
        print("\nðŸ”Ž Deep Scan...")
        for dir_path in COMMON_DIRS:
            test_url = urljoin(url_alvo, dir_path.rstrip('/') + '/')
            if test_url not in visitados:
                caminho_dir = os.path.join(pasta, dir_path, 'index.html')
                ok, _ = baixar_arquivo(test_url, caminho_dir, referer=url_alvo, force=force)
                if ok:
                    visitados.add(test_url)
                    visitar.add(test_url)
    if baixar_apis and not SINGLE_FILE_MODE:
        print("\nðŸŒ Baixando APIs...")
        for root, _, files in os.walk(pasta):
            for file in files:
                if is_text_file(file):
                    with open(os.path.join(root, file), 'rb') as f:
                        conteudo = f.read()
                    for ep in encontrar_apis(conteudo, url_alvo, dominio):
                        if ep not in apis_baixadas: apis_pendentes.add(ep)
        for ep_url in apis_pendentes:
            if ep_url in apis_baixadas: continue
            apis_baixadas.add(ep_url)
            parsed_ep = urlparse(ep_url)
            ep_path = parsed_ep.path
            if ep_path.endswith('/'): ep_path += 'index'
            nome_api = ep_path.split('/')[-1]
            if '.' not in nome_api: nome_api += '.json'
            ep_dir = os.path.dirname(ep_path).lstrip('/')
            caminho_api = os.path.join(pasta, ep_dir, nome_api)
            ok, ct = baixar_arquivo(ep_url, caminho_api, referer=url_alvo, expect_json=True, force=force)
            if not ok:
                ok, ct = baixar_arquivo(ep_url, caminho_api, referer=url_alvo, force=force)
            if ok and ct and 'xml' in ct and not nome_api.endswith('.xml'):
                os.rename(caminho_api, caminho_api.rsplit('.',1)[0] + '.xml')
        print(f"APIs baixadas: {len(apis_baixadas)}")
        with open(os.path.join(pasta, "APIsCaptureds.txt"), 'w', encoding='utf-8') as f:
            f.write(f"# {url_alvo}\nTotal: {len(apis_baixadas)}\n\n")
            for api in sorted(apis_baixadas):
                f.write(api + "\n")
    if not SINGLE_FILE_MODE:
        print(f"\nâœ… ConcluÃ­do! Baixados: {DOWNLOADED} | Falhas: {FAILED_RESOURCES}")
    return pasta

def inline_resource(resource_path, cache=None):
    if cache and resource_path in cache:
        data = cache[resource_path]
    elif os.path.isfile(resource_path):
        with open(resource_path, 'rb') as f:
            data = f.read()
    else:
        return None
    ext = os.path.splitext(resource_path)[1].lower()
    mime_map = {
        '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.gif': 'image/gif',
        '.svg': 'image/svg+xml', '.webp': 'image/webp', '.mp4': 'video/mp4', '.webm': 'video/webm',
        '.mp3': 'audio/mpeg', '.ogg': 'audio/ogg', '.woff': 'font/woff', '.woff2': 'font/woff2',
        '.ttf': 'font/ttf', '.css': 'text/css', '.js': 'application/javascript',
    }
    mime = mime_map.get(ext, 'application/octet-stream')
    b64 = base64.b64encode(data).decode('ascii')
    return f"data:{mime};base64,{b64}"

def create_unico_html(pasta_site, cache=None):
    index_path = os.path.join(pasta_site, 'index.html')
    if cache:
        html_bytes = cache.get(index_path)
        if html_bytes:
            html = html_bytes.decode('utf-8', errors='ignore')
        else:
            print("index.html nÃ£o encontrado no cache.")
            return
    else:
        if not os.path.isfile(index_path):
            print("index.html nÃ£o encontrado.")
            return
        with open(index_path, 'r', encoding='utf-8', errors='ignore') as f:
            html = f.read()
        cache = {}
    base_dir = os.path.abspath(pasta_site)
    html = re.sub(r'<script\s[^>]*src\s*=\s*["\']https?://[^"\']+["\'][^>]*>.*?</script>', '', html, flags=re.DOTALL | re.I)
    html = re.sub(r'<link\s[^>]*href\s*=\s*["\']https?://[^"\']+["\'][^>]*/?>', '', html, flags=re.I)
    html = re.sub(r'<script>\s*(?:var|window|document)\.\s*(?:ga|_ga|GoogleAnalyticsObject|__gaTracker)[^<]*</script>', '', html, flags=re.DOTALL | re.I)
    html = re.sub(r'<script>[^<]*?(?:google-analytics|googletagmanager)[^<]*</script>', '', html, flags=re.DOTALL | re.I)
    def resolve_local_path(url):
        clean = url.split('?')[0].split('#')[0]
        if clean.startswith('/'):
            return os.path.normpath(os.path.join(base_dir, clean.lstrip('/')))
        else:
            return os.path.normpath(os.path.join(base_dir, clean))
    def repl_asset(m):
        attr, url = m.group(1), m.group(2)
        if url.startswith(('http:', 'https:', 'data:', '#', 'javascript:')):
            return m.group(0)
        local = resolve_local_path(url)
        data_uri = inline_resource(local, cache)
        if data_uri:
            return f'{attr}="{data_uri}"'
        return m.group(0)
    html = re.sub(r'(src|href)="([^"]+)"', repl_asset, html, flags=re.I)
    def repl_css_url(m):
        raw = m.group(1).strip().strip("'").strip('"')
        if raw.startswith(('data:', 'http:', 'https:', '#')):
            return m.group(0)
        local = resolve_local_path(raw)
        data_uri = inline_resource(local, cache)
        if data_uri:
            return f"url({data_uri})"
        return m.group(0)
    html = re.sub(r'url\(([^)]+)\)', repl_css_url, html, flags=re.I)
    nav_script = """<script>
(function() {
    function loadPage(path) {
        if (!path.endsWith('.html')) path += '.html';
        return fetch(path).then(r => r.text()).then(html => {
            var doc = new DOMParser().parseFromString(html, 'text/html');
            document.body.innerHTML = doc.body.innerHTML;
            document.title = doc.title;
            window.history.pushState({}, '', path);
            var scripts = doc.querySelectorAll('script:not([src])');
            scripts.forEach(function(s) {
                var newScript = document.createElement('script');
                newScript.textContent = s.textContent;
                document.body.appendChild(newScript);
            });
        }).catch(err => alert('PÃ¡gina nÃ£o encontrada: ' + path));
    }
    document.addEventListener('click', function(e) {
        var target = e.target.closest('a');
        if (target && target.href && !target.href.startsWith('data:') && !target.href.startsWith('javascript:') && target.href.indexOf('#') === -1) {
            e.preventDefault();
            var url = new URL(target.href);
            var path = url.pathname;
            if (path.startsWith('/')) path = path.substring(1);
            loadPage(path || 'index.html');
        }
    });
    window.addEventListener('popstate', function() {
        var path = window.location.pathname.substring(1) || 'index.html';
        loadPage(path);
    });
})();
</script>"""
    html = html.replace('</body>', nav_script + '</body>', 1)
    if '</body>' not in html:
        html += nav_script
    nome_site = os.path.basename(os.path.abspath(pasta_site))
    pasta_destino = nome_site + '_UnicoArquivo'
    os.makedirs(pasta_destino, exist_ok=True)
    output_path = os.path.join(pasta_destino, 'UnicoHtml.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\nðŸ“„ UnicoHtml.html criado em: {output_path} ({len(html)} caracteres)")
    return output_path

class CustomHandler(SimpleHTTPRequestHandler):
    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in ('.php','.asp','.aspx','.jsp'):
            return 'text/html'
        return super().guess_type(path)
    def do_GET(self):
        path = self.path.split('?')[0]
        if not os.path.splitext(path)[1]:
            for ext in ('.json','.xml'):
                if os.path.isfile('.' + path + ext):
                    self.path = path + ext
                    break
        super().do_GET()

def porta_livre(inicio=8000):
    for p in range(inicio, inicio+100):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', p))
                return p
        except: pass
    raise OSError("Nenhuma porta livre")

def iniciar_servidor(diretorio, porta=8000):
    os.chdir(diretorio)
    p = porta_livre(porta)
    httpd = HTTPServer(('', p), CustomHandler)
    print(f"\nðŸš€ Servidor em http://localhost:{p}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor parado.")

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ('-h','--help'):
        print("Uso: python3 clonersite.py <URL> [opÃ§Ãµes]")
        print("  --all           Ativa --deep --force")
        print("  --tor / --proxy socks5://...   Usar Tor/proxy")
        print("  --deep          Vasculha diretÃ³rios comuns")
        print("  --force         Rebaixa tudo (sobrescreve)")
        print("  --no-api        NÃ£o baixar APIs")
        print("  --single-file   Gera UnicoHtml.html (site inteiro em um arquivo)")
        print("  --serve <pasta> [porta]  Apenas sobe servidor local")
        sys.exit(0)
    if sys.argv[1] == '--serve':
        if len(sys.argv) < 3:
            sys.exit("Uso: --serve <pasta> [porta]")
        pasta = sys.argv[2]
        porta = int(sys.argv[3]) if len(sys.argv) > 3 else 8000
        if not os.path.isdir(pasta): sys.exit("Pasta nÃ£o encontrada.")
        iniciar_servidor(pasta, porta)
        sys.exit(0)
    if sys.argv[1] == '--single-file':
        if len(sys.argv) < 3:
            sys.exit("Uso: --single-file <pasta_do_clone>")
        pasta = sys.argv[2]
        if os.path.isdir(pasta):
            create_unico_html(pasta)
        else:
            print("Pasta nÃ£o encontrada.")
        sys.exit(0)
    url = sys.argv[1]
    if not url.startswith('http'): url = 'http://' + url
    porta = 8000
    baixar_apis, deep, force, single_file = True, False, False, False
    proxy = None
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == '--all':
            deep = force = True
        elif arg == '--tor':
            proxy = 'tor'
        elif arg == '--proxy':
            i += 1
            proxy = sys.argv[i] if i < len(sys.argv) else sys.exit("Faltou valor para --proxy")
        elif arg == '--deep':
            deep = True
        elif arg == '--force':
            force = True
        elif arg == '--no-api':
            baixar_apis = False
        elif arg == '--single-file':
            single_file = True
        else:
            try: porta = int(arg)
            except: print(f"Ignorado: {arg}")
        i += 1
    parsed = urlparse(url)
    if parsed.hostname and parsed.hostname.endswith('.onion') and not proxy:
        print("ðŸ§… .onion detectado â€“ ativando Tor/Orbot automaticamente")
        proxy = 'tor'
    setup_proxy(proxy)
    if single_file:
        SINGLE_FILE_MODE = True
        INLINE_CACHE = {}
        pasta_virtual = clonar_site(url, baixar_apis, deep, force)
        create_unico_html(pasta_virtual, cache=INLINE_CACHE)
        print("âœ… Arquivo Ãºnico gerado. Nenhuma pasta foi criada.")
    else:
        pasta = clonar_site(url, baixar_apis, deep, force)
        iniciar_servidor(pasta, porta)
