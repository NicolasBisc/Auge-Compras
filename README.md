# Roteiro do README

Sep 29, 2026 · @Nelsimar

**Como usar:** escreva cada resposta do seu jeito, no espaço "Sua resposta". Não copie do relatório: explicar com as próprias palavras é o que prepara para a banca. Quando terminar uma seção, me avise. Eu só formato, corrijo a ortografia e deixo sugestões pequenas como comentário, sem trocar as suas ideias.

Em cada seção: as perguntas que ela precisa responder, onde encontrar a informação e um tamanho sugerido.

## Progresso

- [ ] 1\. Apresentação
- [ ] 2\. O problema e a adaptação para a Auge
- [ ] 3\. O que o sistema faz
- [ ] 4\. Como rodar
- [ ] 5\. Modelagem dos dados
- [ ] 6\. Decisão 1: cold start
- [ ] 7\. Decisão 2: escopo do MVP
- [ ] 8\. Decisão 3: preço fora do padrão
- [ ] 9\. Decisão 4: tolerância na conciliação
- [ ] 10\. Arquitetura e pastas
- [ ] 11\. Testes
- [ ] 12\. Limitações e próximos passos
- [ ] 13\. Uso de IA e dados fictícios

## 1. Apresentação

**Responda:** o que é o projeto, em uma frase? Para quem ele serve?

**Onde encontrar:** relatório do projeto, introdução.

**Tamanho:** 1 ou 2 frases e o link da demo.

Um sistema pensado para a Auge Contabilidade, que junta o controle de estoque com a projeção de compras — para a própria equipe da Auge decidir, todo dia, o que comprar, quando comprar e de qual fornecedor.

**Responda:**

- Qual era a dor da empresa do desafio (controle pelo WhatsApp, nota fiscal sem conferência)?
- Por que adaptar para a Auge, e quem pediu isso?
- O que virou o quê: produto, compra, venda, estoque?
- O que o domínio da Auge trouxe de ganho (certificado que vence)?

**Onde encontrar:** relatório, fases 1 a 3; guia de estudo, Decisão 5.

**Tamanho:** 1 parágrafo e 1 tabela de correspondência.

A empresa do desafio original controlava compra, estoque e venda de forma informal, registrando tudo pelo WhatsApp — produto, fornecedor, quantidade, preço e data da compra — sem nenhum indicativo de quanto e quando comprar, e sem comparação entre fornecedores.

O cenário foi adaptado para a Auge por pedido do próprio desafio: ele veio junto com um link do site da Auge, e a orientação foi manter fidelidade à marca.

Nesse novo cenário, os produtos viraram serviços digitais (certificado digital, token, licença, hora de consultoria); as compras viraram aquisições; as vendas viraram alocações — a entrega de um serviço a um cliente; e o nosso estoque virou uma capacidade digital: não é mais um produto guardado numa prateleira, e sim a diferença entre o que já chegou do fornecedor e o que já foi entregue a um cliente.

## 3. O que o sistema faz

**Responda:** para cada uma das quatro funções do desafio, o que ela resolve e em qual tela está.

- Cadastro de compra
- Evolução de preço comparando fornecedores
- Projeção de compra com preço esperado
- Conciliação do XML com o pedido

**Onde encontrar:** relatório, parte 2 (Entregáveis); as próprias telas do sistema.

**Tamanho:** 1 ou 2 frases por função. Um print de cada tela ajuda muito.

O sistema cobre as quatro entregas pedidas no desafio:

- **Cadastro de compra** — formulário de nova aquisição, com validação de quantidade, preço e data, na tela Aquisições.
- **Evolução de preço comparando fornecedores** — gráfico em degraus por fornecedor e tabela de comparação, na tela Evolução de preço.
- **Projeção de compra com preço esperado** — para cada item, quanto comprar, de qual fornecedor e por qual preço, na tela Projeção.
- **Conciliação do XML com o pedido** — confere quantidade, preço, emitente e duplicata antes de aceitar a nota, na tela Conciliação.

## 4. Como rodar

**Responda:** quais passos alguém sem contexto precisa seguir? Qual é a diferença entre rodar com servidor e abrir só a demonstração?

**Onde encontrar:** os comandos estão no fim deste roteiro, em "Referência rápida".

**Tamanho:** uma lista de passos, com a versão do Python exigida.

Para rodar com o back-end de verdade (Python 3.10 ou mais novo):

```
py -m pip install -r requirements.txt
py -m app.seed
py -m uvicorn app.main:app --reload
```

Depois é só abrir http://127.0.0.1:8000. O comando do seed recria o banco com os dados fictícios sempre que quiser recomeçar do zero.

Para só visualizar, sem instalar nada: a pasta `web/` funciona sozinha. Abrindo `web/index.html` pelo Live Server (ou com dois cliques), o sistema usa dados de exemplo e mostra a interface inteira — só não grava nada de verdade, porque não há banco por trás.

## 5. Modelagem dos dados

**Responda:**

- Quais são as entidades e o que cada uma representa?
- Por que a Aquisição (o combinado) é separada do Recebimento (o que chegou)?
- Por que o estoque não é uma tabela, e sim um cálculo?
- Por que 1 aquisição pode ter várias notas?

**Onde encontrar:** relatório, fase 2; `app/motor/dominio.py`.

**Tamanho:** 1 parágrafo curto por pergunta. Essas são as duas correções que você mesmo fez: vale contar isso.

O domínio tem cinco entidades: Serviço (o que a Auge revende), Fornecedor, Aquisição (o que foi combinado com o fornecedor), Recebimento (o que realmente chegou numa nota) e Alocação (o que foi entregue a um cliente).

A Aquisição fica separada do Recebimento porque nem sempre o que se combina chega de uma vez: um pedido de 20 vouchers pode chegar em duas notas, 12 e depois 8, e cada nota vira um Recebimento ligado à mesma Aquisição.

O estoque não é uma tabela porque ele muda de significado se for guardado: ele é sempre `recebido − alocado`, calculado na hora. Guardar um número fixo criaria a chance de ele ficar desatualizado assim que uma nota chegasse ou um cliente fosse atendido.

## 6. Decisão 1: cold start

**Responda:**

- O que o sistema faz quando ainda tem pouco histórico de um item?
- Por que 4 alocações e 30 dias? (pista: erro relativo ≈ 1/√n)
- De onde vem o número usado no começo, e por que ele não é inventado pelo sistema?
- Por que a renovação ficou fixa em 100%, e não como campo editável?

**Onde encontrar:** relatório, parte 2; `app/config.py`; tela Regras; Projeção do item "Certificado em nuvem".

**Tamanho:** 1 ou 2 parágrafos.

Quando um item tem pouco histórico, o sistema não inventa um ritmo de consumo: com menos de 30 dias de acompanhamento ou menos de 4 entregas a clientes, ele entra em modo cold start e passa a usar só fatos — o estoque mínimo que eu mesmo defino para aquele item, e as renovações de certificado já conhecidas.

O corte em 4 eventos vem da estatística: o erro relativo de uma estimativa de contagem é aproximadamente 1/√n. Com 4 eventos o erro passa de 50% — qualquer ritmo calculado ali seria estatisticamente indistinguível de chute. Com 16 eventos o erro cai para 25% (confiança média), e com 36 para 17% (confiança alta).

O mínimo usado no começo não é calculado pelo sistema — vem de mim, porque sou eu quem conhece o negócio quando ainda não há dado suficiente para o sistema aprender sozinho.

## 7. Decisão 2: escopo do MVP

**Responda:**

- O que ficou automático e o que ficou manual?
- Por que isso é uma decisão, e não falta de tempo? (pista: onde o risco de errar fica mais barato)
- Por que o aviso de renovação pelo WhatsApp ficou fora?

**Onde encontrar:** relatório, parte 2; fontes: Lean Startup e Lei de Gall.

**Tamanho:** 1 parágrafo e 1 lista curta de "automático" e "manual".

A regra que usei para decidir o escopo do MVP foi: automatizar a decisão, não a entrada de dado.

**Automático:** projeção de compra, comparação de preço entre fornecedores e conciliação da nota fiscal. **Manual:** cadastro da aquisição, casamento de um mesmo item entre nomes diferentes de fornecedores, e aviso de renovação ao cliente (que continua saindo pelo WhatsApp).

Essa fronteira não é falta de tempo — é escolher onde o risco de errar fica mais barato de corrigir. Um erro de digitação num cadastro manual é visível na hora; um erro de leitura automática se espalharia silenciosamente por toda a cadeia de cálculos. O aviso de renovação ficou de fora porque reconstruir dentro do sistema um canal que já funciona (o WhatsApp da Auge) gastaria esforço sem ganho proporcional.

## 8. Decisão 3: preço fora do padrão

**Responda:**

- Qual é a referência de preço, e por que mediana e não média?
- Por que 5% e 15%?
- O que o z modificado resolve (o fornecedor que sempre oscila)?
- Por que "este fornecedor mudou o preço" e "este fornecedor é mais caro" são métricas separadas?
- O que acontece com dois aumentos seguidos de 5%?

**Onde encontrar:** relatório, partes 2 e 3; tela Evolução de preço (a alta de 18% da Vértice); `app/motor/precos.py`.

**Tamanho:** 2 parágrafos.

A referência de preço de cada item é a mediana das últimas 5 compras em 180 dias — não a média, porque um preço isolado errado não arrasta a mediana, e ela aceita um novo patamar assim que ele se repete três vezes.

| Nível | Variação |
| --- | --- |
| Normal | até 5% |
| Nota | 5% a 15% |
| Alerta | 15% ou mais |

O z modificado resolve um problema específico: um fornecedor que sempre oscila (por exemplo, um item cujo preço segue o dólar) não pode disparar alerta toda hora só por oscilar. Ele mede se a variação está dentro da própria oscilação histórica daquele fornecedor e, se estiver, rebaixa o nível um degrau.

"Este fornecedor mudou o preço" e "este fornecedor é mais caro que os outros" são métricas separadas de propósito: um fornecedor pode estar com o preço estável e ainda ser o mais caro do mercado.

Um detalhe que travei sozinho e depois confirmei: como a referência é sempre a mediana do histórico bruto (nunca a última classificação), dois aumentos seguidos de 5% já compõem matematicamente para mais de 5% na segunda compra — o sistema pega isso sem precisar de uma regra extra de acúmulo.

## 9. Decisão 4: tolerância na conciliação

**Responda:**

- Quais são as três camadas e o que separa uma da outra?
- Por que R$ 10 ou 1%? De onde vem o conceito de materialidade?
- Por que as diferenças pequenas somam por fornecedor (o caso dos R$ 53)?
- Por que a quantidade de item contável tem tolerância zero?
- O que mais é conferido além de preço e quantidade (emitente, duplicata, chave)?

**Onde encontrar:** relatório, partes 2 e 3; tela Conciliação com as 8 notas de exemplo; `app/motor/conciliacao.py`.

**Tamanho:** 2 parágrafos e, se quiser, uma tabela das três camadas.

A tolerância da conciliação tem três camadas:

| Camada | O que cobre | Limite |
| --- | --- | --- |
| Arredondamento | diferença que a casa decimal explica | menos de R$ 0,01 no unitário |
| Materialidade | diferença pequena, registrada sem alarme | o maior entre R$ 10 e 1% da linha |
| Divergência | diferença que exige contestar | acima da materialidade |

O limite de R$ 10 (ou 1% da linha) vem do conceito de materialidade da auditoria contábil (NBC TA 320): abaixo desse valor, contestar custa mais em tempo administrativo do que se recupera.

Diferenças pequenas do mesmo fornecedor somam ao longo de 90 dias — passando de R$ 50, viram alerta de padrão recorrente, mesmo que cada nota isolada fosse tolerável (ideia também da auditoria, NBC TA 450): ninguém deveria conseguir vazar dinheiro de centavo em centavo sem nunca disparar um alarme.

Item contável (voucher, token, licença) tem tolerância zero de quantidade — não existe "quase um voucher". Além de preço e quantidade, a conciliação confere se o emitente da nota é mesmo o fornecedor do pedido, se a chave de acesso tem os 44 dígitos com o dígito verificador correto, e recusa qualquer nota já importada antes.

## 10. Arquitetura e pastas

**Responda:**

- Quais linguagens e ferramentas foram usadas, e por que essas?
- Por que o motor não conhece o banco nem a tela?
- O que tem em cada pasta?

**Onde encontrar:** relatório, parte 4.

**Tamanho:** 1 parágrafo e a árvore de pastas com 1 linha por pasta.

O projeto usa Python (motor de cálculo, API com FastAPI, testes com pytest), SQL via SQLite para o banco, e HTML, CSS e JavaScript puros na interface — sem framework de front-end. Os dados trafegam em JSON entre a API e a tela, e as notas fiscais entram em XML.

O motor (`app/motor/`) não conhece o banco nem a tela de propósito: recebe listas de dados e devolve um resultado, o que permite testar cada decisão isolada, sem banco nem navegador.

- `app/` — o sistema: limiares centrais (`config.py`), banco (`db.py`), ponte entre banco e motor (`casos_de_uso.py`), API (`main.py`), gerador de dados fictícios (`seed.py`).
- `app/motor/` — as quatro decisões, puras: domínio, capacidade, projeção, preços, conciliação.
- `tests/` — um arquivo de teste por área do motor.
- `web/` — a interface: `index.html`, `css/estilo.css`, `js/app.js`, e os dados de exemplo usados sem servidor.
- `dados/notas_exemplo/` — 8 XMLs fictícios, um para cada regra da conciliação.

## 11. Testes

**Responda:** o que os testes garantem? Cite um teste de cada decisão. Como se roda?

**Onde encontrar:** pasta `tests/`; relatório, parte 4.

**Tamanho:** 3 a 5 frases.

Os testes garantem que cada uma das quatro decisões continua se comportando como documentado, mesmo depois de qualquer mudança no código. São 70 testes ao todo — por exemplo, um confirma que com menos de 4 entregas o sistema entra em cold start; outro, que dois aumentos de preço seguidos de 5% são pegos na segunda compra; outro, que uma nota fiscal já importada é rejeitada na segunda tentativa. Para rodar: `py -m pytest -q`.

## 12. Limitações e próximos passos

**Responda:** o que o sistema ainda não faz, e por quê? O que viria depois, com mais dados ou mais tempo?

**Onde encontrar:** relatório, parte 5 e "Onde não foram usadas".

**Tamanho:** 1 lista curta. Assumir as limitações mostra maturidade.

- NFS-e municipal ainda não é lida de verdade — o layout usado é o da NF-e, porque a NFS-e (padrão ABRASF) não tem quantidade estruturada por item; o parser fica isolado para ser trocado.
- A taxa de renovação de certificado está fixa em 100%, porque ainda não há dado suficiente para medir a taxa real.
- Não há sazonalidade modelada — precisaria de pelo menos 2 anos de histórico.
- O lote mínimo de compra por fornecedor não está representado.
- Os dados ficam carregados em memória, o que atende bem ao volume de um escritório de contabilidade.

Próximos passos: testar com 3 a 5 pessoas fazendo tarefas reais, configurar testes automáticos a cada envio no GitHub, e publicar a demonstração pelo GitHub Pages.

## 13. Uso de IA e dados fictícios

**Responda:**

- Os dados são reais? O que é inventado, e o que vem do site da Auge?
- Como você usou IA no projeto, e o que foi decisão e validação sua?

**Onde encontrar:** sua própria experiência no processo.

**Tamanho:** 2 a 4 frases, com transparência.

Todos os dados são fictícios: fornecedores, clientes, preços e até os CNPJs (com dígito verificador propositalmente inválido, para nunca coincidirem com uma empresa real). O que vem de verdade do site da Auge é só a marca — cores, logo e os tipos de certificado digital que ela oferece.

Usei um assistente de IA como par de programação ao longo do projeto, para escrever e revisar código, gerar os dados fictícios e montar a interface. As quatro decisões técnicas — cold start, escopo do MVP, regra de preço e tolerância da conciliação — foram discutidas, escolhidas e validadas por mim; é isso que vou defender na banca.

## Referência rápida

**Rodar com servidor** (Python 3.10 ou mais novo):

```
py -m pip install -r requirements.txt
py -m app.seed
py -m uvicorn app.main:app --reload
```

Depois, abra http://127.0.0.1:8000

**Rodar os testes:** `py -m pytest -q`

**Ver sem servidor:** abra `web/index.html` pelo Live Server; a página usa os dados de exemplo.

**Gerar de novo a demonstração:** `py -m scripts.exportar_demo`

**Checklist antes de publicar:**

- [ ] Todas as seções respondidas com as minhas palavras
- [ ] Consigo explicar cada número da tela Regras sem olhar
- [ ] As fontes citadas foram conferidas
- [ ] Link da demo funcionando
- [ ] Prints das telas principais
