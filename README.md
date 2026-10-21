# Bip: controle de embalagem

Registra **quem embalou cada pedido** do TikTok Shop, sem mudar o trabalho do gerente: ele continua bipando os pacotes no UpSeller, e o Bip anota cada bip em segundo plano.

## Por que existe

O pavilhão estava com muitas devoluções por peça errada (cliente pede uma calça e recebe uma bermuda), e não havia como saber quem tinha embalado o pacote. Sem esse dado, não dá para corrigir o processo nem conversar com a pessoa certa.

O UpSeller não tem API de pedidos e não guarda quem embalou. Então o Bip escuta o próprio leitor de código de barras.

## Como funciona

```
Separadores embalam e fecham a pilha
        │
Gerente clica no nome da pessoa no Bip  ──► tela fica na cor dela
        │
Gerente bipa os pacotes no UpSeller (como sempre)
        │
Bip ouve o leitor em segundo plano ──► grava: rastreio + colaborador + data/hora
```

- **1 bip só.** O leitor digita o código no UpSeller e o Bip ouve o mesmo bip pelo teclado do Windows.
- **Leitor ≠ pessoa.** Um bip é reconhecido pela velocidade: o leitor digita 10 a 30 caracteres em milissegundos e termina com Enter. Digitação humana e teclas simuladas por outros programas (como gerenciadores de senha) são ignoradas. Na primeira abertura, uma calibração de 3 bips mede a velocidade do leitor.
- **Tudo local.** Os dados ficam num arquivo SQLite no próprio PC (`%LOCALAPPDATA%\Bip\bip.db`). Nada vai para a internet.

## O que dá para fazer

- **Bipar**: escolher o colaborador ativo (tela inteira na cor dele, som próprio). Aviso para pacote repetido, pacote sem colaborador e bip que caiu na janela errada.
- **Corrigir**: mover um pacote para outro colaborador ou excluir.
- **Pesquisar**: pelo rastreio, completo ou só um pedaço, para ver quem embalou.
- **Registrar erro**: marcar "Peça errada" com observação. Erro de tamanho não conta.
- **Relatórios**: pacotes, erros e taxa de erro por colaborador, por dia, semana ou mês.
- **Colaboradores**: criar, renomear, trocar cor, desativar sem perder o histórico.
- **Alertas**: faixa vermelha e alarme se o programa cair ou o leitor parar de ser escutado.

## Instalação no PC do pavilhão

Basta o arquivo `bip.exe`. Não precisa de Python: ele já vem dentro do exe. Requisitos: Windows 10/11 64 bits e Chrome ou Edge.

1. Copie `bip.exe` para `C:\Bip\`.
2. Abra. Se o Windows ou o antivírus bloquear, libere a pasta `C:\Bip` (o exe não é assinado digitalmente).
3. Faça a calibração bipando 3 pacotes no UpSeller.
4. A partir daí ele abre sozinho com o Windows.

O manual de uso para o gerente está em [LEIAME.md](LEIAME.md).

## Para desenvolver

Python 3.14 no Windows.

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pytest                      # testes
.venv\Scripts\python scripts\dev.py       # interface em http://127.0.0.1:8765; digite rastreios no terminal para simular bips
powershell -ExecutionPolicy Bypass -File build.ps1   # gera dist\bip.exe
```

| Arquivo | Responsabilidade |
|---|---|
| `bip/detector.py` | Separa bip do leitor de digitação humana (tempo entre teclas + Enter) |
| `bip/teclado.py` | Escuta global do teclado (pynput), ignora teclas simuladas |
| `bip/servico.py` | Colaborador ativo, gravação do bip, eventos para a tela, calibração |
| `bip/db.py` | SQLite: colaboradores, registros, configuração, relatórios |
| `bip/relatorios.py` | Períodos dia / semana (seg–dom) / mês |
| `bip/web.py` | API JSON local (só aceita `127.0.0.1`/`localhost` e corpo JSON) |
| `bip/static/` | Interface (HTML, CSS e JS puro) |
| `bip/inicio.py`, `run.py` | Pasta de dados, início automático, instância única, janela do navegador |

Para testar o leitor com teclas simuladas (SendKeys), rode com `BIP_ACEITAR_SIMULADO=1`. Sem isso, teclas simuladas são ignoradas.

Decisões de projeto: [docs/superpowers/specs/2026-10-21-bip-design.md](docs/superpowers/specs/2026-10-21-bip-design.md).
