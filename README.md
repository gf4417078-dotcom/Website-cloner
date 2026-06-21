```markdown
# 🌐 ClonerSite - Clone completo de sites

Script avançado em Python para clonagem de sites estáticos e dinâmicos, com suporte a **Tor/Orbot**, **bypass de mirrors**, **extração de APIs** e geração de **arquivo único HTML** com todos os recursos embutidos.

---

## 🔗 Repositório original

O código-fonte completo está disponível no GitHub:  
👉 [gf4417078-dotcom/Website-cloner](https://github.com/gf4417078-dotcom/Website-cloner/blob/main/clonesite.py)

---

## 📋 Funcionalidades

- **Clonagem completa** de páginas HTML, CSS, JavaScript, imagens, fontes e mídia.
- **Extrai e baixa recursos** de atributos como `src`, `srcset`, `data-src`, `style`, `background`, etc.
- **Detecção e bypass de sistemas de mirror** (como em sites de download).
- **Suporte a Tor/Orbot** (`.onion` e proxies SOCKS5).
- **Deep scan** em diretórios comuns (`admin`, `api`, `wp-json`, etc.).
- **Extrai e baixa endpoints de API** encontrados em scripts e arquivos.
- **Reescreve links** para funcionamento offline.
- **Geração de único arquivo HTML** com todos os recursos embutidos em base64.
- **Servidor HTTP integrado** para visualização local do clone.

---

## 📦 Requisitos

- Python 3.6+
- Bibliotecas: `urllib`, `ssl`, `http.cookiejar` (já inclusas no Python)
- Opcional: `PySocks` (para proxies SOCKS5/Tor)

Instale o PySocks se for usar Tor ou proxy SOCKS:
```bash
pip install PySocks
```

---

🚀 Instalação

Clone o repositório ou baixe o script clonesite.py:

```bash
git clone https://github.com/gf4417078-dotcom/Website-cloner.git
cd Website-cloner
```

Dê permissão de execução (opcional):

```bash
chmod +x clonesite.py
```

---

🧩 Uso

Sintaxe básica

```bash
python3 clonesite.py <URL> [opções]
```

Exemplos

Clone simples de um site

```bash
python3 clonesite.py https://exemplo.com
```

Cria uma pasta com o nome do domínio e inicia um servidor HTTP local.

Clone com deep scan e força (rebaixar tudo)

```bash
python3 clonesite.py https://exemplo.com --all
```

Usando Tor/Orbot (para sites .onion ou anonimato)

```bash
python3 clonesite.py https://exemplo.onion --tor
```

Proxy SOCKS5 personalizado

```bash
python3 clonesite.py https://exemplo.com --proxy socks5://127.0.0.1:9150
```

Gerar um único arquivo HTML (tudo embutido)

```bash
python3 clonesite.py https://exemplo.com --single-file
```

Gera UnicoHtml.html na pasta dominio_UnicoArquivo/.

Servir uma pasta já clonada

```bash
python3 clonesite.py --serve pasta_clonada 8080
```

Inicia servidor na porta 8080.

Criar arquivo único a partir de um clone existente

```bash
python3 clonesite.py --single-file pasta_clonada
```

---

⚙️ Opções completas

Opção Descrição
--all Ativa --deep e --force simultaneamente
--deep Varre diretórios comuns (admin, api, wp-json, etc.)
--force Rebaixa todos os arquivos, sobrescrevendo os existentes
--tor Usa proxy Tor/Orbot (portas 9050 ou 9150)
--proxy <url> Usa proxy personalizado (ex: socks5://127.0.0.1:9150)
--no-api Não baixa endpoints de API
--single-file Gera um único HTML com tudo embutido (não cria pastas)
--serve <pasta> [porta] Inicia servidor HTTP para a pasta clonada
-h / --help Mostra ajuda

---

🧠 Funcionalidades em detalhe

🔍 Extração de recursos

O script analisa o HTML em busca de:

· Tags <img>, <script>, <link>, <source>, <video>, <audio>
· Atributos: src, srcset, data-src, data-lazy-src, poster, background, style, href, etc.
· Arquivos CSS: extrai url() de propriedades background-image, @font-face, etc.

🔄 Reescrita de links

Todos os links absolutos são convertidos para relativos, garantindo funcionamento offline.

🧩 Detecção de Mirror

Se o site possuir um sistema de mirrors (como em sites de download), o script testa cada mirror, escolhe o mais rápido e clona a partir dele.

🕵️ Extração de APIs

Varre arquivos .js, .html, .css em busca de padrões de chamadas a APIs (fetch, axios.get, etc.) e baixa os endpoints como arquivos .json ou .xml.

🔐 Suporte a Tor e proxies

· Detecta automaticamente domínios .onion e ativa o Tor.
· Permite proxy SOCKS4/SOCKS5 via --proxy.
· Funciona com Orbot (Android) ou Tor instalado localmente.

📦 Arquivo único

Com --single-file, todo o site é condensado em um único HTML com:

· Imagens, CSS, JS, fontes e mídia embutidos em base64.
· Navegação entre páginas via JavaScript (SPA-like).
· Remove scripts de analytics e rastreadores.

🌐 Servidor embutido

Após o clone, um servidor HTTP é iniciado automaticamente para visualização local. Use --serve para servir uma pasta já clonada.

---

⚠️ Notas importantes

· O script não clona conteúdo dinâmico gerado por JavaScript (exceto se os dados já estiverem no HTML ou em chamadas API).
· Em modo --single-file, o tamanho do HTML pode ser grande devido ao base64.
· Para sites muito grandes, recomendável usar --force e --deep com moderação.
· O uso de Tor pode deixar o processo mais lento; ajuste os delays nas variáveis TOR_MIN_DELAY e TOR_MAX_DELAY se necessário.

---

📝 Licença

Este projeto é disponibilizado sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

---

👨‍💻 Contribuição

Pull requests são bem-vindos. Para grandes mudanças, abra uma issue primeiro para discutir o que você gostaria de modificar.

---

Divirta-se clonando! 😄

```