# Checklist: montar um cliente novo

Só para mim. Vai do guia recebido até ao link entregue. Baseado no deploy de teste de 25 nov. 2026 (gabibrbs.pythonanywhere.com). Os comandos de PowerShell correm no meu PC, na pasta do projeto, com o venv ativo (`.\venv\Scripts\Activate.ps1`). Os de Bash correm na consola do PythonAnywhere do cliente.

Regras que nunca mudam:
- A chave da API e os hashes nunca vão para o Git nem para o chat.
- Os documentos do cliente nunca entram em `exemplo/`: só em `dados/` no servidor.
- O cliente é dono das contas. Eu nunca peço o papel de *Owner*.

---

## 1. O que pedir ao cliente

- [ ] **O guia da casa:** um documento por tema (check-in, a casa, regras, como chegar, arredores, reservas, emergências), em `.md`, `.txt` ou `.pdf`.
  - Revejo os documentos antes de os carregar.
  - Peço para **tirar o código da porta ou da caixa das chaves**: o link é público para quem o tiver.
- [ ] Por alojamento:
  - o **nome**;
  - a **cor** (`#rrggbb`) e o **logótipo** (PNG ou JPG, até 500 KB), nos pacotes Complete e Premium;
  - a **mensagem quando o guia não tem a resposta** (por exemplo «Please message the host on Airbnb.»);
  - o **contacto do anfitrião**.
- [ ] Número de alojamentos: 1 no Essential, até 3 no Complete e no Premium.
- [ ] Que faça a sua parte das contas (secção 2.1). Envio-lhe o `DELIVERY.md`, secção 1.
- [ ] Marcar a chamada de configuração (30 a 45 min, com partilha de ecrã).

## 2. Contas

### 2.1. O cliente faz sozinho (cerca de 5 min)

- [ ] Conta Google, projeto na Google Cloud e faturação com o cartão dele.
  - Recomendar o **pré-pago do AI Studio** («Set up billing», mínimo 5 $): quando o saldo acaba, as chaves param, e isso serve de teto de gastos.
- [ ] Em IAM → **Grant access**, acrescentar o meu email com:
  - **Service Usage Admin** (`roles/serviceusage.serviceUsageAdmin`);
  - **API Keys Admin** (`roles/serviceusage.apiKeysAdmin`);
  - opcional: **Billing Account Costs Manager** (`roles/billing.costsManager`) na conta de faturação, para o alerta de orçamento.
- [ ] Conta **Developer** (10 $/mês) em **eu.pythonanywhere.com**, com servidores em Frankfurt.
  - Ao criar, confirmar que o site EU ainda existe e o preço.
  - O link fica `https://<conta>.eu.pythonanywhere.com`.

### 2.2. Eu faço (com o acesso IAM)

- [ ] Ativar a **Gemini API** (Generative Language API) no projeto.
- [ ] Criar a **chave da API** só durante a chamada, quando o `.env` do servidor já estiver aberto (secção 6), e restringi-la à Gemini API:
  1. Na Google Cloud do cliente, criar a chave e copiá-la.
  2. Colá-la diretamente na linha `GEMINI_API_KEY=` do `.env` no servidor e guardar o ficheiro.
  3. **Fechar a janela da chave sem a guardar em lado nenhum:** nada de Bloco de Notas, chat, email, captura de ecrã ou ficheiro no meu PC. Se for preciso outra vez, cria-se uma nova e apaga-se a antiga.
- [ ] Criar um **alerta de orçamento**, por exemplo 10 €/mês, com avisos a 50%, 90% e 100%. Lembrar que só envia emails e não trava os gastos.

### 2.3. Na chamada, o cliente faz com a minha ajuda

- [ ] **Desligar o registo de pedidos** no AI Studio, na página **Logs** (logs-policy: «As a project owner, you can turn logging on or off at any time from the Logs page in AI Studio»). Quem o faz é o cliente, que é o *project owner*. Se não der para desligar, pôr a retenção mais curta (7 dias) e avisar-me, porque o aviso de privacidade tem de mudar.
- [ ] Abrir o PythonAnywhere dele. Fazemos as secções 5 a 7 com ele a partilhar o ecrã: eu digo o que fazer, ele carrega o zip e escreve a palavra-passe.

## 3. No meu PC: chave secreta da sessão

- [ ] Gerar a chave da sessão (nova para cada cliente):

  ```powershell
  python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
  ```

- [ ] Guardar a linha num sítio temporário (Bloco de Notas, sem guardar). Nunca no Git.
- [ ] **A palavra-passe do anfitrião não passa por mim:** é o cliente que a escolhe e a escreve na consola dele, durante a chamada (secção 6). Eu nunca a sei.
- [ ] A senha do site (`SITE_PASSWORD_HASH`) é **só para testes**: num cliente real fica vazia.

## 4. Montar o código

- [ ] Correr os testes no PC (tudo a verde) e confirmar que não há nada por fazer commit:

  ```powershell
  python -m pytest -q
  ```

  ```powershell
  git status --short
  ```

- [ ] Criar o zip do último commit. Só inclui o que está no Git, por isso fica sem `.env`, sem `dados/` e sem `venv/`:

  ```powershell
  git archive --format=zip --prefix=Chatbot/ -o chatbot-$(git rev-parse --short HEAD).zip HEAD
  ```

- [ ] **Enviar o zip ao cliente por email antes da chamada** (cerca de 170 KB, sem segredos: só tem o código do Git) e pedir-lhe que o guarde no PC dele. É a forma mais simples: na chamada não preciso de controlo remoto, porque ele próprio carrega o ficheiro.

## 5. Deploy no PythonAnywhere (na conta do cliente, com ele a partilhar o ecrã)

- [ ] **Files:** o cliente carrega o zip que lhe enviei para `/home/<conta>/` (botão «Upload a file»).
- [ ] **Bash:**

  ```bash
  cd ~
  unzip chatbot-<commit>.zip
  mkvirtualenv chatbot --python=/usr/bin/python3.12
  pip install -r ~/Chatbot/requirements.txt
  cd ~/Chatbot
  python -m pytest -q
  ```

  O resultado esperado é «passed» com 1 «skipped», o teste do Git, porque o zip não tem a pasta `.git`.
- [ ] **Pasta de dados:**

  ```bash
  cp -r exemplo dados
  ```

- [ ] **Adaptar a pasta de dados ao cliente:**
  - Para cada alojamento, gerar um código aleatório (`python -c "import secrets; print(secrets.token_hex(3))"`).
  - Renomear a pasta: `mv dados/alojamentos/casa-da-ribeira-demo dados/alojamentos/<nome>-<código>`.
  - Apagar os documentos de exemplo dessa pasta.
  - Editar `dados/config.toml`: `slug` igual ao nome da pasta, `name`, `color`, `logo`, `not_found_message`, `host_contact`.
  - Um bloco `[[property]]` por alojamento, cada um com a sua pasta `alojamentos/<slug>/documentos/`.
  - O logótipo vai para a pasta do alojamento.
- [ ] **Web → Add a new web app → Manual configuration → Python 3.12**, e depois:
  - Source code e Working directory: `/home/<conta>/Chatbot`;
  - Virtualenv: `/home/<conta>/.virtualenvs/chatbot`;
  - Static files: `/static/` → `/home/<conta>/Chatbot/static`;
  - ficheiro WSGI: apagar tudo e deixar só as 3 linhas abaixo (o aviso «imported but unused» do editor é normal):

    ```python
    import sys
    sys.path.insert(0, "/home/<conta>/Chatbot")
    from wsgi import application
    ```

  - **Force HTTPS:** ligado.

## 6. O `.env` no servidor

- [ ] **Palavra-passe do anfitrião, escrita pelo cliente.** Na consola **Bash** dele:

  ```bash
  workon chatbot
  cd ~/Chatbot
  python set_host_password.py
  ```

  - O cliente escreve a palavra-passe duas vezes (pelo menos 10 caracteres). Não aparece no ecrã, por isso eu não a vejo na partilha.
  - O script mostra a linha `HOST_PASSWORD_HASH='...'`. O cliente copia-a para o `.env` abaixo; eu só confirmo que ficou bem colada.
  - Lembrar-lhe que a guarde num gestor de palavras-passe. Se a esquecer, repete este passo (`DELIVERY.md`, secção 4).

**Files** → `/home/<conta>/Chatbot/` → novo ficheiro `.env`:

```bash
GEMINI_API_KEY=<colada aqui ao criá-la (secção 2.2), e a janela fechada>
GEMINI_MODEL=gemini-3.5-flash-lite
GEMINI_FALLBACK_MODEL=gemini-3.6-flash
GEMINI_MAX_WAIT_SECONDS=40

SECRET_KEY=<da secção 3>
HOST_PASSWORD_HASH='<a linha que o script mostrou ao cliente>'
SITE_PASSWORD_HASH=

GUEST_QUESTIONS_PER_HOUR=20
QUESTIONS_PER_DAY=200

PUBLIC_BASE_URL=https://<conta>.eu.pythonanywhere.com
CLIENT_IP_HEADER=X-Real-IP
DATA_FOLDER=dados
```

- [ ] Os hashes ficam entre aspas simples, sem espaços à volta do `=`.
- [ ] **Web → Reload** e abrir o link.
  - Se der erro, ver o **error log**: um erro no `config.toml` aparece lá com a explicação.
- [ ] Confirmar no EU que o `X-Real-IP` também chega à app. Testado só no `www`: 5 logins errados de um telemóvel não devem bloquear o PC.

## 7. QR codes com o URL real

- [ ] **Bash:**

  ```bash
  workon chatbot
  cd ~/Chatbot
  python make_qr_codes.py
  ```

- [ ] Abrir cada `dados/alojamentos/<slug>/qr-code.png` no ecrã, **ler com o telemóvel e abrir o link**: tem de aparecer a página certa.
- [ ] Ou o botão «Download QR code» em `/host/p/<slug>`.

## 8. Verificação no telemóvel

- [ ] 1. Abrir pelo QR: aparece a página do alojamento certo, com nome, cor, logótipo e contacto.
- [ ] 2. Pergunta em português: resposta em português com a fonte. Anotar o tempo.
- [ ] 3. Pergunta noutra língua (inglês ou espanhol): resposta nessa língua.
- [ ] 4. Pergunta sem resposta no guia: diz que não consta e usa a `not_found_message` traduzida.
- [ ] 5. «Privacidade»: o aviso com o nome e o contacto do cliente, os 18 anos e as 24 h.
- [ ] 6. `/host`: login, a lista de alojamentos com os links certos.
- [ ] 7. Carregar um documento de teste, perguntar sobre ele e apagá-lo.
- [ ] 8. «Download QR code» funciona.
- [ ] 9. Com vários alojamentos: o link de um não mostra o guia do outro, e `/` não lista nenhum.
- [ ] 10. O **server log** e o **error log** não têm o texto das perguntas.

## 9. Entregar ao cliente

- [ ] Enviar:
  - o link de cada alojamento;
  - os PNG dos QR codes;
  - o `DELIVERY.md`;
  - o endereço da página do anfitrião (`/host`).
- [ ] A palavra-passe do anfitrião não se envia: o cliente escolheu-a e escreveu-a ele na chamada (secção 6), e eu não a sei.
- [ ] Mostrar-lhe na chamada: carregar e apagar um guia, imprimir o QR, onde ver o saldo pré-pago.
- [ ] Lembrar:
  - nunca mudar o slug depois de imprimir o QR;
  - nada de códigos de porta no guia.
- [ ] Apagar do meu PC a linha temporária da chave da sessão e o zip.

## 10. Depois da entrega

### Atualizar o código (Premium: atualizações durante 3 meses)

- [ ] No PC: testes a verde, commit e novo zip (secção 4).
- [ ] Enviar o zip novo ao cliente por email. Numa chamada curta, ele carrega-o em **Files** com o ecrã partilhado.
- [ ] **Bash:**

  ```bash
  cd ~
  unzip -o chatbot-<commit>.zip
  workon chatbot
  pip install -r ~/Chatbot/requirements.txt
  ```

  O `-o` substitui os ficheiros antigos. O `.env` e `dados/` não estão no zip, por isso ficam como estavam. O `pip install` só é preciso se o `requirements.txt` mudou.
- [ ] **Web → Reload** e repetir os pontos 2, 5 e 6 da secção 8.

### Atualizar o guia (Premium)

- [ ] Pela página do anfitrião, com o login do cliente, ou peço-lhe que o faça. Nunca mudar o slug.

### Cópia de segurança de `dados/`

`dados/` tem tudo o que é do cliente: `config.toml`, guias, logótipos, QR codes, conversas e contadores.

- [ ] **Bash:**

  ```bash
  cd ~/Chatbot
  zip -r ~/backup-dados-$(date +%F).zip dados
  ```

- [ ] **Files:** descarregar o `backup-dados-<data>.zip` e guardá-lo **fora do Git**, de preferência na conta ou no disco do cliente (são dados dele).
- [ ] Quando fazer: depois da entrega, depois de cada mudança no guia ou no `config.toml`, e antes de cada atualização do código.
- [ ] **Repor:** `cd ~/Chatbot && unzip -o ~/backup-dados-<data>.zip` e depois **Reload**.
