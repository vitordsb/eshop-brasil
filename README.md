# E-Shop Brasil | Central de Dados com MongoDB, Streamlit e Docker

Projeto da disciplina **Advanced Databases and Big Data** (UniFECAF): aplicação prática de bancos de dados NoSQL e Big Data na gestão de dados, personalização e logística de um e-commerce de grande porte.

![Demonstração da aplicação](exemplos/demo.gif)

---

## 1. Introdução

A **E-Shop Brasil** é uma das maiores plataformas de comércio eletrônico do país: mais de 5 milhões de clientes ativos e cerca de 100 mil pedidos por dia. Com esse volume, a empresa enfrenta dois problemas centrais:

1. **Gestão de dados**: proteger dados pessoais e financeiros dos clientes (LGPD) e, ao mesmo tempo, analisar o histórico de compras para oferecer recomendações personalizadas.
2. **Logística**: reduzir prazos e atrasos de entrega, principalmente no Norte e no Nordeste, evitar falta de estoque e integrar os canais online e as lojas físicas (omnichannel).

**Objetivo do projeto:** montar um ambiente dockerizado com **MongoDB** e uma interface em **Streamlit** que simula a gestão e a análise de um grande volume de dados da empresa. A aplicação permite inserir, editar, excluir, concatenar e consultar dados, e transforma essas consultas em indicadores de vendas, logística e personalização.

## 2. Tecnologias utilizadas

| Tecnologia | Papel no projeto | Por que foi escolhida |
|---|---|---|
| **Docker / Docker Compose** | Sobe o MongoDB e a aplicação com um único comando | Ambiente idêntico em qualquer máquina, sem instalar banco localmente |
| **MongoDB 7** | Banco de dados NoSQL orientado a documentos | Esquema flexível (catálogo com atributos variados), documentos aninhados (itens e entrega dentro do pedido), escala horizontal com sharding e um framework de agregação para processar grandes volumes no próprio banco |
| **Streamlit** | Interface gráfica web em Python | Transforma scripts de dados em uma aplicação interativa com poucos componentes |
| **PyMongo** | Driver Python do MongoDB | CRUD, agregações e plano de execução (`explain`) |
| **pandas** | Manipulação tabular | Concatenação de fontes (`pd.concat`), deduplicação e exportação CSV |
| **Plotly** | Gráficos interativos | Dashboards de vendas, logística e estoque |
| **Faker (pt_BR)** | Geração de dados falsos realistas | Nomes, CPFs e e-mails brasileiros para simular milhares de clientes sem expor dados reais |

## 3. Arquitetura e modelagem dos dados

```
┌─────────────────────────┐        ┌──────────────────────────┐
│  eshop-app (Streamlit)  │ ─────► │  eshop-mongo (MongoDB 7) │
│  app.py · porta 8501    │ PyMongo│  base eshop_brasil       │
└─────────────────────────┘        │  volume mongo_data       │
                                   └──────────────────────────┘
```

A base `eshop_brasil` tem quatro coleções:

| Coleção | Conteúdo | Decisão de modelagem |
|---|---|---|
| `clientes` | Nome, CPF pseudonimizado, e-mail, cidade/UF/região, consentimento de marketing | CPF nunca é gravado em claro: só o hash SHA-256 com salt e uma versão mascarada |
| `produtos` | Nome, categoria, preço e estoque por centro de distribuição | Estoque **embutido** como array (`[{cd, quantidade}]`): é lido sempre junto com o produto |
| `pedidos` | Cliente, data, canal, status, itens, frete, valor e entrega | Itens e entrega **embutidos** no pedido; cliente e produto **referenciados** por `_id` |
| `visao_pedidos` | Junção de pedidos + clientes + produtos, uma linha por item vendido | Coleção materializada com `$out`, pronta para BI e relatórios |

Exemplo de documento da coleção `pedidos`:

```json
{
  "cliente_id": { "$oid": "6ae24b9ff0b0a6154e21d502" },
  "data": { "$date": "2026-09-14T09:09:43Z" },
  "canal": "App",
  "status": "Entregue",
  "itens": [
    { "produto_id": { "$oid": "6ae24b9ff0b0a6154e21d90f" }, "quantidade": 1, "preco_unitario": 928.9 }
  ],
  "frete": 22.9,
  "valor_total": 951.8,
  "entrega": {
    "cidade": "Recife", "estado": "PE", "regiao": "Nordeste",
    "modalidade": "Entrega em casa", "cd_origem": "CD Recife-PE", "cd_regional": true,
    "prazo_previsto_dias": 5, "prazo_real_dias": 5
  }
}
```

O endereço de entrega é copiado para dentro do pedido de propósito: ele registra **para onde aquele pedido foi**, mesmo que o cliente mude de cidade depois, e evita uma junção nas consultas de logística, que são as mais frequentes.

**Índices criados automaticamente** na inicialização: `cpf_hash` (único), `nome`, `estado`, `categoria`, `data`, `cliente_id`, `entrega.regiao + data` (composto), `itens.produto_id` (multikey) e `status`.

## 4. Descrição da aplicação

A interface tem cinco páginas, acessadas pelo menu lateral.

### 4.1 Inserção de dados no MongoDB (página _Inserir dados_)

- **Gerar massa de dados:** cria clientes, produtos e pedidos falsos com Faker `pt_BR` e insere em lotes de 5 mil documentos (`insert_many`). Na configuração padrão (3 mil clientes, 400 produtos e 30 mil pedidos dos últimos 180 dias), a carga leva cerca de 2 segundos e a tela mostra a vazão em documentos por segundo. Os dados seguem padrões realistas: cauda longa de popularidade de produtos, categorias preferidas por cliente e prazos maiores nas regiões mais distantes.
- **Cadastro manual:** formulários para cliente, produto e pedido. O pedido calcula frete, prazo e o CD de origem: sai do CD da região do cliente quando há estoque lá, ou do CD central (Cajamar-SP) quando não há. Depois dá baixa no estoque com o operador posicional `$inc` em `estoque.$.quantidade`.
- **Importar CSV:** carrega dados reais ou de parceiros (por exemplo, datasets do Kaggle) em `produtos` ou `clientes`. CPFs importados são convertidos em hash antes de gravar.

### 4.2 Edição e exclusão (página _Editar / Excluir_)

- Busca por nome (`$regex`) ou por código, edição em formulário (`update_one` com `$set`) e exclusão com confirmação (`delete_one`).
- Estoque por CD editável em tabela.
- **Direitos do titular (LGPD):** além de excluir, é possível **anonimizar** o cliente, o que remove nome, e-mail e CPF e mantém os pedidos para fins fiscais e estatísticos.
- **Ações em lote:** reajuste de preço por categoria (`update_many` com pipeline e `$round`), exclusão de pedidos cancelados (`delete_many`) e reposição de estoque zerado com `arrayFilters`.

### 4.3 Manipulação e concatenação de dados (página _Concatenar_)

1. **Junção de coleções (`$lookup`):** une pedidos, clientes e produtos em uma visão única. O campo `local_entrega` é montado com `$concat` (`"Recife/PE (Nordeste)"`). O resultado pode ser baixado em CSV ou **materializado** inteiro na coleção `visao_pedidos` com `$out` (cerca de 56 mil linhas em 2,5 s).
2. **Canais online + loja física (`pd.concat`):** simula duas fontes separadas, o e-commerce (site + app) e o PDV das lojas físicas, e empilha as duas em uma base omnichannel com a coluna `origem`.
3. **Catálogo + parceiro (CSV):** concatena o catálogo atual com o catálogo de um fornecedor (`dados/produtos_parceiro.csv`), remove duplicados pelo nome e insere só os produtos novos.

### 4.4 Consultas e exibição na interface (página _Consultas e análises_)

Todas as análises rodam no próprio MongoDB com **pipelines de agregação** (`$match`, `$group`, `$unwind`, `$lookup`, `$dateToString`, `$cond`...). Cada gráfico tem um botão _"Ver pipeline"_ que mostra a consulta usada. Filtros por período, região e canal.

- **Vendas:** pedidos, faturamento, ticket médio, clientes únicos, faturamento diário, por região, por canal e por categoria, top 10 produtos.
- **Logística e estoque:** prazo previsto x real por região, % de entregas atrasadas, comparação **CD regional x CD central**, modalidades de entrega (casa, retirada em loja, ponto de coleta) e produtos em risco de ruptura por CD.
- **Personalização:** _"quem comprou este produto também comprou"_ e recomendações por cliente com base nas categorias favoritas do histórico e no que mais vende na região dele. Clientes sem consentimento recebem aviso de que a recomendação fica só na navegação, sem e-mail marketing.
- **Consulta livre:** filtro em JSON sobre qualquer coleção, com o **plano de execução**: mostra se a consulta usou índice (`IXSCAN`) ou varreu a coleção (`COLLSCAN`) e quantos documentos foram examinados.

### 4.5 Segurança e privacidade (LGPD)

- CPF **pseudonimizado** (hash SHA-256 com salt) e exibido sempre mascarado (`***.123.456-**`); e-mails mascarados nas tabelas.
- Campo de **consentimento** de marketing respeitado nas recomendações.
- **Anonimização** e exclusão atendendo aos direitos do titular.
- MongoDB com **autenticação** ativada e porta exposta só em `127.0.0.1`; senha e salt vêm de variáveis de ambiente (`.env`), fora do código.

## 5. Como executar

### Pré-requisitos

Docker com Docker Compose (Docker Desktop, OrbStack ou Docker Engine).

### Opção 1: Docker Compose (recomendada)

```bash
git clone https://github.com/vitordsb/eshop-brasil.git
cd eshop-brasil
cp .env.example .env          # opcional: troque usuário, senha e salt
docker compose up -d --build
```

Acesse **http://localhost:8501**, vá em **Inserir dados > Gerar e inserir no MongoDB** e navegue pelas páginas.

Para parar: `docker compose down` (mantém os dados) ou `docker compose down -v` (apaga o volume do banco).

### Opção 2: docker build + docker run

```bash
docker network create eshop
docker run -d --name eshop-mongo --network eshop \
  -e MONGO_INITDB_ROOT_USERNAME=eshop_admin -e MONGO_INITDB_ROOT_PASSWORD=troque-esta-senha \
  mongo:7 --wiredTigerCacheSizeGB 0.25
docker build -t eshop-app .
docker run -d --name eshop-app --network eshop -p 8501:8501 \
  -e MONGO_URI="mongodb://eshop_admin:troque-esta-senha@eshop-mongo:27017/?authSource=admin" \
  eshop-app
```

### Opção 3: executar o app.py direto no Streamlit

Com o MongoDB rodando (por exemplo, só o serviço do compose: `docker compose up -d mongo`):

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export MONGO_URI="mongodb://eshop_admin:troque-esta-senha@localhost:27017/?authSource=admin"
streamlit run app.py
```

### Variáveis de ambiente

| Variável | Padrão | Uso |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | Conexão com o MongoDB |
| `MONGO_DB` | `eshop_brasil` | Nome da base |
| `LGPD_SALT` | `eshop-brasil-demo` | Salt do hash de CPF |
| `MONGO_USER` / `MONGO_PASSWORD` | `eshop_admin` / `troque-esta-senha` | Credenciais usadas pelo compose |

## 6. Testes e exemplos

Todas as funcionalidades foram testadas de ponta a ponta com o container rodando: geração em massa, cadastros manuais, importação de CSV, edição, anonimização, exclusão, ações em lote, `$lookup`, `$out`, `pd.concat`, dashboards e consulta livre com índice.

| Tela | O que mostra |
|---|---|
| ![](exemplos/02-gerar-massa-de-dados.png) | **Inserção em massa:** 3 mil clientes, 400 produtos e 30 mil pedidos inseridos em cerca de 2 s |
| ![](exemplos/03-inicio-com-dados.png) | **Início:** contagem das coleções, documento de exemplo e índices criados |
| ![](exemplos/04-consultas-vendas.png) | **Vendas:** KPIs, faturamento diário, por região, canal e categoria, top 10 produtos |
| ![](exemplos/05-consultas-logistica.png) | **Logística:** atraso por região e efeito do CD regional (no Norte, 14 dias saindo do CD central contra 6 saindo do CD de Manaus) |
| ![](exemplos/06-consultas-personalizacao.png) | **Personalização:** "quem comprou também comprou" e recomendações por cliente |
| ![](exemplos/07-consulta-livre-indice.png) | **Consulta livre:** filtro JSON e plano de execução usando índice (`IXSCAN`) |
| ![](exemplos/08-concatenar-lookup.png) | **Concatenação com `$lookup`** e materialização com `$out` |
| ![](exemplos/09-concatenar-canais.png) | **Concatenação com `pd.concat`:** e-commerce + lojas físicas |
| ![](exemplos/10-concatenar-catalogo-parceiro.png) | **Catálogo + parceiro:** concatena, remove duplicados e insere só o que é novo |
| ![](exemplos/11-editar-cliente-lgpd.png) | **Edição e exclusão** de cliente com anonimização (LGPD) |
| ![](exemplos/12-acoes-em-lote.png) | **Ações em lote:** `update_many`, `delete_many` e `arrayFilters` |

## 7. Do protótipo à escala real

O protótipo roda com dezenas de milhares de documentos, mas o desenho já acompanha o volume real da E-Shop (100 mil pedidos por dia, cerca de 36 milhões por ano):

- **Sharding** da coleção `pedidos` por `entrega.regiao` + `data` (ou por `cliente_id` com hash), distribuindo escrita e leitura entre servidores.
- **Replica set** para alta disponibilidade e leituras analíticas em nós secundários, sem afetar o checkout.
- **Visões materializadas** (`$out`/`$merge`) atualizadas periodicamente, como a `visao_pedidos`, alimentando BI.
- **Spark + MongoDB Connector** para processamento distribuído pesado (modelos de recomendação, previsão de demanda por CD) e um data lake (Hadoop/HDFS ou object storage) para o histórico completo.
- Banco **relacional** (PostgreSQL) mantido para o que exige transações ACID rígidas, como pagamentos e fiscal, em arquitetura de persistência poliglota.

## 8. Estrutura do repositório

```
eshop-brasil/
├── README.md
├── Dockerfile
├── docker-compose.yml
├── app.py
├── requirements.txt
├── .env.example
├── dados/
│   └── produtos_parceiro.csv
└── exemplos/
    ├── demo.gif
    └── 01 a 12 (prints das funcionalidades)
```

## 9. Autor

**Vitor de Souza Barreto** · RA 236770
UniFECAF · Advanced Databases and Big Data · 2026
