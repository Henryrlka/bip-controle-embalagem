# Bip — quem embalou cada pacote

O Bip roda no PC onde o gerente bipa os pacotes no UpSeller. Cada vez que um pacote é bipado no UpSeller, o Bip também anota o código de rastreio, quem embalou e a hora. Não precisa bipar duas vezes.

## Instalar no PC do pavilhão

1. Crie a pasta `C:\Bip` e copie o arquivo `bip.exe` para dentro dela.
2. Dê dois cliques no `bip.exe`. Ele abre uma janela estreita: deixe ao lado do UpSeller.
3. Se o Windows bloquear o programa:
   - Na tela azul "O Windows protegeu o computador", clique em **Mais informações** e depois em **Executar assim mesmo**.
   - Se o antivírus apagar ou bloquear o arquivo, abra **Segurança do Windows > Proteção contra vírus e ameaças > Gerenciar configurações > Exclusões > Adicionar ou remover exclusões > Adicionar uma exclusão > Pasta** e escolha `C:\Bip`. Depois copie o `bip.exe` de novo.
4. **Calibração**: na primeira vez aparece a tela "Calibração do leitor". Bipe 3 pacotes no UpSeller, normalmente. Esses pacotes ficam registrados como "Sem colaborador"; depois é só mover para a pessoa certa.
5. Clique em **Ativar som** (canto de baixo). O navegador só toca som depois de um clique.

A partir daí o Bip abre sozinho quando o PC liga.

## Uso no dia a dia

- **Antes de bipar a pilha de alguém**, clique no botão com o nome da pessoa. A tela fica na cor dela, com o nome grande.
- Cada pessoa tem um som. Pacote repetido faz dois bipes graves e aparece um aviso amarelo "Já registrado no …". Pacote sem colaborador escolhido faz dois bipes bem graves e fica vermelho.
- Bipou na pessoa errada? Na lista "Últimos bips", use **Mover para…**.
- Bipou algo por engano? **Excluir**.

## Quando chega reclamação de peça errada

1. Aba **Pesquisar**: digite o código de rastreio (ou só um pedaço, mínimo 3 números).
2. Aparece quem embalou. Clique em **Peça errada** e, se quiser, escreva o que aconteceu.
3. Erro de tamanho (cliente escolheu errado) não se marca.

## Relatórios

Aba **Relatórios**: escolha Hoje, Semana (segunda a domingo) ou Mês. Mostra pacotes, erros e taxa de erro de cada pessoa. Clique numa linha para ver os pacotes daquela pessoa.

## Colaboradores

Aba **Colaboradores**: adicionar, renomear, trocar a cor e desativar. Desativar tira o botão da tela mas mantém o histórico da pessoa. Marque "Mostrar desativados" para reativar.

**Recalibrar leitor** (fim da aba Colaboradores): use se trocar o leitor ou se os bips pararem de aparecer.

## Bom saber

- Os dados ficam só nesse PC, em `%LOCALAPPDATA%\Bip` (cole isso na barra do Explorador de Arquivos). **Não tem backup**: se essa pasta for apagada ou o PC formatado, o histórico se perde.
- O Bip ignora digitação feita por programas (como gerenciador de senha). Só o leitor e o teclado de verdade contam, e só quando a digitação é rápida como a de um leitor.
- Para o Bip não abrir mais sozinho: **Gerenciador de Tarefas > Aplicativos de inicialização > Bip > Desabilitar**.
- Fechou a janela sem querer? Dê dois cliques no `bip.exe` de novo: ele só reabre a janela, os bips continuam sendo anotados.
- Problema? O arquivo `%LOCALAPPDATA%\Bip\bip.log` mostra o que aconteceu.

## Para quem for mexer no código

- Python usado no build: 3.14 (venv em `.venv`, dependências em `requirements.txt`).
- Testes: `.venv\Scripts\pytest`
- Gerar o exe: `powershell -ExecutionPolicy Bypass -File build.ps1` → `dist\bip.exe`
- Interface sem leitor: `.venv\Scripts\python scripts\dev.py` e digite rastreios no terminal.
- Simular leitor com SendKeys exige `BIP_ACEITAR_SIMULADO=1` (teclas simuladas são ignoradas por padrão).
