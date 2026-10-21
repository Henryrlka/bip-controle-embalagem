# Bip — rastreio de quem embalou cada pacote

Data: 2026-10-21. Origem: sessão de grilling com o dono do pavilhão.

## Problema

Pavilhão envia pedidos TikTok Shop. Muitas devoluções por peça errada (pediu calça, chegou bermuda). Hoje não se sabe qual colaborador embalou cada pacote.

Fluxo atual: imprime etiqueta, cola no saco, produto em cima. Pilhas vão para 2 separadores que conferem, embalam e fecham. Gerente bipa o pacote fechado no UpSeller (código de rastreio TikTok) e põe na gaiola.

## Objetivo

Só rastrear (não prevenir). Vincular cada rastreio ao colaborador que embalou. Permitir pesquisar "quem embalou o rastreio X" e medir erros por pessoa.

## Decisões

1. **Bip único.** Gerente continua bipando só no UpSeller. Programa local escuta o leitor em segundo plano (hook global de teclado) e grava rastreio + colaborador ativo + data/hora. UpSeller não tem API de pedidos (só estoque), por isso o hook.
2. **Filtro do bip.** Só sequência digitada rápido terminada em Enter, 10 a 30 letras/números. Formato atual: 15 dígitos, ex. `999882543964725`. Naquele PC só se bipa pacote.
3. **Calibração.** Na primeira abertura, modo teste: gerente bipa 3 pacotes e o programa mede a velocidade do leitor. Botão "Recalibrar". Bips da calibração também são gravados normalmente.
4. **Colaborador ativo.** Gerente troca pela interface. Tela inteira na cor do colaborador, nome grande, som diferente por pessoa.
5. **Sem colaborador.** Bip sem colaborador escolhido (ou programa recém-aberto) grava como "Sem colaborador", destaque vermelho, para atribuir depois.
6. **Repetido.** Rastreio já gravado não grava de novo. Avisa "Já registrado no {nome}".
7. **Correção.** Mover registro para outro colaborador. Excluir com confirmação.
8. **Colaboradores.** Muitos temporários: criar, renomear, desativar livremente. Desativar não apaga histórico.
9. **Interface web** em `localhost`, só naquele PC. Pesquisa por rastreio completo ou parcial mostra quem embalou.
10. **Erro.** Sem bipar devolução. Pesquisa o rastreio, clica "Peça errada", observação opcional. Erro de tamanho não conta (não se registra).
11. **Relatórios** (só na interface): pacotes por colaborador (dia/semana/mês), erros por colaborador, taxa de erro (erros ÷ pacotes), lista de pacotes por pessoa.
12. **Dados locais.** Sem backup, sem exportação Excel. Abre sozinho com o Windows.
13. **Entrega.** `.exe` gerado no PC de desenvolvimento, copiado para o PC do pavilhão (Windows 11, sem Python). `.exe` não assinado: dono adiciona exceção no Defender.

## Fora do escopo

Conferência de SKU, integração com UpSeller/TikTok, busca por número de pedido, bip de devolução, backup, acesso por rede/celular.
