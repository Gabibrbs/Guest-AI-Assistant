# Checklist: montar um cliente novo

Só para mim. Vai do guia recebido até ao link entregue. Baseado no deploy de teste de 25 nov. 2026 (gabibrbs.pythonanywhere.com) e corrigido depois do ensaio geral de 26 nov. 2026 (cliente fictício em Lisboa). Os comandos de PowerShell correm no meu PC, na pasta do projeto, com o venv ativo (`.\venv\Scripts\Activate.ps1`). Os de Bash correm na consola do PythonAnywhere do cliente.

Regras que nunca mudam:
- A chave da API e os hashes nunca vão para o Git nem para o chat.
- Os documentos do cliente nunca entram em `exemplo/`: só em `dados/` no servidor.
- O cliente é dono das contas. Eu nunca peço o papel de *Owner*.

Regras para dar comandos ao cliente (aprendidas no ensaio):
- **Um comando de cada vez.** Num bloco com vários comandos, o Bash continua depois de um erro e os seguintes falham de forma confusa.
- **Nada de `<...>` nos comandos.** No Bash, `<` e `>` são redirecionamentos: o comando falha ou faz outra coisa. Uso nomes exatos ou a variável `$SLUG`.
- **Um só caminho.** Nada de «se aparecer X faz Y»: escolher entre ramos também gera erros.
- **Depois de gerar um segredo na consola, escrever `clear`.** E nada de capturas de ecrã da consola nem do `.env`.

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
- [ ] Marcar a chamada de configuração (45 a 60 min, com partilha de ecrã).

## 2. Contas

### 2.1. O cliente faz sozinho (cerca de 15 min)

- [ ] Conta Google, projeto na Google Cloud e faturação com o cartão dele.
  - Recomendar o **pré-pago do AI Studio** («Set up billing», mínimo 5 $): quando o saldo acaba, as chaves param, e isso serve de teto de gastos.
- [ ] Em IAM → **Grant access**, acrescentar o meu email com:
  - **Service Usage Admin** (`roles/serviceusage.serviceUsageAdmin`);
  - **API Keys Admin** (`roles/serviceusage.apiKeysAdmin`);
  - opcional: **Billing Account Costs Manager** (`roles/billing.costsManager`) na conta de faturação, para o alerta de orçamento.
- [ ] Conta **Developer** (10 $/mês) em **eu.pythonanywhere.com**, com servidores em Frankfurt.
  - Ao criar, confirmar que o site EU ainda existe e o preço.
  - O link fica `https://CONTA.eu.pythonanywhere.com` (CONTA é o nome de utilizador dele).

### 2.2. Eu faço (com o acesso IAM)

- [ ] Ativar a **Gemini API** (Generative Language API) no projeto.
- [ ] Criar a **chave da API** só durante a chamada, quando o `.env` do servidor já estiver aberto (secção 6), e restringi-la à Gemini API:
  1. Na Google Cloud do cliente, criar a chave e copiá-la.
  2. Colá-la diretamente na linha `GEMINI_API_KEY=` do `.env` no servidor e guardar o ficheiro.
  3. **Fechar a janela da chave sem a guardar em lado nenhum:** nada de Bloco de Notas, chat, email, captura de ecrã ou ficheiro no meu PC. Se for preciso outra vez, cria-se uma nova e apaga-se a antiga.
- [ ] Criar um **alerta de orçamento**, por exemplo 10 €/mês, com avisos a 50%, 90% e 100%. Lembrar que só envia emails e não trava os gastos.

### 2.3. Na chamada, o cliente faz com a minha ajuda

- [ ] **Desligar o registo de pedidos** no AI Studio, na página **Logs** (logs-policy: «As a project owner, you can turn logging on or off at any time from the Logs page in AI Studio»). Quem o faz é o cliente, que é o *project owner*. Se não der para desligar, pôr a retenção mais curta (7 dias) e avisar-me, porque o aviso de privacidade tem de mudar.
- [ ] Abrir o PythonAnywhere dele. Fazemos as secções 5 a 8 com ele a partilhar o ecrã: eu digo o que fazer, ele carrega os ficheiros e escreve a palavra-passe.

## 3. Antes da chamada

- [ ] **A palavra-passe do anfitrião não passa por mim:** é o cliente que a escolhe e a escreve na consola dele, durante a chamada (secção 6). Eu nunca a sei.
- [ ] A chave secreta da sessão (`SECRET_KEY`) gera-se na consola do servidor, na secção 6, e vai direta para o `.env`. Nunca passa pelo meu PC.
- [ ] A senha do site (`SITE_PASSWORD_HASH`) é **só para testes**: num cliente real fica vazia.
- [ ] Ter à mão, numa pasta do meu PC fora do projeto, os ficheiros do cliente já revistos: os documentos do guia e o logótipo de cada alojamento.

## 4. Montar o código

- [ ] Correr os testes no PC (tudo a verde) e confirmar que não há nada por fazer commit:

  ```powershell
  python -m pytest -q
  ```

  ```powershell
  git status --short
  ```

- [ ] Apagar zips antigos e criar o zip do último commit. Só inclui o que está no Git, por isso fica sem `.env`, sem `dados/` e sem `venv/`:

  ```powershell
  Remove-Item chatbot-*.zip
  ```

  ```powershell
  git archive --format=zip --prefix=Chatbot/ -o chatbot-$(git rev-parse --short HEAD).zip HEAD
  ```

- [ ] **Enviar o zip ao cliente por email antes da chamada** (cerca de 170 KB, sem segredos: só tem o código do Git) e pedir-lhe que o guarde no PC dele. É a forma mais simples: na chamada não preciso de controlo remoto, porque ele próprio carrega o ficheiro.

## 5. Deploy no PythonAnywhere (na conta do cliente, com ele a partilhar o ecrã)

No ensaio, esta secção demorou 15 min (com os erros que deram origem às regras do topo).

- [ ] **Files:** em `/home/CONTA/`, o cliente carrega em **Upload a file** e escolhe o zip que lhe enviei (`chatbot-` seguido do código do commit, `.zip`).
- [ ] **Bash** (abrir uma consola em **Consoles → Bash**), um comando de cada vez:

  ```bash
  ls ~/chatbot-*.zip
  ```

  Tem de aparecer **um só** zip. Se aparecerem vários, apagar os antigos em **Files** antes de continuar.

  ```bash
  cd ~
  ```

  ```bash
  unzip chatbot-*.zip
  ```

  ```bash
  mkvirtualenv chatbot --python=/usr/bin/python3.12
  ```

  ```bash
  pip install -r ~/Chatbot/requirements.txt
  ```

  ```bash
  cd ~/Chatbot
  ```

  ```bash
  python -m pytest -q
  ```

  O resultado esperado é «passed» com 1 «skipped», o teste do Git, porque o zip não tem a pasta `.git`. No ensaio: `386 passed, 1 skipped`, em cerca de 1 min.

- [ ] **Pasta de dados:**

  ```bash
  cp -r exemplo dados
  ```

  ```bash
  rm -r dados/alojamentos/casa-da-ribeira-demo
  ```

- [ ] **Uma pasta por alojamento.** Para cada alojamento, na mesma consola:
  1. Escrever o nome do alojamento em minúsculas e com hífenes, sem acentos (por exemplo `alfama-rooftop-studio`), nesta linha:

     ```bash
     NOME=alfama-rooftop-studio
     ```

  2. Juntar-lhe um código aleatório, para ninguém adivinhar o link:

     ```bash
     SLUG=$NOME-$(python -c "import secrets; print(secrets.token_hex(3))")
     ```

     ```bash
     mkdir -p dados/alojamentos/$SLUG/documentos
     ```

     ```bash
     echo $SLUG
     ```

  3. **Apontar o slug que apareceu** (por exemplo `alfama-rooftop-studio-d52ef7`). Vai para o `config.toml` e para o link. Se a consola fechar, a variável perde-se: volta-se a escrever `SLUG=` com o slug apontado.

- [ ] **Logótipo** (pacotes Complete e Premium): em **Files**, entrar em `Chatbot/` → `dados/` → `alojamentos/` → a pasta do slug. **Confirmar que o caminho no topo da página acaba no slug** e só então **Upload a file**. O Files carrega para a pasta que está aberta, e é fácil estar na errada. Confirmar na consola:

  ```bash
  ls dados/alojamentos/$SLUG
  ```

  Tem de aparecer o logótipo e a pasta `documentos`.

- [ ] **`dados/config.toml`:** em **Files** → `Chatbot/` → `dados/` → `config.toml`, abre-se o editor. Mudar só os valores (os comentários com `#` ficam):

  | Campo | Valor |
  |---|---|
  | `slug` | o slug apontado |
  | `name` | o nome do alojamento |
  | `color` | a cor, `#rrggbb` |
  | `logo` | tirar o `#` do início da linha e pôr o nome do ficheiro (por exemplo `logo.png`). Sem logótipo, a linha fica com `#`. |
  | `not_found_message` | a mensagem do cliente |
  | `host_contact` | o contacto do cliente |

  - Com vários alojamentos: copiar o bloco `[[property]]` inteiro, um por alojamento.
  - **Save**.

- [ ] **Confirmar o `config.toml`** antes de passar à **Web**. Um erro (logótipo em falta, cor errada, slug diferente da pasta…) aparece logo aqui, explicado numa linha, sem ter de procurar no error log:

  ```bash
  python -c "from assistant.properties import load_properties; print(list(load_properties('dados')))"
  ```

  Tem de aparecer a lista dos slugs. Se aparecer `ConfigError`, corrigir o que a linha diz e repetir.

- [ ] **Web → Add a new web app → Manual configuration → Python 3.12**, e depois:
  - Source code e Working directory: `/home/CONTA/Chatbot`;
  - Virtualenv: `/home/CONTA/.virtualenvs/chatbot`;
  - Static files: `/static/` → `/home/CONTA/Chatbot/static`;
  - ficheiro WSGI: apagar tudo e deixar só as 3 linhas abaixo, com o nome de utilizador do cliente no lugar de `CONTA` (o aviso «imported but unused» do editor é normal):

    ```python
    import sys
    sys.path.insert(0, "/home/CONTA/Chatbot")
    from wsgi import application
    ```

  - **Force HTTPS:** ligado.
  - Uma conta gratuita (Beginner) só tem uma web app. Isto só me afeta nos meus testes: a conta Developer do cliente começa vazia.

## 6. O `.env` no servidor

No ensaio, esta secção demorou 10 min (incluindo encontrar o logótipo na pasta errada).

- [ ] **Chave secreta da sessão**, na consola Bash:

  ```bash
  workon chatbot
  ```

  ```bash
  cd ~/Chatbot
  ```

  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

  O cliente copia o texto para a linha `SECRET_KEY=` do `.env` (abaixo).

- [ ] **Palavra-passe do anfitrião, escrita pelo cliente:**

  ```bash
  python set_host_password.py
  ```

  - O cliente escreve a palavra-passe duas vezes (pelo menos 10 caracteres). Não aparece no ecrã, por isso eu não a vejo na partilha.
  - O script mostra uma linha que começa por `HOST_PASSWORD_HASH='`. O cliente copia-a **inteira** e substitui com ela a linha `HOST_PASSWORD_HASH=` do `.env`; eu só confirmo que ficou bem colada.
  - Lembrar-lhe que a guarde num gestor de palavras-passe. Se a esquecer, repete este passo (`DELIVERY.md`, secção 4).

- [ ] **Files** → `/home/CONTA/Chatbot/` → em «Enter new file name» escrever `.env` → **New file**. Colar e trocar cada `TROCAR`:

  ```bash
  GEMINI_API_KEY=TROCAR
  GEMINI_MODEL=gemini-3.5-flash-lite
  GEMINI_FALLBACK_MODEL=gemini-3.6-flash
  GEMINI_MAX_WAIT_SECONDS=40

  SECRET_KEY=TROCAR
  HOST_PASSWORD_HASH=TROCAR
  SITE_PASSWORD_HASH=

  GUEST_QUESTIONS_PER_HOUR=20
  QUESTIONS_PER_DAY=200

  PUBLIC_BASE_URL=https://TROCAR.eu.pythonanywhere.com
  CLIENT_IP_HEADER=X-Real-IP
  DATA_FOLDER=dados
  ```

  - `GEMINI_API_KEY`: a chave criada nesse momento (secção 2.2), colada aqui e a janela fechada.
  - `PUBLIC_BASE_URL`: o nome de utilizador do cliente no lugar de `TROCAR`.
  - Confirmar que não ficou nenhum `TROCAR`. Os hashes ficam entre aspas simples, sem espaços à volta do `=`. **Save**.

- [ ] Limpar a consola, para a chave da sessão e o hash não ficarem no ecrã:

  ```bash
  clear
  ```

- [ ] Confirmar outra vez que a app arranca, agora com o `.env`:

  ```bash
  python -c "import wsgi; print('OK')"
  ```

- [ ] **Web → Reload** e abrir o link. Aparece a página do alojamento com nome, cor, logótipo e contacto, e «0 documents».
  - Se der «Something went wrong», voltar a correr o comando do `OK` acima: mostra o erro numa linha.
- [ ] **Carregar o guia**: em `https://CONTA.eu.pythonanywhere.com/host`, o cliente entra com a sua palavra-passe, abre o alojamento e carrega **todos os documentos de uma vez** (o botão aceita vários ficheiros, até 5 MB no total). Confirmar o número de documentos na página dos hóspedes. No ensaio: 2 min para 7 documentos, um a um, antes de o botão aceitar vários.
- [ ] Confirmar no EU que o `X-Real-IP` também chega à app. Testado só no `www`: 5 logins errados de um telemóvel não devem bloquear o PC.

## 7. QR codes com o URL real

No ensaio: 2 min 30 s.

- [ ] **Bash**, um comando de cada vez:

  ```bash
  workon chatbot
  ```

  ```bash
  cd ~/Chatbot
  ```

  ```bash
  python make_qr_codes.py
  ```

- [ ] Em **Files**, abrir o `qr-code.png` de cada alojamento (na pasta do slug), **ler com o telemóvel e abrir o link**: tem de aparecer a página certa.
- [ ] Ou o botão «Download QR code» na página do alojamento, em `/host`.

## 8. Verificação no telemóvel

No ensaio: 4 min 30 s.

- [ ] 1. Abrir pelo QR: aparece a página do alojamento certo, com nome, cor, logótipo, contacto e o número certo de documentos.
- [ ] 2. Pergunta em português: resposta em português com a fonte.
- [ ] 3. Pergunta noutra língua (inglês ou espanhol): resposta nessa língua.
- [ ] 4. Pergunta sem resposta no guia: diz que não consta e usa a `not_found_message` traduzida.
- [ ] 5. «Privacidade»: o aviso com o nome e o contacto do cliente, os 18 anos e as 24 h.
- [ ] 6. `/host`: login, a lista de alojamentos com os links certos.
- [ ] 7. Carregar um documento de teste, perguntar sobre ele e apagá-lo.
- [ ] 8. «Download QR code» funciona.
- [ ] 9. Com vários alojamentos: o link de um não mostra o guia do outro, e `/` não lista nenhum.
- [ ] 10. O **error log** (onde a app escreve) não tem o texto das perguntas: só linhas `HTTP Request: POST … 200 OK`. Também não deve aparecer «AFC is enabled».
- [ ] 11. Tempo de resposta: no **access log** (separador **Web**), cada linha `POST /p/…/ask` termina com `response-time=` em segundos. Anotar o das perguntas 2 a 4.

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
- [ ] Apagar do meu PC o zip e a cópia dos ficheiros do cliente.

## 10. Depois da entrega

### Atualizar o código (Premium: atualizações durante 3 meses)

- [ ] No PC: testes a verde, commit e novo zip (secção 4).
- [ ] Enviar o zip novo ao cliente por email. Numa chamada curta, com o ecrã partilhado:
  1. Em **Files**, ele apaga o zip antigo de `/home/CONTA/` e carrega o novo.
  2. **Bash**, um comando de cada vez:

     ```bash
     cd ~
     ```

     ```bash
     unzip -o chatbot-*.zip
     ```

     ```bash
     workon chatbot
     ```

     ```bash
     pip install -r ~/Chatbot/requirements.txt
     ```

  O `-o` substitui os ficheiros antigos. O `.env` e `dados/` não estão no zip, por isso ficam como estavam. O `pip install` só é preciso se o `requirements.txt` mudou.
- [ ] **Web → Reload** e repetir os pontos 2, 5 e 6 da secção 8.

### Atualizar o guia (Premium)

- [ ] Pela página do anfitrião, com o login do cliente, ou peço-lhe que o faça. Nunca mudar o slug.

### Cópia de segurança de `dados/`

`dados/` tem tudo o que é do cliente: `config.toml`, guias, logótipos, QR codes, conversas e contadores.

- [ ] **Bash**, um comando de cada vez:

  ```bash
  cd ~/Chatbot
  ```

  ```bash
  zip -r ~/backup-dados-$(date +%F).zip dados
  ```

- [ ] **Files:** descarregar o `backup-dados-` com a data de hoje e guardá-lo **fora do Git**, de preferência na conta ou no disco do cliente (são dados dele).
- [ ] Quando fazer: depois da entrega, depois de cada mudança no guia ou no `config.toml`, e antes de cada atualização do código.
- [ ] **Repor:** em **Files**, carregar o backup para `/home/CONTA/` (só esse backup lá), e depois:

  ```bash
  cd ~/Chatbot
  ```

  ```bash
  unzip -o ~/backup-dados-*.zip
  ```

  E **Reload**.
